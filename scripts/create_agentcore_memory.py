#!/usr/bin/env python3
"""One-time setup script to create AgentCore memory store.

Run this once, then add the output to your .env file.
Includes rollback logic to clean up resources on failure.

Usage:
    python scripts/create_agentcore_memory.py [--region REGION]
    python scripts/create_agentcore_memory.py --clean  # Remove all resources

Example:
    python scripts/create_agentcore_memory.py --region us-east-1

Supported regions for AgentCore Memory (as of 2025):
    - us-east-1 (N. Virginia)
    - us-west-2 (Oregon)
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager

import boto3
from bedrock_agentcore.memory import MemoryClient


MEMORY_NAME = "AirlineCheckinAgentMemory"
ROLE_NAME = "AgentCoreMemoryExecutionRole"

# AgentCore Memory is only available in specific regions
SUPPORTED_REGIONS = ["us-east-1", "us-west-2"]


@dataclass
class DeploymentState:
    """Tracks resources created during deployment for rollback purposes."""
    iam_role_created: bool = False
    iam_policy_created: bool = False
    memory_created: bool = False
    memory_id: Optional[str] = None
    errors: list = field(default_factory=list)

    def record_error(self, step: str, error: Exception):
        """Record an error that occurred during deployment."""
        self.errors.append({"step": step, "error": str(error), "type": type(error).__name__})


class DeploymentRollback:
    """Handles rollback of resources created during a failed deployment."""

    def __init__(self, state: DeploymentState, region: str):
        self.state = state
        self.region = region
        self.iam = boto3.client("iam")

    def rollback(self):
        """Roll back all resources created during this deployment."""
        print("\n" + "=" * 60)
        print("DEPLOYMENT FAILED - INITIATING ROLLBACK")
        print("=" * 60)

        rollback_errors = []

        # Rollback in reverse order of creation

        # 1. Delete memory if created
        if self.state.memory_created and self.state.memory_id:
            try:
                print(f"Rolling back: Deleting memory {self.state.memory_id}...")
                delete_memory(self.region, self.state.memory_id)
                print(f"  ✓ Deleted memory")
            except Exception as e:
                rollback_errors.append(f"Failed to delete memory: {e}")
                print(f"  ✗ Failed to delete memory: {e}")

        # 2. Delete IAM policy if created
        if self.state.iam_policy_created:
            try:
                print(f"Rolling back: Deleting IAM policy from role {ROLE_NAME}...")
                self.iam.delete_role_policy(
                    RoleName=ROLE_NAME,
                    PolicyName=f"{ROLE_NAME}-policy"
                )
                print(f"  ✓ Deleted IAM policy")
            except Exception as e:
                rollback_errors.append(f"Failed to delete IAM policy: {e}")
                print(f"  ✗ Failed to delete IAM policy: {e}")

        # 3. Delete IAM role if created
        if self.state.iam_role_created:
            try:
                print(f"Rolling back: Deleting IAM role {ROLE_NAME}...")
                # Must delete all inline policies first
                try:
                    self.iam.delete_role_policy(
                        RoleName=ROLE_NAME,
                        PolicyName=f"{ROLE_NAME}-policy"
                    )
                except Exception:
                    pass  # Policy may already be deleted
                self.iam.delete_role(RoleName=ROLE_NAME)
                print(f"  ✓ Deleted IAM role")
            except Exception as e:
                rollback_errors.append(f"Failed to delete IAM role: {e}")
                print(f"  ✗ Failed to delete IAM role: {e}")

        print("\n" + "-" * 60)
        if rollback_errors:
            print("ROLLBACK COMPLETED WITH ERRORS:")
            for err in rollback_errors:
                print(f"  - {err}")
        else:
            print("ROLLBACK COMPLETED SUCCESSFULLY")
        print("-" * 60)

        return rollback_errors


@contextmanager
def deployment_context(region: str):
    """Context manager for deployment with automatic rollback on failure."""
    state = DeploymentState()
    try:
        yield state
    except Exception as e:
        state.record_error("deployment", e)
        rollback = DeploymentRollback(state, region)
        rollback.rollback()
        raise
    finally:
        if state.errors:
            print("\nDeployment errors encountered:")
            for err in state.errors:
                print(f"  [{err['step']}] {err['type']}: {err['error']}")


def create_memory_execution_role(region: str, state: Optional[DeploymentState] = None) -> str:
    """Create IAM role for AgentCore Memory with Bedrock model invocation permissions."""
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    
    # Trust policy - allow AgentCore to assume this role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # Permissions for custom memory strategies
    # Based on: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-self-managed-strategies.html
    execution_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            }
        ]
    }
    
    role_arn = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"
    
    # Check if role exists
    try:
        iam.get_role(RoleName=ROLE_NAME)
        print(f"IAM role exists: {ROLE_NAME}")
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        pass
    
    # Create role
    print(f"Creating IAM role: {ROLE_NAME}")
    iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Execution role for AgentCore Memory custom strategies"
    )
    if state:
        state.iam_role_created = True

    # Attach inline policy
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=f"{ROLE_NAME}-policy",
        PolicyDocument=json.dumps(execution_policy)
    )
    if state:
        state.iam_policy_created = True

    # Wait for role AND trust policy to propagate
    # IAM eventual consistency requires ~10-30 seconds for cross-service trust relationships
    print("Waiting for IAM role and trust policy to propagate...")

    # First, verify role exists
    max_attempts = 5
    base_delay = 2
    for attempt in range(max_attempts):
        delay = base_delay * (2 ** attempt)  # 2, 4, 8, 16, 32 seconds
        time.sleep(delay)
        try:
            iam.get_role(RoleName=ROLE_NAME)
            print(f"IAM role exists after {delay}s")
            break
        except Exception:
            if attempt < max_attempts - 1:
                print(f"Role not ready, retrying in {base_delay * (2 ** (attempt + 1))}s...")
            else:
                print("Role created, proceeding...")

    # Additional wait for trust policy propagation (cross-service assume-role)
    # This is critical - get_role succeeding doesn't mean the trust policy is propagated
    propagation_wait = 15
    print(f"Waiting {propagation_wait}s for trust policy propagation...")
    time.sleep(propagation_wait)
    print("Trust policy propagation wait complete")

    return role_arn


def delete_memory(region: str, memory_id: str) -> None:
    """Delete an existing AgentCore memory store and wait for completion."""
    from bedrock_agentcore.memory import MemoryClient
    
    client = MemoryClient(region_name=region)
    boto_client = boto3.client("bedrock-agentcore-control", region_name=region)
    print(f"Deleting memory {memory_id}...")
    
    try:
        client.delete_memory(memory_id=memory_id)
        print("Waiting for deletion to complete", end="", flush=True)
        
        # Poll until memory is fully deleted with exponential backoff
        max_attempts = 10
        base_delay = 2
        for attempt in range(max_attempts):
            delay = min(base_delay * (2 ** attempt), 30)  # Cap at 30 seconds
            time.sleep(delay)
            print(".", end="", flush=True)
            try:
                response = boto_client.get_memory(memoryId=memory_id)
                status = response.get("memory", {}).get("status", "")
                if status not in ("DELETING", "ACTIVE"):
                    break
            except boto_client.exceptions.ResourceNotFoundException:
                break
            except Exception as e:
                if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                    break
        
        print()
        print(f"✓ Memory {memory_id} deleted")
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            print(f"Memory {memory_id} already deleted or does not exist")
        else:
            raise


def create_memory(region: str, force: bool = False, state: Optional[DeploymentState] = None) -> dict:
    """Create the AgentCore memory store with episodic strategy."""
    if region not in SUPPORTED_REGIONS:
        print(f"⚠ Warning: Region '{region}' may not support AgentCore Memory.")
        print(f"  Supported regions: {', '.join(SUPPORTED_REGIONS)}")
        print()

    # Create IAM role for memory execution
    role_arn = create_memory_execution_role(region, state)
    print(f"Using execution role: {role_arn}")
    print()
    
    client = MemoryClient(region_name=region)
    boto_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Check if memory already exists
    print(f"Checking for existing memory '{MEMORY_NAME}' in {region}...")
    try:
        memories = client.list_memories(max_results=50)
        for memory_summary in memories:
            memory_id = memory_summary.get("id")
            if memory_id:
                detail = boto_client.get_memory(memoryId=memory_id).get("memory", {})
                if detail.get("name") == MEMORY_NAME:
                    if force:
                        print(f"\n⚠ Memory exists, --force specified, deleting...")
                        delete_memory(region, memory_id)
                        break
                    else:
                        print(f"\n✓ Memory already exists!")
                        return {
                            "id": memory_id,
                            "arn": detail.get("arn"),
                            "name": detail.get("name"),
                            "status": detail.get("status"),
                        }
    except Exception as e:
        print(f"Warning: Could not check existing memories: {e}")

    # Create new memory with custom extraction instructions
    print(f"Creating new memory '{MEMORY_NAME}' with custom extraction...")
    
    try:
        extraction_prompt = """
# IMPORTANT: Extract Aggressively

You MUST extract a summary for EVERY conversation turn, even if it seems routine or unsuccessful.
Do NOT skip turns. Do NOT filter out "unimportant" interactions.
Every tool call, every navigation, every form interaction is valuable for learning.

# Domain Context: Airline Check-in Automation (Single Website Focus)

NOTE: Memory is segmented per website. All extracted data will only be used for future 
check-ins on THIS SAME WEBSITE. Focus on patterns specific to this site.

## ALWAYS Extract (be generous):
- ALL tool calls and their outcomes (success or failure)
- ALL navigation actions and page transitions
- ALL element interactions (clicks, fills, selections)
- ALL error messages and how they were handled
- ALL wait/timing patterns used
- This website's structure: URLs, button labels, form fields, selectors
- This website's UI patterns, quirks, and flows
- This site's seat map layout and selection mechanism
- Any workarounds or alternative approaches attempted on this site

## Redact Only (replace with generic placeholders):
- Passenger names → "[PASSENGER]"
- Email addresses → "[EMAIL]"
- Phone numbers → "[PHONE]"
- Booking/confirmation codes → "[BOOKING_REF]"
- Passport numbers → "[PASSPORT]"
- Payment details → "[PAYMENT]"

## Key Principle:
When in doubt, INCLUDE the information. More context is better for learning.
Failed attempts are just as valuable as successes for building automation knowledge.
Focus on what works (or doesn't) specifically on THIS website.
"""

        consolidation_prompt = """
# Domain-Specific Consolidation Guidance for Airline Check-in Automation

NOTE: Memory is segmented per website (actor). Episodes are consolidated WITHIN a single 
website's context. Focus on patterns that will help future check-ins on THIS SAME SITE.

## Content Exclusions (Do NOT include):
- Any passenger PII or booking-specific details
- Individual flight information or dates

## Focus Areas for Episode Consolidation:

### For <situation> field:
- Describe this website's check-in flow type (e.g., "SkyWings demo multi-step check-in with seat selection")
- Note the technical context (browser automation, form filling, navigation)
- Reference the specific website/URL being automated

### For <intent> field:
- Generalize to reusable patterns (e.g., "complete online check-in" not "check in John's flight")

### For <reflection> field:
- Emphasize tool effectiveness patterns FOR THIS WEBSITE
- Document successful element selectors and DOM patterns that work on this site
- Note timing/wait strategies that worked here
- Capture error recovery approaches specific to this site's behavior
- Highlight this website's quirks (e.g., "requires cookie acceptance before form access")

Prioritize insights transferable to future check-ins ON THIS SAME WEBSITE across different sessions.
"""

        reflection_prompt = """
# Domain-Specific Reflection Guidance for Airline Check-in Automation

NOTE: Reflections are scoped to a SINGLE WEBSITE (actor). All patterns identified here 
will only be retrieved for future check-ins on THIS SAME WEBSITE. Do not reference 
other airlines or websites - focus exclusively on patterns for this specific site.

## Pattern Categories to Identify:

### Tool Effectiveness Patterns (for this website):
- Which browser automation tools work best for specific actions on this site
- Parameter combinations that succeed here (e.g., "click with force=true for modal overlays")
- Tool sequences that reliably complete this site's multi-step flows

### Website-Specific Patterns:
- Navigation flows unique to THIS website
- Form field requirements and validation behaviors on this site
- This site's seat map interaction patterns
- Error message patterns and recovery strategies specific to this site
- UI quirks, timing requirements, and workarounds discovered

### Technical Patterns (verified on this site):
- DOM selector strategies that work reliably on this site
- Wait/timing strategies for this site's dynamic content
- Accessibility tree patterns for reliable element location here
- iframe handling and popup management specific to this site

## Reflection Quality Guidelines:
- Title should reference THIS WEBSITE and the pattern type (e.g., "SkyWings Seat Selection Flow")
- Use cases should describe when this pattern applies on this website
- Hints should be actionable for future automation attempts on this same site
- Higher confidence for patterns verified across multiple sessions on this website

Exclude any passenger-specific information from reflections.
"""
    
        memory = client.create_memory_and_wait(
            name=MEMORY_NAME,
            description="Episodic memory for airline check-in automation learnings",
            memory_execution_role_arn=role_arn,
            strategies=[
                {
                    "customMemoryStrategy": {
                        "name": "CheckinLearnings",
                        "namespaces": ["/strategies/{memoryStrategyId}/actors/{actorId}/sessions/{sessionId}"],
                        "configuration": {
                            "episodicOverride": {
                                "extraction": {
                                    "appendToPrompt": extraction_prompt,
                                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0"
                                },
                                "consolidation": {
                                    "appendToPrompt": consolidation_prompt,
                                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0"
                                },
                                "reflection": {
                                    "appendToPrompt": reflection_prompt,
                                    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                                    "namespaces" : ["/strategies/{memoryStrategyId}/actors/{actorId}"]
                                }
                            }
                        }
                    }
                }
            ],
        )

        if state:
            state.memory_created = True
            state.memory_id = memory.get("id")

        return {
            "id": memory.get("id"),
            "arn": memory.get("arn"),
            "name": memory.get("name"),
            "status": memory.get("status"),
        }
    
    except Exception as e:
        error_msg = str(e).lower()
        # If memory already exists, try to find and return it
        if "already exists" in error_msg or "duplicate" in error_msg:
            print(f"\n⚠ Memory already exists, searching for it...")
            try:
                # Use boto3 client directly to list all memories
                gmcp = boto3.client("bedrock-agentcore-control", region_name=region)
                
                # List all memories and find ours
                paginator = gmcp.get_paginator("list_memories")
                for page in paginator.paginate():
                    for memory_summary in page.get("memories", []):
                        memory_id = memory_summary.get("id")
                        if memory_id:
                            # Get full memory details
                            detail = gmcp.get_memory(memoryId=memory_id)
                            memory_detail = detail.get("memory", {})
                            if memory_detail.get("name") == MEMORY_NAME:
                                print(f"✓ Found existing memory!")
                                return {
                                    "id": memory_id,
                                    "arn": memory_detail.get("arn"),
                                    "name": memory_detail.get("name"),
                                    "status": memory_detail.get("status"),
                                }
                
                raise RuntimeError(f"Memory '{MEMORY_NAME}' exists but could not be retrieved")
            except Exception as list_error:
                raise RuntimeError(f"Memory exists but could not be found: {list_error}") from e
        raise


def cleanup_resources(region: str) -> bool:
    """Clean up all deployed AgentCore memory resources."""
    print("=" * 60)
    print("CLEANUP: Removing AgentCore Memory resources")
    print("=" * 60)

    iam = boto3.client("iam")
    errors = []

    # 1. Find and delete the memory
    print(f"\n1. Finding and deleting memory: {MEMORY_NAME}")
    try:
        client = MemoryClient(region_name=region)
        boto_client = boto3.client("bedrock-agentcore-control", region_name=region)

        memories = client.list_memories(max_results=50)
        memory_found = False
        for memory_summary in memories:
            memory_id = memory_summary.get("id")
            if memory_id:
                detail = boto_client.get_memory(memoryId=memory_id).get("memory", {})
                if detail.get("name") == MEMORY_NAME:
                    memory_found = True
                    print(f"   Found memory: {memory_id}")
                    delete_memory(region, memory_id)
                    print(f"   ✓ Deleted memory")
                    break

        if not memory_found:
            print(f"   Memory not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete memory: {e}")
        print(f"   ✗ Error: {e}")

    # 2. Delete IAM role policy
    print(f"\n2. Deleting IAM role policy: {ROLE_NAME}-policy")
    try:
        iam.delete_role_policy(
            RoleName=ROLE_NAME,
            PolicyName=f"{ROLE_NAME}-policy"
        )
        print(f"   ✓ Deleted IAM role policy")
    except iam.exceptions.NoSuchEntityException:
        print(f"   Policy not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete IAM policy: {e}")
        print(f"   ✗ Error: {e}")

    # 3. Delete IAM role
    print(f"\n3. Deleting IAM role: {ROLE_NAME}")
    try:
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"   ✓ Deleted IAM role")
    except iam.exceptions.NoSuchEntityException:
        print(f"   Role not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete IAM role: {e}")
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 60)
    if errors:
        print("CLEANUP COMPLETED WITH ERRORS:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("CLEANUP COMPLETED SUCCESSFULLY")
    print("=" * 60)

    return len(errors) == 0


def deploy_memory(region: str, force: bool = False) -> dict:
    """Deploy the memory with rollback on failure."""
    print("=" * 60)
    print("AgentCore Memory Setup")
    print("=" * 60)

    with deployment_context(region) as state:
        result = create_memory(region, force=force, state=state)

        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nMemory ID:  {result['id']}")
        print(f"ARN:        {result['arn']}")
        print(f"Status:     {result['status']}")

        print("\n" + "-" * 60)
        print("Add this to your .env file:")
        print("-" * 60)
        print(f"\nAGENTCORE_MEMORY_ID={result['id']}")

        print("\n" + "-" * 60)
        print("Or export directly:")
        print("-" * 60)
        print(f"\nexport AGENTCORE_MEMORY_ID={result['id']}")
        print()

        return result


def main():
    """Main entry point with command-line argument handling."""
    parser = argparse.ArgumentParser(
        description="Create or clean up AgentCore Memory resources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/create_agentcore_memory.py                  # Create memory
  python scripts/create_agentcore_memory.py --force          # Recreate memory
  python scripts/create_agentcore_memory.py --clean          # Remove all resources
  python scripts/create_agentcore_memory.py --region us-east-1  # Specify region
        """
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and recreate memory if it already exists",
    )
    parser.add_argument(
        "--clean", "--cleanup",
        action="store_true",
        dest="cleanup",
        help="Remove all deployed AgentCore Memory resources (IAM role, memory)"
    )
    args = parser.parse_args()

    if args.cleanup:
        success = cleanup_resources(args.region)
        sys.exit(0 if success else 1)
    else:
        try:
            deploy_memory(args.region, force=args.force)
        except Exception as e:
            print(f"\nDeployment failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
