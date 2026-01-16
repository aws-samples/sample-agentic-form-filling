"""
Accessibility tree extraction and embedding-based filtering.

This module provides functions to extract the accessibility tree from a web page,
filter it based on semantic relevance using local embedding models, and format
it for LLM consumption.
"""

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
import numpy as np
import yaml
from playwright.async_api import Page

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================================
# Data Classes
# ============================================================================


class ChunkingStrategy(str, Enum):
    """Strategy for chunking the accessibility tree for embedding."""

    INDIVIDUAL_NODES = "individual_nodes"  # Embed each node's text separately
    SUBTREES = "subtrees"  # Embed node + descendants together


@dataclass
class AriaNode:
    """Parsed accessibility tree node from aria_snapshot() YAML."""

    role: str
    name: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List["AriaNode"] = field(default_factory=list)
    depth: int = 0


@dataclass
class EmbeddingChunk:
    """A chunk of text with its embedding and source node reference."""

    text: str
    embedding: Optional[List[float]] = None
    source_node: Optional[AriaNode] = None
    subtree_yaml: Optional[str] = None
    similarity_score: float = 0.0


# ============================================================================
# YAML Parser for aria_snapshot() output
# ============================================================================


class AriaSnapshotParser:
    """Parser for Playwright's aria_snapshot() YAML output.

    Parses YAML format like:
        - button "Submit" [focused]
        - list "Navigation":
          - listitem:
            - link "Home"
    """

    # Pattern: role "name" [attr1] [attr2=value]
    NODE_PATTERN = re.compile(
        r'^(?P<role>[a-zA-Z]+)(?:\s+"(?P<name>[^"]*)")?(?P<attrs>(?:\s+\[[^\]]+\])*)$'
    )

    def parse(self, yaml_string: str) -> List[AriaNode]:
        """Parse YAML string into AriaNode trees.

        Args:
            yaml_string: YAML output from aria_snapshot()

        Returns:
            List of root AriaNode objects
        """
        try:
            data = yaml.safe_load(yaml_string)
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML: {e}")
            return []

        if data is None:
            return []

        return self._parse_items(data, depth=0)

    def _parse_items(self, items: Any, depth: int) -> List[AriaNode]:
        """Recursively parse items into AriaNode objects."""
        nodes = []

        if isinstance(items, list):
            for item in items:
                parsed = self._parse_item(item, depth)
                nodes.extend(parsed)
        elif isinstance(items, str):
            node = self._parse_node_string(items, depth)
            if node:
                nodes.append(node)
        elif isinstance(items, dict):
            for key, value in items.items():
                node = self._parse_node_string(key, depth)
                if node:
                    if value is not None:
                        node.children = self._parse_items(value, depth + 1)
                    nodes.append(node)

        return nodes

    def _parse_item(self, item: Any, depth: int) -> List[AriaNode]:
        """Parse a single item (string or dict)."""
        if isinstance(item, str):
            node = self._parse_node_string(item, depth)
            return [node] if node else []
        elif isinstance(item, dict):
            nodes = []
            for key, value in item.items():
                node = self._parse_node_string(key, depth)
                if node:
                    if value is not None:
                        node.children = self._parse_items(value, depth + 1)
                    nodes.append(node)
            return nodes
        return []

    def _parse_node_string(self, text: str, depth: int) -> Optional[AriaNode]:
        """Parse 'role "name" [attrs]' format."""
        text = text.strip()
        if not text:
            return None

        match = self.NODE_PATTERN.match(text)
        if not match:
            # Handle text-only nodes or malformed entries
            return AriaNode(role="text", name=text, depth=depth)

        role = match.group("role")
        name = match.group("name")
        attrs_str = match.group("attrs") or ""

        # Parse attributes like [focused] [checked=true]
        attributes = {}
        for attr_match in re.finditer(r"\[([^\]=]+)(?:=([^\]]+))?\]", attrs_str):
            attr_name = attr_match.group(1)
            attr_value = attr_match.group(2) or "true"
            attributes[attr_name] = attr_value

        return AriaNode(role=role, name=name, attributes=attributes, depth=depth)


# ============================================================================
# Bedrock Embedding using Cohere Embed v4
# ============================================================================


class BedrockCohereEmbedder:
    """Embedding using AWS Bedrock Cohere Embed v4.

    Uses class-level singleton pattern for the Bedrock client.
    """

    _client = None
    _model_id = "global.cohere.embed-v4:0"  # Use inference profile for cross-region support
    _region = "us-west-2"
    _lock = asyncio.Lock()
    _executor = ThreadPoolExecutor(max_workers=1)
    _max_batch_size = 96  # Cohere embed v4 supports up to 96 texts per call

    @classmethod
    def _get_client(cls):
        """Get or create Bedrock client."""
        if cls._client is None:
            cls._client = boto3.client("bedrock-runtime", region_name=cls._region)
            logger.info(f"Created Bedrock client for region: {cls._region}")
        return cls._client

    @classmethod
    def _embed_sync(cls, texts: List[str], input_type: str) -> List[List[float]]:
        """Synchronous embedding using Bedrock Cohere."""
        if not texts:
            return []

        client = cls._get_client()
        all_embeddings = []

        # Process in batches of max_batch_size
        for i in range(0, len(texts), cls._max_batch_size):
            batch = texts[i:i + cls._max_batch_size]
            embed_start = time.time()

            request_body = {
                "texts": batch,
                "input_type": input_type,
                "embedding_types": ["float"],
            }

            try:
                response = client.invoke_model(
                    modelId=cls._model_id,
                    body=json.dumps(request_body),
                )
                response_body = json.loads(response["body"].read())

                # Cohere returns embeddings in response_body["embeddings"]["float"]
                embeddings = response_body.get("embeddings", {}).get("float", [])
                all_embeddings.extend(embeddings)

                embed_elapsed = time.time() - embed_start
                logger.debug(f"Embedded batch of {len(batch)} texts in {embed_elapsed:.3f}s")

            except Exception as e:
                logger.error(f"Bedrock embedding failed: {e}")
                raise

        return all_embeddings

    @classmethod
    async def embed_batch(
        cls, texts: List[str], input_type: str = "search_document"
    ) -> List[List[float]]:
        """Embed multiple texts asynchronously using Bedrock Cohere.

        Args:
            texts: List of text strings to embed
            input_type: "search_document" for chunks, "search_query" for queries

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        async with cls._lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                cls._executor,
                cls._embed_sync,
                texts,
                input_type,
            )

    @classmethod
    async def embed_single(cls, text: str, input_type: str = "search_query") -> List[float]:
        """Embed a single text."""
        result = await cls.embed_batch([text], input_type=input_type)
        return result[0] if result else []


# ============================================================================
# Tree Chunking Strategies
# ============================================================================


class TreeChunker:
    """Creates text chunks from parsed accessibility tree for embedding."""

    def __init__(
        self, strategy: ChunkingStrategy = ChunkingStrategy.SUBTREES
    ):
        self.strategy = strategy

    def create_chunks(self, nodes: List[AriaNode]) -> List[EmbeddingChunk]:
        """Create chunks based on configured strategy.

        Args:
            nodes: List of root AriaNode objects

        Returns:
            List of EmbeddingChunk objects ready for embedding
        """
        if self.strategy == ChunkingStrategy.INDIVIDUAL_NODES:
            return self._chunk_individual_nodes(nodes)
        else:
            return self._chunk_subtrees(nodes)

    def _chunk_individual_nodes(self, nodes: List[AriaNode]) -> List[EmbeddingChunk]:
        """Create one chunk per node (flattened tree)."""
        chunks: List[EmbeddingChunk] = []
        self._flatten_nodes(nodes, chunks)
        return chunks

    def _flatten_nodes(
        self, nodes: List[AriaNode], chunks: List[EmbeddingChunk]
    ) -> None:
        """Recursively flatten nodes into chunks."""
        for node in nodes:
            text = self._node_to_text(node)
            if text:
                chunks.append(
                    EmbeddingChunk(
                        text=text,
                        source_node=node,
                        subtree_yaml=self._node_to_yaml(node, include_children=False),
                    )
                )
            self._flatten_nodes(node.children, chunks)

    def _chunk_subtrees(self, nodes: List[AriaNode]) -> List[EmbeddingChunk]:
        """Create one chunk per subtree (node + descendants)."""
        chunks: List[EmbeddingChunk] = []
        for node in nodes:
            self._add_subtree_chunk(node, chunks)
        return chunks

    def _add_subtree_chunk(
        self, node: AriaNode, chunks: List[EmbeddingChunk]
    ) -> None:
        """Add a chunk for this node's subtree."""
        text = self._subtree_to_text(node)
        if text:
            chunks.append(
                EmbeddingChunk(
                    text=text,
                    source_node=node,
                    subtree_yaml=self._node_to_yaml(node, include_children=True),
                )
            )
        # Also process children as their own subtrees
        for child in node.children:
            self._add_subtree_chunk(child, chunks)

    def _node_to_text(self, node: AriaNode, parent_context: str = "") -> str:
        """Convert single node to text for embedding with semantic context.

        Enhances node text with inferred semantic context to improve embedding
        similarity matching. For example, a button named "10A" becomes
        "seat 10A button available" or "seat 10A button unavailable".
        """
        parts = []

        # Infer semantic context from node patterns
        context = self._infer_semantic_context(node, parent_context)
        if context:
            parts.append(context)

        parts.append(f"Role: {node.role}")

        if node.name:
            parts.append(f"Name: {node.name}")

        if node.attributes:
            attrs = ", ".join(f"{k}={v}" for k, v in node.attributes.items())
            parts.append(f"Attributes: {attrs}")

        return " | ".join(parts)

    # Pre-compiled regex for seat pattern (row number + seat letter A-K)
    _SEAT_PATTERN = re.compile(r'^(\d{1,2})([A-K])$', re.IGNORECASE)

    def _infer_semantic_context(self, node: AriaNode, parent_context: str = "") -> str:
        """Infer semantic context from node patterns.

        This helps the embedding model understand domain-specific meaning.
        For example, buttons with names like "10A", "12C" are likely seats.
        """
        context_parts = []

        # Seat pattern detection: alphanumeric names like "10A", "12C", "1F"
        # Common in airline seat maps
        if node.name:
            seat_pattern = self._SEAT_PATTERN.match(node.name)
            if seat_pattern:
                row = seat_pattern.group(1)
                seat_letter = seat_pattern.group(2).upper()
                context_parts.append(f"seat row {row}")
                context_parts.append(f"seat {node.name}")

                # Add availability context from attributes
                if node.attributes.get("disabled") == "true":
                    context_parts.append("unavailable occupied taken")
                else:
                    context_parts.append("available free selectable")

        # Form field detection
        if node.role in ("textbox", "combobox", "searchbox"):
            context_parts.append("input field form")

        # Navigation detection
        if node.role == "link":
            context_parts.append("navigation link clickable")

        # Button with specific keywords
        if node.role == "button" and node.name:
            name_lower = node.name.lower()
            if any(kw in name_lower for kw in ["submit", "continue", "next", "confirm"]):
                context_parts.append("submit action confirm")
            elif any(kw in name_lower for kw in ["cancel", "back", "previous"]):
                context_parts.append("cancel navigation back")

        # Inherit parent context if provided
        if parent_context:
            context_parts.append(parent_context)

        return " ".join(context_parts) if context_parts else ""

    def _subtree_to_text(self, node: AriaNode) -> str:
        """Convert node and all descendants to combined text."""
        texts = [self._node_to_text(node)]
        for child in node.children:
            child_text = self._subtree_to_text(child)
            if child_text:
                texts.append(child_text)
        return " ".join(texts)

    def _node_to_yaml(self, node: AriaNode, include_children: bool = False) -> str:
        """Reconstruct YAML representation of a node."""
        parts = [node.role]
        if node.name:
            parts.append(f'"{node.name}"')
        for attr, value in node.attributes.items():
            if value == "true":
                parts.append(f"[{attr}]")
            else:
                parts.append(f"[{attr}={value}]")

        line = " ".join(parts)

        if include_children and node.children:
            yaml_lines = [f"- {line}:"]
            for child in node.children:
                child_yaml = self._node_to_yaml(child, include_children=True)
                # Indent child lines
                for child_line in child_yaml.split("\n"):
                    yaml_lines.append(f"  {child_line}")
            return "\n".join(yaml_lines)
        else:
            return f"- {line}"


# ============================================================================
# Main Extractor Class
# ============================================================================


class AccessibilityTreeExtractor:
    """Extracts and filters accessibility trees using local embeddings."""

    def __init__(self, region: str = "us-west-2"):
        """
        Initialize the extractor.

        Args:
            region: AWS region for Bedrock client (kept for backward compatibility)
        """
        # Keep Bedrock as fallback option
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
        self.embedding_model = "amazon.titan-embed-text-v2:0"
        self._embedding_cache: Dict[str, List[float]] = {}
        # New components for local embedding
        self._parser = AriaSnapshotParser()

    async def extract_accessibility_tree(
        self, page: Page, max_depth: int = 5
    ) -> Optional[str]:
        """
        Extract the accessibility tree from the current page using ARIA snapshots.

        Args:
            page: Playwright page instance
            max_depth: Maximum depth to traverse (not used with aria_snapshot)

        Returns:
            YAML string of accessibility tree, or None if extraction fails
        """
        try:
            logger.info("Extracting accessibility tree via aria_snapshot()...")
            start_time = time.time()

            # Use Playwright's native aria_snapshot() method
            # This returns a YAML representation of the accessibility tree
            snapshot = await page.locator("body").aria_snapshot()

            elapsed = time.time() - start_time
            snapshot_lines = snapshot.count('\n') + 1 if snapshot else 0
            logger.info(f"Accessibility tree extracted: {len(snapshot)} chars, {snapshot_lines} lines in {elapsed:.3f}s")

            return snapshot
        except Exception as e:
            logger.error(f"Failed to extract accessibility tree: {e}")
            return None

    def _filter_tree_by_depth(
        self, node: Dict[str, Any], max_depth: int, current_depth: int = 0
    ) -> Dict[str, Any]:
        """
        Recursively filter the tree to a maximum depth.

        Args:
            node: Current node in the tree
            max_depth: Maximum depth to traverse
            current_depth: Current depth level

        Returns:
            Filtered node
        """
        if current_depth >= max_depth:
            return {k: v for k, v in node.items() if k != "children"}

        filtered_node = {k: v for k, v in node.items() if k != "children"}

        if "children" in node and node["children"]:
            filtered_children = [
                self._filter_tree_by_depth(child, max_depth, current_depth + 1)
                for child in node["children"]
            ]
            filtered_node["children"] = filtered_children

        return filtered_node

    def _flatten_tree_nodes(
        self, node: Dict[str, Any], nodes: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Flatten the accessibility tree into a list of nodes.

        Args:
            node: Root node of the tree
            nodes: Accumulator for nodes

        Returns:
            List of all nodes in the tree
        """
        if nodes is None:
            nodes = []

        # Add current node
        node_info = {
            "role": node.get("role", ""),
            "name": node.get("name", ""),
            "value": node.get("value", ""),
            "description": node.get("description", ""),
        }

        # Only include nodes with meaningful information
        if any(v for v in node_info.values()):
            nodes.append(node_info)

        # Recursively process children
        if "children" in node and node["children"]:
            for child in node["children"]:
                self._flatten_tree_nodes(child, nodes)

        return nodes

    def _create_node_text(self, node: Dict[str, Any]) -> str:
        """
        Create a text representation of a node for embedding.

        Args:
            node: Node dictionary

        Returns:
            Text representation
        """
        parts = []
        if node.get("role"):
            parts.append(f"Role: {node['role']}")
        if node.get("name"):
            parts.append(f"Name: {node['name']}")
        if node.get("value"):
            parts.append(f"Value: {node['value']}")
        if node.get("description"):
            parts.append(f"Description: {node['description']}")

        return " | ".join(parts) if parts else "empty node"

    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using AWS Bedrock Titan.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Check cache
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=self.embedding_model,
                body=json.dumps({"inputText": text}),
            )

            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding", [])

            # Cache the embedding
            self._embedding_cache[text] = embedding
            return embedding

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []

    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        if not vec1 or not vec2:
            return 0.0

        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return float(dot_product / (norm_v1 * norm_v2))

    def _filter_nodes_by_state_and_role(
        self,
        nodes: List[AriaNode],
        filter_states: Optional[List[str]] = None,
        filter_roles: Optional[List[str]] = None,
    ) -> List[AriaNode]:
        """
        Filter nodes by ARIA state attributes and/or roles.

        Args:
            nodes: List of AriaNode objects
            filter_states: State filters like ['-disabled', '+checked'].
                          '+state' requires the state, '-state' excludes it.
            filter_roles: Role filters like ['button', 'link'].

        Returns:
            Filtered list of AriaNode objects (with children also filtered)
        """
        if not filter_states and not filter_roles:
            return nodes

        # Parse state filters into required and excluded sets
        required_states = set()
        excluded_states = set()

        if filter_states:
            for state_filter in filter_states:
                if state_filter.startswith('+'):
                    required_states.add(state_filter[1:].lower())
                elif state_filter.startswith('-'):
                    excluded_states.add(state_filter[1:].lower())
                else:
                    # Default: treat as required
                    required_states.add(state_filter.lower())

        # Normalize role filters
        allowed_roles = set(r.lower() for r in filter_roles) if filter_roles else None

        def matches_filters(node: AriaNode) -> bool:
            """Check if a node matches the state and role filters."""
            # Check role filter
            if allowed_roles and node.role.lower() not in allowed_roles:
                return False

            # Check state filters
            node_attrs = {k.lower(): v.lower() for k, v in node.attributes.items()}

            # Check required states
            for state in required_states:
                # State can be a boolean attribute (e.g., [disabled]) or value (e.g., [pressed=true])
                if state not in node_attrs:
                    return False
                # If it's there, it should be "true" or present
                if node_attrs[state] not in ("true", ""):
                    return False

            # Check excluded states
            for state in excluded_states:
                if state in node_attrs and node_attrs[state] in ("true", ""):
                    return False

            return True

        def filter_recursive(node_list: List[AriaNode]) -> List[AriaNode]:
            """Recursively filter nodes and their children."""
            result = []
            for node in node_list:
                # Filter children first
                filtered_children = filter_recursive(node.children)

                # Check if this node matches
                if matches_filters(node):
                    # Create a new node with filtered children
                    filtered_node = AriaNode(
                        role=node.role,
                        name=node.name,
                        attributes=node.attributes,
                        children=filtered_children,
                        depth=node.depth,
                    )
                    result.append(filtered_node)
                else:
                    # Node doesn't match, but include matching children at this level
                    result.extend(filtered_children)

            return result

        return filter_recursive(nodes)

    def _format_filtered_nodes_as_yaml(self, nodes: List[AriaNode]) -> str:
        """Format filtered nodes as YAML-like output."""
        if not nodes:
            return "No nodes to display"

        lines = [f"Filtered Accessibility Tree ({self._count_nodes(nodes)} nodes):", ""]

        def format_node(node: AriaNode, indent: int = 0) -> None:
            prefix = "  " * indent + "- "
            parts = [node.role]
            if node.name:
                parts.append(f'"{node.name}"')
            for attr, value in node.attributes.items():
                if value == "true":
                    parts.append(f"[{attr}]")
                else:
                    parts.append(f"[{attr}={value}]")
            lines.append(prefix + " ".join(parts))

            for child in node.children:
                format_node(child, indent + 1)

        for node in nodes:
            format_node(node)

        return "\n".join(lines)

    def _count_nodes(self, nodes: List[AriaNode]) -> int:
        """Count total nodes including children."""
        count = len(nodes)
        for node in nodes:
            count += self._count_nodes(node.children)
        return count

    async def get_filtered_accessibility_tree(
        self,
        page: Page,
        query: Optional[str] = None,
        max_depth: int = 5,
        max_results: int = 20,
        similarity_threshold: float = 0.3,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.SUBTREES,
        filter_states: Optional[List[str]] = None,
        filter_roles: Optional[List[str]] = None,
    ) -> str:
        """
        Get the accessibility tree, optionally filtered by semantic relevance and/or state.

        Args:
            page: Playwright page instance
            query: Optional query for semantic filtering
            max_depth: Maximum depth to traverse (not used with aria_snapshot)
            max_results: Maximum number of nodes to return when filtering
            similarity_threshold: Minimum similarity score (0-1) for filtering
            chunking_strategy: How to chunk the tree for embedding
            filter_states: Filter by ARIA states. Use '+state' to require, '-state' to exclude.
                          Examples: ['-disabled'] for enabled only, ['+checked'] for checked only.
            filter_roles: Filter by ARIA roles. Only include nodes with these roles.
                         Examples: ['button'], ['button', 'link']

        Returns:
            YAML string of accessibility tree (filtered if query provided)
        """
        total_start = time.time()
        logger.info(
            f"get_filtered_accessibility_tree called: query={query!r}, threshold={similarity_threshold}, "
            f"strategy={chunking_strategy.value}, filter_states={filter_states}, filter_roles={filter_roles}"
        )

        # Extract tree using Playwright's ARIA snapshot
        tree_yaml = await self.extract_accessibility_tree(page, max_depth)
        if not tree_yaml:
            logger.error("Failed to extract accessibility tree - returning error message")
            return "Failed to extract accessibility tree"

        # If no query, return the full tree
        if not query:
            logger.info("No query provided - returning full accessibility tree (no filtering)")
            return tree_yaml

        # Parse YAML into structured nodes
        logger.info("Parsing YAML into structured nodes...")
        parse_start = time.time()
        try:
            nodes = self._parser.parse(tree_yaml)
        except Exception as e:
            logger.warning(f"Failed to parse tree for filtering, returning raw: {e}")
            return tree_yaml
        parse_elapsed = time.time() - parse_start

        def count_nodes(node_list: List[AriaNode]) -> int:
            count = len(node_list)
            for n in node_list:
                count += count_nodes(n.children)
            return count

        total_nodes = count_nodes(nodes)
        logger.info(f"Parsed {total_nodes} nodes from YAML in {parse_elapsed:.3f}s")

        if not nodes:
            logger.warning("No nodes parsed from tree - returning raw YAML")
            return tree_yaml

        # Apply state/role filters if provided
        if filter_states or filter_roles:
            nodes = self._filter_nodes_by_state_and_role(nodes, filter_states, filter_roles)
            filtered_count = count_nodes(nodes)
            logger.info(f"After state/role filtering: {filtered_count}/{total_nodes} nodes remain")

            if not nodes:
                return f"No nodes matched filters: states={filter_states}, roles={filter_roles}"

        # If no semantic query and we have state/role filters, format and return
        if not query and (filter_states or filter_roles):
            return self._format_filtered_nodes_as_yaml(nodes)

        # If no query at all, return the full tree
        if not query:
            logger.info("No query provided - returning full accessibility tree (no filtering)")
            return tree_yaml

        # Create chunks based on strategy
        logger.info(f"Creating chunks using strategy: {chunking_strategy.value}")
        chunk_start = time.time()
        chunker = TreeChunker(strategy=chunking_strategy)
        chunks = chunker.create_chunks(nodes)
        chunk_elapsed = time.time() - chunk_start
        logger.info(f"Created {len(chunks)} chunks in {chunk_elapsed:.3f}s")

        if not chunks:
            logger.warning("No chunks created - returning raw YAML")
            return tree_yaml

        # Log sample of chunk texts for debugging (first 5 with semantic context)
        chunks_with_context = [c for c in chunks if c.text.startswith("seat")]
        if chunks_with_context:
            logger.debug(f"Sample chunks with seat context ({len(chunks_with_context)} total):")
            for c in chunks_with_context[:5]:
                logger.debug(f"  - {c.text[:100]}...")
        else:
            logger.debug(f"Sample chunk texts (first 3):")
            for c in chunks[:3]:
                logger.debug(f"  - {c.text[:100]}...")

        # Embed chunks and query separately with appropriate input_types
        chunk_texts = [chunk.text for chunk in chunks]
        logger.info(f"Embedding {len(chunk_texts)} chunks + 1 query using Bedrock Cohere...")
        embed_start = time.time()

        try:
            # Embed chunks as search documents
            chunk_embeddings = await BedrockCohereEmbedder.embed_batch(
                chunk_texts, input_type="search_document"
            )
            # Embed query as search query
            query_embeddings = await BedrockCohereEmbedder.embed_batch(
                [query], input_type="search_query"
            )
            query_embedding = query_embeddings[0] if query_embeddings else []
        except Exception as e:
            logger.error(f"Embedding failed, returning unfiltered tree: {e}")
            return tree_yaml

        embed_elapsed = time.time() - embed_start
        logger.info(f"Embedding completed in {embed_elapsed:.3f}s")

        if not chunk_embeddings or len(chunk_embeddings) != len(chunk_texts):
            logger.warning(f"Embedding returned unexpected results: got {len(chunk_embeddings) if chunk_embeddings else 0}, expected {len(chunk_texts)}")
            return tree_yaml

        # Calculate similarities
        logger.info("Calculating cosine similarities...")
        sim_start = time.time()
        for i, chunk in enumerate(chunks):
            chunk.embedding = chunk_embeddings[i]
            chunk.similarity_score = self._calculate_similarity(
                query_embedding, chunk.embedding
            )
        sim_elapsed = time.time() - sim_start
        logger.info(f"Similarity calculation completed in {sim_elapsed:.3f}s")

        # Filter by threshold and sort by similarity
        filtered_chunks = [
            c for c in chunks if c.similarity_score >= similarity_threshold
        ]
        filtered_chunks.sort(key=lambda c: c.similarity_score, reverse=True)

        # Take top results
        top_chunks = filtered_chunks[:max_results]

        # Log filtering stats
        total_elapsed = time.time() - total_start
        logger.info(
            f"Filtering complete: {len(top_chunks)}/{len(chunks)} chunks matched "
            f"(threshold={similarity_threshold}, max_results={max_results})"
        )
        if top_chunks:
            top_score = int(top_chunks[0].similarity_score * 100)
            bottom_score = int(top_chunks[-1].similarity_score * 100) if len(top_chunks) > 1 else top_score
            logger.info(f"Score range: {top_score}% - {bottom_score}%")
        logger.info(f"Total get_filtered_accessibility_tree time: {total_elapsed:.3f}s")

        # Format output
        return self._format_filtered_results(top_chunks, query)

    def _format_filtered_results(
        self, chunks: List[EmbeddingChunk], query: str
    ) -> str:
        """Format filtered results with similarity scores.

        Args:
            chunks: List of filtered EmbeddingChunk objects
            query: The original search query

        Returns:
            Formatted string for display
        """
        if not chunks:
            return f"No elements matched query: '{query}'"

        lines = [
            f"Filtered Accessibility Tree ({len(chunks)} matches for: '{query}')",
            "",
        ]

        for i, chunk in enumerate(chunks, 1):
            node = chunk.source_node
            if not node:
                continue

            score_pct = int(chunk.similarity_score * 100)

            # Format: 1. [85%] button "Submit" [focused]
            node_str = node.role
            if node.name:
                node_str += f' "{node.name}"'
            if node.attributes:
                attrs = " ".join(
                    f"[{k}]" if v == "true" else f"[{k}={v}]"
                    for k, v in node.attributes.items()
                )
                node_str += f" {attrs}"

            lines.append(f"{i}. [{score_pct}%] {node_str}")

        return "\n".join(lines)

    def _format_nodes(
        self, nodes: List[Dict[str, Any]], include_scores: bool = False
    ) -> str:
        """
        Format nodes into a readable string for the LLM.

        Args:
            nodes: List of nodes to format
            include_scores: Whether to include similarity scores (not implemented yet)

        Returns:
            Formatted string
        """
        if not nodes:
            return "No nodes to display"

        formatted_lines = [f"Accessibility Tree ({len(nodes)} nodes):", ""]

        for i, node in enumerate(nodes, 1):
            role = node.get("role", "unknown")
            name = node.get("name", "")
            value = node.get("value", "")
            description = node.get("description", "")

            line_parts = [f"{i}. {role}"]

            if name:
                line_parts.append(f'name="{name}"')
            if value:
                line_parts.append(f'value="{value}"')
            if description:
                line_parts.append(f'desc="{description}"')

            formatted_lines.append(" - ".join(line_parts))

        return "\n".join(formatted_lines)


# ============================================================================
# HTML Semantic Filtering
# ============================================================================


@dataclass
class HtmlElement:
    """Parsed HTML element for semantic filtering."""

    tag: str
    text: str
    attributes: Dict[str, str]
    outer_html: str
    depth: int = 0


@dataclass
class HtmlEmbeddingChunk:
    """A chunk of HTML with its embedding and source element reference."""

    text: str
    embedding: Optional[List[float]] = None
    source_element: Optional[HtmlElement] = None
    similarity_score: float = 0.0


class HtmlSemanticFilter:
    """Filters HTML elements using semantic similarity."""

    # Interactive element tags to prioritize
    INTERACTIVE_TAGS = {
        "button", "a", "input", "select", "textarea", "form",
        "label", "option", "nav", "menu", "menuitem"
    }

    # Tags to include in filtering
    INCLUDED_TAGS = {
        "button", "a", "input", "select", "textarea", "form",
        "label", "option", "nav", "menu", "menuitem",
        "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "ul", "ol", "table", "tr", "td", "th",
        "img", "header", "footer", "section", "article", "aside"
    }

    def __init__(self):
        self._embedder = BedrockCohereEmbedder

    def parse_html_to_elements(self, html: str, max_elements: int = 500) -> List[HtmlElement]:
        """
        Parse HTML string into a list of HtmlElement objects.

        Args:
            html: Raw HTML string
            max_elements: Maximum number of elements to extract

        Returns:
            List of HtmlElement objects
        """
        import re

        elements = []

        # Pattern to match HTML tags with content
        # Matches: <tag attrs>content</tag> or <tag attrs />
        tag_pattern = re.compile(
            r'<(\w+)([^>]*)>([^<]*(?:<(?!/?\1)[^<]*)*)</\1>|<(\w+)([^>]*)/?>',
            re.IGNORECASE | re.DOTALL
        )

        for match in tag_pattern.finditer(html):
            if len(elements) >= max_elements:
                break

            if match.group(1):  # Opening/closing tag pair
                tag = match.group(1).lower()
                attrs_str = match.group(2)
                content = match.group(3).strip()
                outer_html = match.group(0)
            else:  # Self-closing tag
                tag = match.group(4).lower()
                attrs_str = match.group(5)
                content = ""
                outer_html = match.group(0)

            # Skip tags we don't care about
            if tag not in self.INCLUDED_TAGS:
                continue

            # Parse attributes
            attributes = {}
            attr_pattern = re.compile(r'(\w+)=["\']([^"\']*)["\']')
            for attr_match in attr_pattern.finditer(attrs_str):
                attributes[attr_match.group(1)] = attr_match.group(2)

            # Clean content (remove nested tags for text)
            clean_content = re.sub(r'<[^>]+>', ' ', content).strip()
            clean_content = re.sub(r'\s+', ' ', clean_content)

            # Skip empty elements (unless they have meaningful attributes)
            if not clean_content and not attributes.get('value') and not attributes.get('placeholder'):
                continue

            elements.append(HtmlElement(
                tag=tag,
                text=clean_content[:200],  # Truncate long text
                attributes=attributes,
                outer_html=outer_html[:500],  # Truncate long HTML
            ))

        return elements

    def _element_to_text(self, element: HtmlElement) -> str:
        """Convert an HTML element to text for embedding."""
        parts = [f"Tag: {element.tag}"]

        if element.text:
            parts.append(f"Text: {element.text}")

        # Include important attributes
        important_attrs = ['id', 'class', 'name', 'type', 'value', 'placeholder', 'href', 'title', 'aria-label']
        for attr in important_attrs:
            if attr in element.attributes:
                parts.append(f"{attr}: {element.attributes[attr]}")

        return " | ".join(parts)

    async def filter_html_semantically(
        self,
        html: str,
        query: str,
        max_results: int = 20,
        similarity_threshold: float = 0.3,
    ) -> str:
        """
        Filter HTML elements by semantic similarity to query.

        Args:
            html: Raw HTML string
            query: Search query
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            Formatted string of matching elements with scores
        """
        total_start = time.time()
        logger.info(f"filter_html_semantically called: query={query!r}, threshold={similarity_threshold}")

        # Parse HTML into elements
        logger.info("Parsing HTML into elements...")
        parse_start = time.time()
        elements = self.parse_html_to_elements(html)
        parse_elapsed = time.time() - parse_start
        logger.info(f"Parsed {len(elements)} elements from HTML in {parse_elapsed:.3f}s")

        if not elements:
            logger.warning("No elements parsed from HTML")
            return f"No elements found in HTML to filter for query: '{query}'"

        # Create chunks for embedding
        chunks = []
        for elem in elements:
            text = self._element_to_text(elem)
            if text:
                chunks.append(HtmlEmbeddingChunk(
                    text=text,
                    source_element=elem,
                ))

        if not chunks:
            logger.warning("No chunks created from elements")
            return f"No elements with content found for query: '{query}'"

        # Embed chunks and query separately with appropriate input_types
        chunk_texts = [chunk.text for chunk in chunks]
        logger.info(f"Embedding {len(chunk_texts)} chunks + 1 query using Bedrock Cohere...")
        embed_start = time.time()

        try:
            # Embed chunks as search documents
            chunk_embeddings = await self._embedder.embed_batch(
                chunk_texts, input_type="search_document"
            )
            # Embed query as search query
            query_embeddings = await self._embedder.embed_batch(
                [query], input_type="search_query"
            )
            query_embedding = query_embeddings[0] if query_embeddings else []
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return f"Embedding failed for query: '{query}'"

        embed_elapsed = time.time() - embed_start
        logger.info(f"Embedding completed in {embed_elapsed:.3f}s")

        if not chunk_embeddings or len(chunk_embeddings) != len(chunk_texts):
            logger.warning("Embedding returned unexpected results")
            return f"Embedding error for query: '{query}'"

        logger.info("Calculating cosine similarities...")
        for i, chunk in enumerate(chunks):
            chunk.embedding = chunk_embeddings[i]
            chunk.similarity_score = self._calculate_similarity(query_embedding, chunk.embedding)

        # Filter and sort
        filtered_chunks = [c for c in chunks if c.similarity_score >= similarity_threshold]
        filtered_chunks.sort(key=lambda c: c.similarity_score, reverse=True)
        top_chunks = filtered_chunks[:max_results]

        # Log stats
        total_elapsed = time.time() - total_start
        logger.info(
            f"HTML filtering complete: {len(top_chunks)}/{len(chunks)} elements matched "
            f"(threshold={similarity_threshold}, max_results={max_results})"
        )
        if top_chunks:
            top_score = int(top_chunks[0].similarity_score * 100)
            bottom_score = int(top_chunks[-1].similarity_score * 100) if len(top_chunks) > 1 else top_score
            logger.info(f"Score range: {top_score}% - {bottom_score}%")
        logger.info(f"Total filter_html_semantically time: {total_elapsed:.3f}s")

        return self._format_filtered_html(top_chunks, query)

    def _calculate_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        return float(dot_product / (norm_v1 * norm_v2))

    def _format_filtered_html(self, chunks: List[HtmlEmbeddingChunk], query: str) -> str:
        """Format filtered HTML results with similarity scores."""
        if not chunks:
            return f"No HTML elements matched query: '{query}'"

        lines = [
            f"Filtered HTML Elements ({len(chunks)} matches for: '{query}')",
            "",
        ]

        for i, chunk in enumerate(chunks, 1):
            elem = chunk.source_element
            if not elem:
                continue

            score_pct = int(chunk.similarity_score * 100)

            # Show the outer HTML (truncated)
            html_preview = elem.outer_html
            if len(html_preview) > 200:
                html_preview = html_preview[:200] + "..."

            lines.append(f"{i}. [{score_pct}%] {html_preview}")

        return "\n".join(lines)
