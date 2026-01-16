#!/usr/bin/env python3
"""Invoke AgentCore airline check-in agent with streaming support.

Reads configuration from .env files and invokes the deployed AgentCore agent.

Usage:
    python invoke_agent.py --env .env.website1
    python invoke_agent.py --env .env.website2 --prompt "Check in and select seats"
"""
import argparse
import json
import os
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

config = Config(read_timeout=1000)


def build_task_prompt(custom_prompt: str | None = None) -> str:
    """Build task prompt from env vars, similar to agent.py."""
    if custom_prompt:
        return custom_prompt
    
    airline_url = os.getenv("AIRLINE_URL", "")
    login = os.getenv("CHECK_IN_LOGIN", "")
    code = os.getenv("CHECK_IN_CODE", "")
    seat = os.getenv("SEAT_PREFERENCE", "any available")
    
    return f"""Complete airline check-in and download the boarding pass:
URL: {airline_url}
Login: {login} / {code}
Seat: {seat}

Go fast."""


def invoke_agent_streaming(
    agent_arn: str,
    session_id: str,
    prompt: str,
    memory_id: str | None = None,
    airline_id: str | None = None,
    region: str = "us-west-2"
) -> str:
    """Invoke AgentCore agent with streaming response."""
    client = boto3.client("bedrock-agentcore", region_name=region,config=config)
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Check runtime status before invoking
    try:
        # Extract runtime ID from ARN: arn:aws:bedrock-agentcore:region:account:runtime/runtime-id
        runtime_id = agent_arn.split("/")[-1]
        runtime_info = control_client.get_agent_runtime(agentRuntimeId=runtime_id)
        status = runtime_info.get("status", "UNKNOWN")
        print(f"Runtime status: {status}")
        
        if status != "READY":
            print(f"⚠ Warning: Runtime is not READY (status: {status})")
            print("Runtime may not be able to process requests.")
            print()
    except Exception as e:
        print(f"⚠ Warning: Could not check runtime status: {e}")
        print()

    payload_bytes = json.dumps({"input": {"prompt": prompt, "url":f"https://{airline_id}/"}}).encode()

    print(f"Invoking agent: {agent_arn}")
    print(f"Session ID: {session_id}")
    if airline_id:
        print(f"Airline ID (actorId): {airline_id}")
    print(f"Prompt: {prompt}")
    print("-" * 60)

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload_bytes
        )

        stream = response["response"]
        full_response = ""
        for chunk in stream.iter_chunks():
            text = chunk.decode("utf-8")
            print(text, end="", flush=True)
            full_response += text
        print()
        return full_response
    finally:
        print("\nStopping session...")
        try:
            client.stop_runtime_session(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=session_id
            )
            print(f"Session {session_id} stopped successfully")
        except Exception as e:
            print(f"Warning: Failed to stop session: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Invoke AgentCore airline check-in agent"
    )
    parser.add_argument(
        "--env",
        required=True,
        help="Path to .env file (e.g., .env.website1)"
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt (default: builds from env vars like agent.py)"
    )
    parser.add_argument(
        "--session-id",
        help="Session ID (generates new if not provided)"
    )
    parser.add_argument(
        "--agent-arn",
        help="Agent ARN (reads from AGENT_RUNTIME_ARN env var if not provided)"
    )
    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )
    args = parser.parse_args()

    env_path = Path(args.env)
    if not env_path.exists():
        print(f"Error: Environment file not found: {args.env}")
        return 1

    load_dotenv(env_path)

    agent_arn = args.agent_arn or os.getenv("AGENT_RUNTIME_ARN")
    if not agent_arn:
        print("Error: AGENT_RUNTIME_ARN not set in env file or --agent-arn not provided")
        print("\nAdd to your .env file:")
        print("AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:REGION:ACCOUNT:agent-runtime/NAME")
        return 1

    session_id = args.session_id or str(uuid.uuid4())
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    
    airline_url = os.getenv("AIRLINE_URL", "")
    airline_id = None
    if airline_url:
        airline_id = airline_url.rstrip("/").split("/")[-1] or "airline"
        if "localhost" in airline_url:
            port = airline_url.split(":")[-1].rstrip("/")
            airline_id = f"localhost-{port}"

    print("=" * 60)
    print("AgentCore Airline Check-in Agent")
    print("=" * 60)
    print(f"Config file: {args.env}")
    print(f"Airline URL: {os.getenv('AIRLINE_URL')}")
    print(f"Login: {os.getenv('CHECK_IN_LOGIN')}")
    print(f"Code: {os.getenv('CHECK_IN_CODE')}")
    if memory_id:
        print(f"Memory ID: {memory_id}")
    print("=" * 60)
    print()

    prompt = build_task_prompt(args.prompt)

    try:
        result = invoke_agent_streaming(
            agent_arn=agent_arn,
            session_id=session_id,
            prompt=prompt,
            memory_id=memory_id,
            airline_id=airline_id,
            region=args.region
        )
        print("\n" + "=" * 60)
        print("INVOCATION COMPLETE")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
