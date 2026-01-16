"""Deploy agent to Amazon Bedrock AgentCore using boto3.

Creates/retrieves memory, IAM role, ECR repository, builds/pushes Docker image, and deploys to AgentCore.
Includes rollback logic to clean up resources on deployment failure.
"""
import base64
import boto3
import json
import subprocess
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager

# Configuration
REGION = os.getenv("AWS_REGION", "us-west-2")
AGENT_NAME = "airline_checkin_agent"
ECR_REPO_NAME = "airline-checkin-agent"  # ECR allows hyphens
ROLE_NAME = f"AgentCoreExecutionRole_{AGENT_NAME}"


@dataclass
class DeploymentState:
    """Tracks resources created during deployment for rollback purposes."""
    iam_role_created: bool = False
    iam_policy_created: bool = False
    ecr_repo_created: bool = False
    agent_runtime_created: bool = False
    agent_runtime_id: Optional[str] = None
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
        self.ecr = boto3.client("ecr", region_name=region)
        self.agentcore = boto3.client("bedrock-agentcore-control", region_name=region)

    def rollback(self):
        """Roll back all resources created during this deployment."""
        print("\n" + "=" * 60)
        print("DEPLOYMENT FAILED - INITIATING ROLLBACK")
        print("=" * 60)

        rollback_errors = []

        # Rollback in reverse order of creation

        # 1. Delete agent runtime if created
        if self.state.agent_runtime_created and self.state.agent_runtime_id:
            try:
                print(f"Rolling back: Deleting agent runtime {self.state.agent_runtime_id}...")
                self.agentcore.delete_agent_runtime(agentRuntimeId=self.state.agent_runtime_id)
                print(f"  ✓ Deleted agent runtime")
            except Exception as e:
                rollback_errors.append(f"Failed to delete agent runtime: {e}")
                print(f"  ✗ Failed to delete agent runtime: {e}")

        # 2. Delete ECR repository if created (only if empty)
        if self.state.ecr_repo_created:
            try:
                print(f"Rolling back: Deleting ECR repository {ECR_REPO_NAME}...")
                # Only delete if we created it and it's empty or has only the image we pushed
                self.ecr.delete_repository(repositoryName=ECR_REPO_NAME, force=True)
                print(f"  ✓ Deleted ECR repository")
            except Exception as e:
                rollback_errors.append(f"Failed to delete ECR repository: {e}")
                print(f"  ✗ Failed to delete ECR repository: {e}")

        # 3. Delete IAM policy if created
        if self.state.iam_policy_created:
            try:
                print(f"Rolling back: Deleting IAM policy from role {ROLE_NAME}...")
                self.iam.delete_role_policy(
                    RoleName=ROLE_NAME,
                    PolicyName=f"{AGENT_NAME}-execution-policy"
                )
                print(f"  ✓ Deleted IAM policy")
            except Exception as e:
                rollback_errors.append(f"Failed to delete IAM policy: {e}")
                print(f"  ✗ Failed to delete IAM policy: {e}")

        # 4. Delete IAM role if created
        if self.state.iam_role_created:
            try:
                print(f"Rolling back: Deleting IAM role {ROLE_NAME}...")
                # Must delete all inline policies first
                try:
                    self.iam.delete_role_policy(
                        RoleName=ROLE_NAME,
                        PolicyName=f"{AGENT_NAME}-execution-policy"
                    )
                except Exception:
                    pass  # Policy may already be deleted
                self.iam.delete_role(RoleName=ROLE_NAME)
                print(f"  ✓ Deleted IAM role")
            except Exception as e:
                rollback_errors.append(f"Failed to delete IAM role: {e}")
                print(f"  ✗ Failed to delete IAM role: {e}")

        # Note: We don't rollback memory as it's a valuable resource that should persist
        if self.state.memory_created and self.state.memory_id:
            print(f"\nNote: AgentCore Memory {self.state.memory_id} was created and preserved.")
            print("  Memory resources are retained as they may contain valuable data.")

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


def create_or_update_iam_role(iam, account_id: str, state: Optional[DeploymentState] = None) -> str:
    """Create or update IAM role for AgentCore with required permissions."""

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

    # Execution policy based on AWS documentation
    # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html
    execution_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ECRAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": f"arn:aws:logs:{REGION}:{account_id}:log-group:/aws/bedrock-agentcore/*"
            },
            {
                "Sid": "XRayTracing",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords"
                ],
                "Resource": "*"
            },
            {
                "Sid": "CloudWatchMetrics",
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "AWS/BedrockAgentCore"
                    }
                }
            },
            {
                "Sid": "WorkloadIdentity",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForEntityOwner"
                ],
                "Resource": "*"
            },
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            },
            {
                "Sid": "AgentCoreMemoryAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:RetrieveEvents"
                ],
                "Resource": f"arn:aws:bedrock-agentcore:{REGION}:{account_id}:memory/*"
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue"
                ],
                "Resource": f"arn:aws:secretsmanager:{REGION}:{account_id}:secret:airline-demo/*"
            },
            {
                "Sid": "AgentCoreBrowserAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:StartBrowserSession",
                    "bedrock-agentcore:StopBrowserSession",
                    "bedrock-agentcore:GetBrowserSession",
                    "bedrock-agentcore:UpdateBrowserStream",
                    "bedrock-agentcore:ConnectBrowserAutomationStream",
                    "bedrock-agentcore:ConnectBrowserLiveViewStream",
                    "bedrock-agentcore:ListBrowserSessions"
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
        print(f"Updating IAM role policy...")
        
        # Update inline policy with latest permissions
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName=f"{AGENT_NAME}-execution-policy",
            PolicyDocument=json.dumps(execution_policy)
        )
        print(f"Updated IAM role policy with latest permissions")
        return role_arn
        
    except iam.exceptions.NoSuchEntityException:
        pass

    # Create role
    print(f"Creating IAM role: {ROLE_NAME}")
    iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description=f"Execution role for AgentCore agent: {AGENT_NAME}"
    )
    if state:
        state.iam_role_created = True

    # Attach inline policy
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=f"{AGENT_NAME}-execution-policy",
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


def check_image_scan_results(ecr_client, repo_name: str, image_tag: str = "latest") -> bool:
    """Check ECR image scan results and report vulnerabilities."""
    print(f"Checking image scan results for {repo_name}:{image_tag}...")

    # Wait for scan to complete (max 60 seconds)
    max_wait = 60
    wait_interval = 5
    elapsed = 0

    while elapsed < max_wait:
        try:
            response = ecr_client.describe_image_scan_findings(
                repositoryName=repo_name,
                imageId={"imageTag": image_tag}
            )
            status = response.get("imageScanStatus", {}).get("status", "")

            if status == "COMPLETE":
                findings = response.get("imageScanFindings", {})
                counts = findings.get("findingSeverityCounts", {})

                critical = counts.get("CRITICAL", 0)
                high = counts.get("HIGH", 0)
                medium = counts.get("MEDIUM", 0)
                low = counts.get("LOW", 0)

                print(f"Scan complete - Vulnerabilities: CRITICAL={critical}, HIGH={high}, MEDIUM={medium}, LOW={low}")

                if critical > 0 or high > 0:
                    print(f"  ⚠ WARNING: {critical + high} critical/high severity vulnerabilities found")
                    print(f"  Review findings in ECR console before deploying to production")
                    return False
                return True

            elif status == "FAILED":
                print(f"  Scan failed: {response.get('imageScanStatus', {}).get('description', 'Unknown error')}")
                return False

            # Still in progress
            time.sleep(wait_interval)
            elapsed += wait_interval

        except ecr_client.exceptions.ScanNotFoundException:
            # Scan not started yet, wait
            time.sleep(wait_interval)
            elapsed += wait_interval
        except Exception as e:
            print(f"  Could not retrieve scan results: {e}")
            return True  # Don't block deployment on scan check errors

    print(f"  Scan still in progress after {max_wait}s, continuing deployment...")
    return True


def get_or_create_memory(region: str, state: Optional[DeploymentState] = None) -> str:
    """Get existing or create new AgentCore memory."""
    print("Checking AgentCore Memory...")

    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    if memory_id:
        print(f"Using existing memory ID from env: {memory_id}")
        return memory_id

    # Run create_agentcore_memory.py script
    print("No AGENTCORE_MEMORY_ID found, creating new memory...")
    script_path = os.path.join(os.path.dirname(__file__), "scripts", "create_agentcore_memory.py")

    try:
        # Using list of arguments (not shell=True) prevents command injection
        result = subprocess.run(  # nosec B602 - Safe: using list args with controlled internal paths, no shell=True
            [sys.executable, script_path, "--region", region],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse memory ID from output
        for line in result.stdout.split('\n'):
            if "Memory ID:" in line:
                memory_id = line.split("Memory ID:")[-1].strip()
                print(f"Created new memory: {memory_id}")
                if state:
                    state.memory_created = True
                    state.memory_id = memory_id
                return memory_id

        raise RuntimeError("Could not parse memory ID from create script output")

    except subprocess.CalledProcessError as e:
        print(f"Error creating memory: {e.stderr}")
        raise


def get_or_update_agent_runtime(
    agentcore, account_id: str, ecr_uri: str, role_arn: str, memory_id: str,
    state: Optional[DeploymentState] = None
) -> str:
    """Get existing or create/update AgentCore runtime."""

    try:
        response = agentcore.list_agent_runtimes(maxResults=100)
        runtimes = response.get("agentRuntimes", [])
        
        for runtime in runtimes:
            runtime_arn = runtime.get("agentRuntimeArn")
            runtime_id = runtime.get("agentRuntimeId")
            runtime_name = runtime.get("agentRuntimeName")
            print(f"Existing runtime: {runtime_name} / {runtime_id}")            
            if runtime_name == AGENT_NAME:                
                print(f"Agent runtime exists: {AGENT_NAME}")
                print(f"Updating existing runtime: {runtime_id}")
                
                env_vars = {
                    "AGENTCORE_MEMORY_ID": memory_id,
                    "AGENTCORE_MEMORY_ENABLED": "true",
                    "AGENT_OBSERVABILITY_ENABLED": "true",
                    "OTEL_PYTHON_DISTRO": "aws_distro",
                    "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                    "OTEL_RESOURCE_ATTRIBUTES": f"service.name={AGENT_NAME}",
                    "CLOUDFRONT_KEY_PAIR_ID": os.getenv("CLOUDFRONT_KEY_PAIR_ID", ""),
                    "CLOUDFRONT_SECRET_NAME": os.getenv("CLOUDFRONT_SECRET_NAME", "airline-demo/cloudfront-private-key"),
                    "BROWSER_TYPE":"agentcore"
                }
                
                agentcore.update_agent_runtime(
                    agentRuntimeId=runtime_id,
                    agentRuntimeArtifact={
                        "containerConfiguration": {"containerUri": ecr_uri}
                    },
                    networkConfiguration={"networkMode": "PUBLIC"},
                    roleArn=role_arn,
                    environmentVariables=env_vars
                )
                print(f"Updated agent runtime with new image and memory config")
                return runtime_arn
    except Exception as e:
        print(f"Error checking for existing runtime: {e}")
    
    print(f"Creating new AgentCore runtime: {AGENT_NAME}")
    print(f"Configuring with AgentCore Memory ID: {memory_id}")
    
    env_vars = {
        "AGENTCORE_MEMORY_ID": memory_id,
        "AGENTCORE_MEMORY_ENABLED": "true",
        "AGENT_OBSERVABILITY_ENABLED": "true",
        "OTEL_PYTHON_DISTRO": "aws_distro",
        "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_RESOURCE_ATTRIBUTES": f"service.name={AGENT_NAME}",
        "CLOUDFRONT_KEY_PAIR_ID": os.getenv("CLOUDFRONT_KEY_PAIR_ID", ""),
        "CLOUDFRONT_SECRET_NAME": os.getenv("CLOUDFRONT_SECRET_NAME", "airline-demo/cloudfront-private-key"),
        "BROWSER_TYPE":"agentcore"
    }
    
    response = agentcore.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        agentRuntimeArtifact={
            "containerConfiguration": {"containerUri": ecr_uri}
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
        environmentVariables=env_vars
    )

    if state:
        state.agent_runtime_created = True
        # Extract runtime ID from ARN
        runtime_arn = response["agentRuntimeArn"]
        state.agent_runtime_id = runtime_arn.split("/")[-1]

    return response["agentRuntimeArn"]


def cleanup_resources(region: str = REGION):
    """Clean up all deployed AgentCore resources."""
    print("=" * 60)
    print("CLEANUP: Removing deployed AgentCore resources")
    print("=" * 60)

    iam = boto3.client("iam")
    ecr = boto3.client("ecr", region_name=region)
    agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    errors = []

    # 1. Delete agent runtime
    print(f"\n1. Deleting agent runtime: {AGENT_NAME}")
    try:
        response = agentcore.list_agent_runtimes(maxResults=100)
        for runtime in response.get("agentRuntimes", []):
            if runtime.get("agentRuntimeName") == AGENT_NAME:
                runtime_id = runtime.get("agentRuntimeId")
                print(f"   Found runtime: {runtime_id}")
                agentcore.delete_agent_runtime(agentRuntimeId=runtime_id)
                print(f"   ✓ Deleted agent runtime")
                break
        else:
            print(f"   Agent runtime not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete agent runtime: {e}")
        print(f"   ✗ Error: {e}")

    # 2. Delete ECR repository
    print(f"\n2. Deleting ECR repository: {ECR_REPO_NAME}")
    try:
        ecr.delete_repository(repositoryName=ECR_REPO_NAME, force=True)
        print(f"   ✓ Deleted ECR repository")
    except ecr.exceptions.RepositoryNotFoundException:
        print(f"   Repository not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete ECR repository: {e}")
        print(f"   ✗ Error: {e}")

    # 3. Delete IAM role policy
    print(f"\n3. Deleting IAM role policy: {AGENT_NAME}-execution-policy")
    try:
        iam.delete_role_policy(
            RoleName=ROLE_NAME,
            PolicyName=f"{AGENT_NAME}-execution-policy"
        )
        print(f"   ✓ Deleted IAM role policy")
    except iam.exceptions.NoSuchEntityException:
        print(f"   Policy not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete IAM policy: {e}")
        print(f"   ✗ Error: {e}")

    # 4. Delete IAM role
    print(f"\n4. Deleting IAM role: {ROLE_NAME}")
    try:
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"   ✓ Deleted IAM role")
    except iam.exceptions.NoSuchEntityException:
        print(f"   Role not found (may already be deleted)")
    except Exception as e:
        errors.append(f"Failed to delete IAM role: {e}")
        print(f"   ✗ Error: {e}")

    # Note about memory
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    if memory_id:
        print(f"\n5. AgentCore Memory: {memory_id}")
        print(f"   ⚠ Memory is preserved (contains learned patterns)")
        print(f"   To delete manually, use the AgentCore console or API")

    print("\n" + "=" * 60)
    if errors:
        print("CLEANUP COMPLETED WITH ERRORS:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("CLEANUP COMPLETED SUCCESSFULLY")
    print("=" * 60)

    return len(errors) == 0


def deploy():
    """Deploy the agent with rollback on failure."""
    iam = boto3.client("iam")
    ecr = boto3.client("ecr", region_name=REGION)
    agentcore = boto3.client("bedrock-agentcore-control", region_name=REGION)

    account_id = boto3.client("sts").get_caller_identity()["Account"]
    print(f"Deploying to account: {account_id}, region: {REGION}")
    print()

    with deployment_context(REGION) as state:
        # 1. Get or create AgentCore memory
        memory_id = get_or_create_memory(REGION, state)
        print()

        # 2. Create IAM role
        role_arn = create_or_update_iam_role(iam, account_id, state)
        print(f"Using IAM role: {role_arn}")
        print()

        # 3. Create ECR repository if not exists (with image scanning enabled)
        try:
            ecr.create_repository(
                repositoryName=ECR_REPO_NAME,
                imageScanningConfiguration={"scanOnPush": True}
            )
            print(f"Created ECR repo: {ECR_REPO_NAME} (scan on push enabled)")
            state.ecr_repo_created = True
        except ecr.exceptions.RepositoryAlreadyExistsException:
            print(f"ECR repo exists: {ECR_REPO_NAME}")
            # Ensure scanning is enabled on existing repo
            ecr.put_image_scanning_configuration(
                repositoryName=ECR_REPO_NAME,
                imageScanningConfiguration={"scanOnPush": True}
            )
            print(f"Enabled scan on push for existing repo")
        print()

        # 4. Build and push Docker image
        ecr_uri = f"{account_id}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPO_NAME}:latest"

        print("Logging into ECR...")
        login_cmd = subprocess.run(
            ["aws", "ecr", "get-login-password", "--region", REGION],
            capture_output=True, text=True, check=True
        )
        subprocess.run(
            ["docker", "login", "--username", "AWS", "--password-stdin",
             f"{account_id}.dkr.ecr.{REGION}.amazonaws.com"],
            input=login_cmd.stdout, text=True, check=True
        )

        print("Building and pushing Docker image...")
        subprocess.run(
            ["docker", "buildx", "build", "--platform", "linux/arm64",
             "-t", ecr_uri, "--push", "."],
            check=True
        )
        print()

        # 4.1. Check image scan results (scan triggered automatically on push)
        check_image_scan_results(ecr, ECR_REPO_NAME, "latest")
        print()

        # 5. Get or update AgentCore runtime
        agent_arn = get_or_update_agent_runtime(
            agentcore, account_id, ecr_uri, role_arn, memory_id, state
        )
        response = {"agentRuntimeArn": agent_arn}

        print("=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print(f"Agent ARN: {response['agentRuntimeArn']}")
        print(f"Memory ID: {memory_id}")
        print(f"ECR Image: {ecr_uri}")
        print(f"IAM Role: {role_arn}")
        print()
        print("Add to your .env files:")
        print(f"AGENT_RUNTIME_ARN={response['agentRuntimeArn']}")
        print(f"AGENTCORE_MEMORY_ID={memory_id}")


def main():
    """Main entry point with command-line argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy or clean up AgentCore resources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy_agentcore.py           # Deploy the agent
  python deploy_agentcore.py --clean   # Remove all deployed resources
  python deploy_agentcore.py --cleanup # Same as --clean
        """
    )
    parser.add_argument(
        "--clean", "--cleanup",
        action="store_true",
        dest="cleanup",
        help="Remove all deployed AgentCore resources (IAM role, ECR repo, agent runtime)"
    )
    parser.add_argument(
        "--region",
        default=REGION,
        help=f"AWS region (default: {REGION})"
    )

    args = parser.parse_args()

    if args.cleanup:
        success = cleanup_resources(args.region)
        sys.exit(0 if success else 1)
    else:
        try:
            deploy()
        except Exception as e:
            print(f"\nDeployment failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
