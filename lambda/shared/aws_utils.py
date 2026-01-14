"""
AWS utility functions for managing cross-account access and client initialization.

Provides reusable utilities for:
- Assuming cross-account IAM roles
- Initializing AWS service clients with optional assumed role credentials
"""

import logging
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_assumed_role_session(role_arn: str, session_name: str = 'sp-autopilot-session') -> Optional[boto3.Session]:
    """
    Assume a cross-account role and return a session with temporary credentials.

    Args:
        role_arn: ARN of the IAM role to assume
        session_name: Name for the role session (default: 'sp-autopilot-session')

    Returns:
        boto3.Session with assumed credentials, or None if role_arn is empty

    Raises:
        ClientError: If assume role fails
    """
    if not role_arn:
        return None

    logger.info(f"Assuming role: {role_arn}")

    try:
        sts_client = boto3.client('sts')
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name
        )

        credentials = response['Credentials']

        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )

        logger.info(f"Successfully assumed role, session expires: {credentials['Expiration']}")
        return session

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to assume role {role_arn} - Code: {error_code}, Message: {error_message}")
        raise


def get_clients(config: Dict[str, Any], session_name: str = 'sp-autopilot-session') -> Dict[str, Any]:
    """
    Get AWS clients, using assumed role if configured.

    Args:
        config: Configuration dictionary with management_account_role_arn
        session_name: Name for the role session when assuming role

    Returns:
        Dictionary of boto3 clients
    """
    role_arn = config.get('management_account_role_arn')

    if role_arn:
        session = get_assumed_role_session(role_arn, session_name)
        return {
            'ce': session.client('ce'),
            'savingsplans': session.client('savingsplans'),
            # Keep SNS/SQS/S3 using local credentials
            'sns': boto3.client('sns'),
            'sqs': boto3.client('sqs'),
            's3': boto3.client('s3'),
        }
    else:
        return {
            'ce': boto3.client('ce'),
            'savingsplans': boto3.client('savingsplans'),
            'sns': boto3.client('sns'),
            'sqs': boto3.client('sqs'),
            's3': boto3.client('s3'),
        }
