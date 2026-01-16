from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
from constructs import Construct
import os

WEBSITES = [
    "website1-airlines",
    "website2-seatmap",
    "website3-spa",
    "website4-dialogs",
    "website5-iframes",
    "website6-popups",
]


class TestWebsitesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        public_key_path = self.node.try_get_context("cloudfront_public_key_path")
        if not public_key_path:
            raise ValueError(
                "Missing context: cloudfront_public_key_path. "
                "Generate a key pair and pass the path via -c cloudfront_public_key_path='...'"
            )

        with open(os.path.expanduser(public_key_path), "r") as f:
            public_key_pem = f.read()

        cf_public_key = cloudfront.PublicKey(
            self,
            "SignedCookiePublicKey",
            encoded_key=public_key_pem,
        )

        key_group = cloudfront.KeyGroup(
            self,
            "SignedCookieKeyGroup",
            items=[cf_public_key],
        )

        CfnOutput(
            self,
            "CloudFrontKeyPairId",
            value=cf_public_key.public_key_id,
            description="CloudFront Key Pair ID for signed cookies",
        )

        websites_path = os.path.join(os.path.dirname(__file__), "..", "..", "test-websites")

        for site_name in WEBSITES:
            site_path = os.path.join(websites_path, site_name)
            if not os.path.isdir(site_path):
                continue

            safe_id = site_name.replace("-", "")

            bucket = s3.Bucket(
                self,
                f"{safe_id}Bucket",
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
            )

            oac = cloudfront.S3OriginAccessControl(
                self,
                f"{safe_id}OAC",
                signing=cloudfront.Signing.SIGV4_ALWAYS,
            )

            s3_origin = origins.S3BucketOrigin.with_origin_access_control(
                bucket,
                origin_access_control=oac,
            )

            distribution = cloudfront.Distribution(
                self,
                f"{safe_id}Distribution",
                default_behavior=cloudfront.BehaviorOptions(
                    origin=s3_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    trusted_key_groups=[key_group],
                    cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                ),
                default_root_object="index.html",
                # No custom error responses - let 403 (auth) and 404 (not found) return as-is
            )

            s3deploy.BucketDeployment(
                self,
                f"{safe_id}Deployment",
                sources=[s3deploy.Source.asset(site_path)],
                destination_bucket=bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )

            CfnOutput(
                self,
                f"{safe_id}Url",
                value=f"https://{distribution.distribution_domain_name}",
                description=f"CloudFront URL for {site_name}",
            )

            CfnOutput(
                self,
                f"{safe_id}DistributionId",
                value=distribution.distribution_id,
                description=f"CloudFront Distribution ID for {site_name}",
            )
