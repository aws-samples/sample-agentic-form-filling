#!/usr/bin/env python3
"""Explore the contents of an AgentCore episodic memory store.

This script helps debug and inspect what's stored in an AgentCore memory,
including events, branches, extracted memories, and reflections.

Usage:
    python scripts/explore_agentcore_memory.py [--memory-id ID] [--actor-id ACTOR] [--region REGION]

Examples:
    # List all actors and sessions in the memory
    python scripts/explore_agentcore_memory.py

    # Explore a specific actor's data
    python scripts/explore_agentcore_memory.py --actor-id globalair-com

    # Explore with specific memory ID
    python scripts/explore_agentcore_memory.py --memory-id mem-abc123 --actor-id globalair-com
"""

import argparse
import json
import os
import sys
from datetime import datetime

import boto3
from bedrock_agentcore.memory import MemoryClient


def format_timestamp(ts: str | None) -> str:
    """Format ISO timestamp to readable format."""
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def format_json(obj: dict | list, indent: int = 2) -> str:
    """Format object as indented JSON."""
    return json.dumps(obj, indent=indent, default=str)


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_subsection(title: str):
    """Print a subsection header."""
    print("\n" + "-" * 40)
    print(title)
    print("-" * 40)


def explore_memory_info(client: MemoryClient, memory_id: str):
    """Display basic memory information and strategies."""
    print_section("MEMORY INFORMATION")

    # Get memory details
    memories = client.list_memories(max_results=50)
    memory_info = None
    for mem in memories:
        if mem.get("id") == memory_id:
            memory_info = mem
            break

    if memory_info:
        print(f"Memory ID:   {memory_info.get('id')}")
        print(f"Name:        {memory_info.get('name', 'N/A')}")
        print(f"Status:      {memory_info.get('status', 'N/A')}")
        print(f"ARN:         {memory_info.get('arn', 'N/A')}")
        print(f"Created:     {format_timestamp(memory_info.get('createdAt'))}")
        print(f"Updated:     {format_timestamp(memory_info.get('updatedAt'))}")
    else:
        print(f"Memory ID: {memory_id}")
        print("(Could not fetch additional details)")

    # Get strategies
    print_subsection("Configured Strategies")
    try:
        strategies = client.get_memory_strategies(memory_id)
        if strategies:
            for i, strategy in enumerate(strategies, 1):
                print(f"\n[Strategy {i}]")
                strategy_type = strategy.get("memoryStrategyType", strategy.get("type", "unknown"))
                details = strategy

                print(f"  Type:       {strategy_type}")
                print(f"  Name:       {details.get('name', 'N/A')}")
                print(f"  Namespaces: {details.get('namespaces', [])}")
                if "reflectionConfiguration" in details:
                    print(f"  Reflections: {details['reflectionConfiguration'].get('namespaces', [])}")
        else:
            print("  No strategies configured")
    except Exception as e:
        print(f"  Error fetching strategies: {e}")


def explore_events(client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
    """Explore events (short-term memory) for a session."""
    print_subsection(f"Events for session: {session_id}")

    try:
        events = client.list_events(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            include_payload=True,
            max_results=50
        )

        if not events:
            print("  No events found")
            return

        print(f"  Found {len(events)} events\n")

        for i, event in enumerate(events, 1):
            event_id = event.get("eventId", "N/A")
            timestamp = format_timestamp(event.get("eventTimestamp"))
            payload = event.get("payload", {})
            messages = payload.get("messages", [])

            print(f"  [{i}] Event: {event_id}")
            print(f"      Time: {timestamp}")
            print(f"      Messages: {len(messages)}")

            # Show message summary
            for msg in messages[:3]:  # Show first 3 messages
                role = msg.get("role", "?")
                text = msg.get("content", {}).get("text", "")[:80]
                if len(msg.get("content", {}).get("text", "")) > 80:
                    text += "..."
                print(f"        - [{role}] {text}")
            if len(messages) > 3:
                print(f"        ... and {len(messages) - 3} more messages")
            print()

    except Exception as e:
        print(f"  Error: {e}")


def explore_branches(client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
    """Explore conversation branches."""
    print_subsection(f"Branches for session: {session_id}")

    try:
        branches = client.list_branches(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id
        )

        if not branches:
            print("  No branches found (main branch only)")
            return

        print(f"  Found {len(branches)} branches\n")
        for branch in branches:
            print(f"  - {branch.get('name', 'unnamed')}")
            print(f"    Root Event: {branch.get('rootEventId', 'N/A')}")

    except Exception as e:
        print(f"  Error: {e}")


def list_memory_records_boto3(region: str, memory_id: str, namespace: str):
    """List memory records using boto3 directly (no semantic search required)."""
    print_subsection(f"Memory Records (boto3) - Namespace: {namespace}")
    
    client = boto3.client("bedrock-agentcore", region_name=region)
    
    try:
        all_records = []
        next_token = None
        
        while True:
            kwargs = {
                "memoryId": memory_id,
                "namespace": namespace,
                "maxResults": 50
            }
            if next_token:
                kwargs["nextToken"] = next_token
                
            response = client.list_memory_records(**kwargs)
            records = response.get("memoryRecordSummaries", [])
            all_records.extend(records)
            
            next_token = response.get("nextToken")
            if not next_token:
                break
        
        if not all_records:
            print("  No memory records found")
            return
            
        print(f"  Found {len(all_records)} memory records\n")
        for i, record in enumerate(all_records, 1):
            record_id = record.get("memoryRecordId", "N/A")
            content = record.get("content", {})
            text = content.get("text", str(content))[:5000]
            if len(str(content.get("text", content))) > 5000:
                text += "..."
            created = format_timestamp(record.get("createdAt"))
            strategy_id = record.get("memoryStrategyId", "N/A")
            
            print(f"  [{i}] ID: {record_id}")
            print(f"      Strategy: {strategy_id}")
            print(f"      Created: {created}")
            print(f"      Content: {text}")
            if record.get("metadata"):
                print(f"      Metadata: {record.get('metadata')}")
            print()
            
    except Exception as e:
        print(f"  Error: {e}")


def get_strategy_ids(client: MemoryClient, memory_id: str) -> list[str]:
    """Get memory strategy IDs from the memory configuration."""
    try:
        strategies = client.get_memory_strategies(memory_id)
        strategy_ids = []
        for strategy in strategies:
            strategy_id = strategy.get("strategyId") or strategy.get("memoryStrategyId")
            if strategy_id:
                strategy_ids.append(strategy_id)
        return strategy_ids
    except Exception as e:
        print(f"  Warning: Could not fetch strategy IDs: {e}")
        return []


def explore_extracted_memories(client: MemoryClient, memory_id: str, actor_id: str, region: str):
    """Explore extracted long-term memories (episodes and reflections)."""
    print_section(f"EXTRACTED MEMORIES for actor: {actor_id}")

    strategy_ids = get_strategy_ids(client, memory_id)
    print(f"Found strategy IDs: {strategy_ids}")
    
    namespaces_to_try = []
    for strategy_id in strategy_ids:
        namespaces_to_try.append(f"/strategies/{strategy_id}/actors/{actor_id}")

    for namespace in namespaces_to_try:
        list_memory_records_boto3(region, memory_id, namespace)


def explore_recent_turns(client: MemoryClient, memory_id: str, actor_id: str, session_id: str):
    """Get the last K conversation turns."""
    print_subsection(f"Recent turns for session: {session_id}")

    try:
        turns = client.get_last_k_turns(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=5
        )

        if not turns:
            print("  No recent turns found")
            return

        print(f"  Found {len(turns)} recent turns\n")
        for i, turn in enumerate(turns, 1):
            print(f"  [Turn {i}]")
            for msg in turn:
                role = msg.get("role", "?")
                text = msg.get("content", {}).get("text", "")[:100]
                if len(msg.get("content", {}).get("text", "")) > 100:
                    text += "..."
                print(f"    [{role}] {text}")
            print()

    except Exception as e:
        print(f"  Error: {e}")


def discover_sessions(client: MemoryClient, memory_id: str, actor_id: str) -> list[str]:
    """Try to discover session IDs by listing events with common patterns."""
    # For episodic memory, sessions are usually timestamped
    # We can't easily enumerate them without knowing the pattern
    # Return common test patterns
    return [
        f"checkin-{datetime.now().strftime('%Y%m%d')}",  # Today's session
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Explore AgentCore memory contents"
    )
    parser.add_argument(
        "--memory-id",
        default=os.getenv("AGENTCORE_MEMORY_ID"),
        help="Memory ID (or set AGENTCORE_MEMORY_ID env var)",
    )
    parser.add_argument(
        "--actor-id",
        help="Actor ID to explore (e.g., 'globalair-com')",
    )
    parser.add_argument(
        "--session-id",
        help="Specific session ID to explore",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-west-2"),
        help="AWS region (default: us-west-2)",
    )
    parser.add_argument(
        "--list-all",
        action="store_true",
        help="List all memories in the account",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AgentCore Memory Explorer")
    print("=" * 60)
    print(f"Region: {args.region}")

    client = MemoryClient(region_name=args.region)

    # List all memories if requested or if no memory ID provided
    if args.list_all or not args.memory_id:
        print_section("ALL MEMORIES IN ACCOUNT")
        try:
            memories = client.list_memories(max_results=50)
            if memories:
                for mem in memories:
                    print(f"\n  ID:     {mem.get('id')}")
                    print(f"  Name:   {mem.get('name', 'N/A')}")
                    print(f"  Status: {mem.get('status', 'N/A')}")
                    print(f"  ARN:    {mem.get('arn', 'N/A')}")
            else:
                print("  No memories found in this account/region")

            if not args.memory_id and memories:
                print("\n\nTip: Run with --memory-id <ID> to explore a specific memory")
                print("     Run with --memory-id <ID> --actor-id <ACTOR> for detailed exploration")
        except Exception as e:
            print(f"  Error listing memories: {e}")

        if not args.memory_id:
            return

    memory_id = args.memory_id
    print(f"\nExploring Memory: {memory_id}")

    # Show memory info and strategies
    explore_memory_info(client, memory_id)

    # If actor ID provided, explore in detail
    if args.actor_id:
        actor_id = args.actor_id

        # Explore extracted memories (long-term)
        explore_extracted_memories(client, memory_id, actor_id, args.region)

        # If session ID provided, explore events
        if args.session_id:
            session_id = args.session_id

            print_section(f"SESSION DETAILS: {session_id}")

            # Events (short-term memory)
            explore_events(client, memory_id, actor_id, session_id)

            # Branches
            explore_branches(client, memory_id, actor_id, session_id)

            # Recent turns
            explore_recent_turns(client, memory_id, actor_id, session_id)
        else:
            print("\n\nTip: Add --session-id <SESSION> to explore specific session events")
            print("     Session IDs are typically like 'checkin-20241219120000'")
    else:
        print("\n\nTip: Add --actor-id <ACTOR> to explore actor-specific data")
        print("     For this project, actor IDs are URL slugs like 'globalair-com'")


if __name__ == "__main__":
    main()
