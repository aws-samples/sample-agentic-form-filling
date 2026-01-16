"""
CloudFront Signed Cookie Generator.

Generates CloudFront signed cookies for authenticating browser access to private S3 content.
"""

import base64
import datetime
import json
import logging
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class CloudFrontSigner:
    """Generate CloudFront signed cookies for private content access."""

    def __init__(
        self,
        key_pair_id: str,
        private_key_pem: str,
    ):
        self.key_pair_id = key_pair_id
        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )

    def _rsa_sign(self, message: bytes) -> bytes:
        """Sign a message with RSA-SHA1 (required by CloudFront)."""
        return self.private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA1(),
        )

    def _base64_encode_url_safe(self, data: bytes) -> str:
        """Encode bytes to URL-safe base64 (CloudFront format)."""
        encoded = base64.b64encode(data).decode("utf-8")
        return encoded.replace("+", "-").replace("=", "_").replace("/", "~")

    def _create_policy(self, resource: str, expires: datetime.datetime) -> str:
        """Create a CloudFront canned policy."""
        policy = {
            "Statement": [
                {
                    "Resource": resource,
                    "Condition": {
                        "DateLessThan": {
                            "AWS:EpochTime": int(expires.timestamp())
                        }
                    },
                }
            ]
        }
        return json.dumps(policy, separators=(",", ":"))

    def generate_signed_cookies(
        self,
        domain: str,
        expires_hours: int = 24,
    ) -> Dict[str, str]:
        """
        Generate CloudFront signed cookies for a domain.

        Args:
            domain: CloudFront distribution domain (e.g., d123456789.cloudfront.net)
            expires_hours: Cookie validity duration in hours

        Returns:
            Dict with CloudFront-Policy, CloudFront-Signature, CloudFront-Key-Pair-Id cookies
        """
        resource = f"https://{domain}/*"
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_hours)

        policy = self._create_policy(resource, expires)
        policy_bytes = policy.encode("utf-8")

        signature = self._rsa_sign(policy_bytes)

        return {
            "CloudFront-Policy": self._base64_encode_url_safe(policy_bytes),
            "CloudFront-Signature": self._base64_encode_url_safe(signature),
            "CloudFront-Key-Pair-Id": self.key_pair_id,
        }

    def get_playwright_cookies(
        self,
        domain: str,
        expires_hours: int = 24,
    ) -> List[Dict]:
        """
        Generate cookies in Playwright format for browser context.

        Args:
            domain: CloudFront distribution domain
            expires_hours: Cookie validity duration in hours

        Returns:
            List of cookie dicts ready for Playwright's context.add_cookies()
        """
        signed_cookies = self.generate_signed_cookies(domain, expires_hours)
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expires_hours)
        expires_timestamp = int(expires.timestamp())

        playwright_cookies = []
        for name, value in signed_cookies.items():
            playwright_cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "expires": expires_timestamp,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            })

        return playwright_cookies


def get_private_key_from_secrets_manager(secret_name: str, region: str = None) -> Optional[str]:
    """
    Retrieve CloudFront private key from AWS Secrets Manager.

    Args:
        secret_name: Name or ARN of the secret
        region: AWS region (defaults to AWS_REGION env var or us-west-2)

    Returns:
        PEM-encoded private key string or None if retrieval fails
    """
    if not region:
        region = os.getenv("AWS_REGION", "us-west-2")

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        private_key = response.get("SecretString")

        if private_key and private_key.startswith("-----BEGIN"):
            logger.info(f"Retrieved CloudFront private key from Secrets Manager: {secret_name}")
            return private_key
        else:
            logger.warning(f"Secret {secret_name} does not contain valid PEM data")
            return None

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Secret not found: {secret_name}")
        elif error_code == "AccessDeniedException":
            logger.warning(f"Access denied to secret: {secret_name}")
        else:
            logger.warning(f"Failed to retrieve secret {secret_name}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error retrieving secret {secret_name}: {e}")
        return None


def get_signer_from_env() -> Optional[CloudFrontSigner]:
    """
    Create a CloudFrontSigner from environment variables.

    Checks for credentials in this order:
    1. CLOUDFRONT_SECRET_NAME - retrieve private key from Secrets Manager
    2. CLOUDFRONT_PRIVATE_KEY - PEM content, file path, or base64-encoded

    Required environment variables:
        CLOUDFRONT_KEY_PAIR_ID: The CloudFront key pair ID

    Plus one of:
        CLOUDFRONT_SECRET_NAME: Name/ARN of secret in Secrets Manager (preferred)
        CLOUDFRONT_PRIVATE_KEY: The PEM-encoded private key (or path to file, or base64-encoded)

    Returns:
        CloudFrontSigner instance or None if not configured
    """
    key_pair_id = os.getenv("CLOUDFRONT_KEY_PAIR_ID")
    if not key_pair_id:
        logger.debug("CloudFront signing not configured (missing KEY_PAIR_ID)")
        return None

    secret_name = os.getenv("CLOUDFRONT_SECRET_NAME")
    if secret_name:
        private_key = get_private_key_from_secrets_manager(secret_name)
        if private_key:
            return CloudFrontSigner(key_pair_id, private_key)
        logger.warning("Failed to get key from Secrets Manager, falling back to env var")

    private_key = os.getenv("CLOUDFRONT_PRIVATE_KEY")
    if not private_key:
        logger.debug("CloudFront signing not configured (missing PRIVATE_KEY or SECRET_NAME)")
        return None

    if os.path.isfile(private_key):
        logger.info(f"Reading CloudFront private key from file: {private_key}")
        with open(private_key, "r") as f:
            private_key = f.read()
    elif private_key.startswith("-----BEGIN"):
        logger.debug("Using raw PEM content from env var")
    else:
        try:
            decoded = base64.b64decode(private_key).decode("utf-8")
            if decoded.startswith("-----BEGIN"):
                logger.info("Decoded base64-encoded PEM key from env var")
                private_key = decoded
            else:
                logger.warning("CLOUDFRONT_PRIVATE_KEY is not valid PEM or base64-encoded PEM")
                return None
        except Exception as e:
            logger.warning(f"Failed to decode CLOUDFRONT_PRIVATE_KEY: {e}")
            return None

    return CloudFrontSigner(key_pair_id, private_key)


def extract_cloudfront_domain(url: str) -> Optional[str]:
    """
    Extract CloudFront domain from a URL.

    Args:
        url: Full URL (e.g., https://d123456789.cloudfront.net/page.html)

    Returns:
        Domain string (e.g., d123456789.cloudfront.net) or None
    """
    parsed = urlparse(url)
    if parsed.netloc and "cloudfront.net" in parsed.netloc:
        return parsed.netloc
    return None
