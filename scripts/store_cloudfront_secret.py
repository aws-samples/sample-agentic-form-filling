"""Store CloudFront private key in AWS Secrets Manager.

Usage:
    python scripts/store_cloudfront_secret.py --key-file ~/.cloudfront/airline-demo-key.pem
    python scripts/store_cloudfront_secret.py --key-file ~/.cloudfront/airline-demo-key.pem --secret-name my-custom-name
"""
import argparse
import boto3
import os
import sys

DEFAULT_SECRET_NAME = "airline-demo/cloudfront-private-key"
REGION = os.getenv("AWS_REGION", "us-west-2")


def store_secret(key_file: str, secret_name: str, region: str) -> str:
    """Store CloudFront private key in Secrets Manager."""
    key_path = os.path.expanduser(key_file)
    if not os.path.isfile(key_path):
        print(f"Error: Key file not found: {key_path}")
        sys.exit(1)

    with open(key_path, "r") as f:
        private_key_pem = f.read()

    if not private_key_pem.startswith("-----BEGIN"):
        print("Error: File does not appear to be a valid PEM file")
        sys.exit(1)

    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.describe_secret(SecretId=secret_name)
        print(f"Secret exists: {secret_name}")
        print("Updating secret value...")
        client.put_secret_value(SecretId=secret_name, SecretString=private_key_pem)
        secret_arn = response["ARN"]
    except client.exceptions.ResourceNotFoundException:
        print(f"Creating new secret: {secret_name}")
        response = client.create_secret(
            Name=secret_name,
            Description="CloudFront private key for airline demo signed cookies",
            SecretString=private_key_pem,
        )
        secret_arn = response["ARN"]

    print(f"Secret ARN: {secret_arn}")
    return secret_arn


def main():
    parser = argparse.ArgumentParser(description="Store CloudFront private key in Secrets Manager")
    parser.add_argument("--key-file", required=True, help="Path to private key PEM file")
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME, help=f"Secret name (default: {DEFAULT_SECRET_NAME})")
    parser.add_argument("--region", default=REGION, help=f"AWS region (default: {REGION})")
    args = parser.parse_args()

    secret_arn = store_secret(args.key_file, args.secret_name, args.region)

    print()
    print("=" * 60)
    print("SECRET STORED SUCCESSFULLY")
    print("=" * 60)
    print()
    print("Add to your .env files:")
    print(f"CLOUDFRONT_SECRET_NAME={args.secret_name}")
    print()
    print("Or use the ARN:")
    print(f"CLOUDFRONT_SECRET_ARN={secret_arn}")


if __name__ == "__main__":
    main()
