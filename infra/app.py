#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.websites_stack import TestWebsitesStack

app = cdk.App()

TestWebsitesStack(
    app,
    "AirlineTestWebsitesStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    description="S3 + CloudFront infrastructure for airline test websites with signed cookie authentication",
)

app.synth()
