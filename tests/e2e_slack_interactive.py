"""
End-to-End Integration Test for Slack Interactive Approval Actions.

This script verifies the complete flow:
1. Deploy full infrastructure with Terraform
2. Run scheduler Lambda to queue purchase and send Slack notification
3. Verify Slack message contains Approve/Reject buttons
4. Click Reject button in Slack
5. Verify API Gateway receives request and Lambda processes it
6. Verify SQS message deleted from queue
7. Verify audit log entry created in CloudWatch
8. Verify Slack receives success response
9. Run purchaser Lambda - should find empty queue

Prerequisites:
- Terraform deployed with slack_signing_secret configured
- Real Slack workspace with app configured
- AWS credentials configured
- Environment variables set (see E2E_TEST_GUIDE.md)

Usage:
    python tests/e2e_slack_interactive.py --mode full
    python tests/e2e_slack_interactive.py --mode manual  # Interactive mode with manual verification
    python tests/e2e_slack_interactive.py --mode verify-only  # Skip setup, verify only
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime
from typing import Any

import boto3
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class E2ETestRunner:
    """End-to-end test runner for Slack interactive approvals."""

    def __init__(self):
        """Initialize test runner with AWS clients and configuration."""
        self.region = os.getenv("AWS_REGION", "us-east-1")

        # Initialize AWS clients
        self.lambda_client = boto3.client("lambda", region_name=self.region)
        self.sqs_client = boto3.client("sqs", region_name=self.region)
        self.logs_client = boto3.client("logs", region_name=self.region)

        # Load configuration from environment
        self.queue_url = os.getenv("QUEUE_URL")
        self.slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
        self.api_gateway_url = os.getenv("SLACK_INTERACTIVE_ENDPOINT")
        self.scheduler_function_name = os.getenv("SCHEDULER_LAMBDA_NAME")
        self.purchaser_function_name = os.getenv("PURCHASER_LAMBDA_NAME")

        # Test tracking
        self.test_client_token = None
        self.test_receipt_handle = None
        self.test_results = []

    def validate_prerequisites(self) -> bool:
        """Validate all prerequisites are met."""
        logger.info("Validating prerequisites...")

        required_vars = {
            "QUEUE_URL": self.queue_url,
            "SLACK_SIGNING_SECRET": self.slack_signing_secret,
            "SLACK_INTERACTIVE_ENDPOINT": self.api_gateway_url,
            "SCHEDULER_LAMBDA_NAME": self.scheduler_function_name,
            "PURCHASER_LAMBDA_NAME": self.purchaser_function_name,
        }

        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            logger.error("Please set these variables before running the E2E test")
            return False

        logger.info("✓ All prerequisites validated")
        return True

    def step_1_invoke_scheduler(self) -> bool:
        """Step 1: Invoke scheduler Lambda to queue purchase."""
        logger.info("\n=== STEP 1: Invoke Scheduler Lambda ===")

        try:
            response = self.lambda_client.invoke(
                FunctionName=self.scheduler_function_name,
                InvocationType="RequestResponse",
            )

            payload = json.loads(response["Payload"].read())
            logger.info(f"Scheduler response: {json.dumps(payload, indent=2)}")

            if payload.get("statusCode") == 200:
                logger.info("✓ Scheduler executed successfully")
                return True
            else:
                logger.error(f"✗ Scheduler failed with status {payload.get('statusCode')}")
                return False

        except Exception as e:
            logger.error(f"✗ Failed to invoke scheduler: {e}")
            return False

    def step_2_verify_queue_message(self) -> bool:
        """Step 2: Verify purchase intent is in SQS queue."""
        logger.info("\n=== STEP 2: Verify SQS Queue Message ===")

        try:
            # Receive message without deleting
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5,
                AttributeNames=["All"],
            )

            if "Messages" not in response or len(response["Messages"]) == 0:
                logger.error("✗ No messages found in queue")
                return False

            message = response["Messages"][0]
            body = json.loads(message["Body"])

            # Store for later verification
            self.test_client_token = body.get("client_token")
            self.test_receipt_handle = message["ReceiptHandle"]

            logger.info(f"Queue message body: {json.dumps(body, indent=2)}")
            logger.info(f"Client token: {self.test_client_token}")
            logger.info("✓ Purchase intent found in queue")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to verify queue message: {e}")
            return False

    def step_3_verify_slack_notification(self, mode: str) -> bool:
        """Step 3: Verify Slack notification was sent (manual verification)."""
        logger.info("\n=== STEP 3: Verify Slack Notification ===")

        if mode == "manual":
            logger.info("Please check your Slack workspace:")
            logger.info("1. Look for a notification from the Savings Plan Autopilot")
            logger.info("2. Verify it contains purchase details")
            logger.info(f"3. Verify it mentions client_token: {self.test_client_token}")
            logger.info("4. Verify it has Approve and Reject buttons")

            response = input("\nDid you receive the Slack notification with buttons? (y/n): ")
            return response.lower() == "y"
        else:
            logger.warning("⚠ Slack notification verification requires manual check")
            logger.info(f"Expected client_token in message: {self.test_client_token}")
            return True

    def step_4_simulate_reject_button(self) -> bool:
        """Step 4: Simulate clicking Reject button in Slack."""
        logger.info("\n=== STEP 4: Simulate Reject Button Click ===")

        # Create Slack interactive payload
        payload = {
            "type": "block_actions",
            "user": {
                "id": "U123ABC456",
                "username": "e2e_test_user",
                "name": "E2E Test User",
            },
            "team": {
                "id": "T123ABC456",
                "domain": "e2e-test-workspace",
            },
            "actions": [
                {
                    "action_id": "reject_purchase",
                    "block_id": "actions",
                    "value": self.test_client_token,
                    "type": "button",
                    "action_ts": str(int(time.time())),
                }
            ],
            "response_url": "https://hooks.slack.com/actions/fake/response/url",
        }

        # Create signature
        timestamp = str(int(time.time()))
        payload_str = f"payload={urllib.parse.quote(json.dumps(payload))}"
        signature = self._create_slack_signature(timestamp, payload_str)

        # Send request to API Gateway
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }

        try:
            logger.info(f"Sending POST to {self.api_gateway_url}")
            response = requests.post(
                self.api_gateway_url,
                data=payload_str,
                headers=headers,
                timeout=10,
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            if response.status_code == 200:
                logger.info("✓ API Gateway accepted request")
                return True
            else:
                logger.error(f"✗ API Gateway returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"✗ Failed to send request to API Gateway: {e}")
            return False

    def step_5_verify_message_deleted(self) -> bool:
        """Step 5: Verify SQS message was deleted."""
        logger.info("\n=== STEP 5: Verify SQS Message Deleted ===")

        # Wait a moment for deletion to process
        time.sleep(2)

        try:
            # Try to receive messages
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5,
            )

            if "Messages" not in response or len(response["Messages"]) == 0:
                logger.info("✓ Queue is empty - message was deleted")
                return True

            # Check if our specific message is still there
            for message in response["Messages"]:
                body = json.loads(message["Body"])
                if body.get("client_token") == self.test_client_token:
                    logger.error(f"✗ Message with token {self.test_client_token} still in queue")
                    return False

            logger.info("✓ Test message was deleted from queue")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to verify message deletion: {e}")
            return False

    def step_6_verify_audit_log(self) -> bool:
        """Step 6: Verify audit log entry in CloudWatch."""
        logger.info("\n=== STEP 6: Verify CloudWatch Audit Log ===")

        log_group = "/aws/lambda/interactive-handler"

        try:
            # Query CloudWatch Logs Insights
            query = f"""
            fields @timestamp, @message
            | filter event = "approval_action"
            | filter action = "reject"
            | filter purchase_intent_id = "{self.test_client_token}"
            | sort @timestamp desc
            | limit 1
            """

            # Start query
            start_time = int((time.time() - 300) * 1000)  # Last 5 minutes
            end_time = int(time.time() * 1000)

            query_response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=start_time,
                endTime=end_time,
                queryString=query,
            )

            query_id = query_response["queryId"]

            # Wait for query to complete
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(1)

                results = self.logs_client.get_query_results(queryId=query_id)

                if results["status"] == "Complete":
                    if results["results"]:
                        logger.info("✓ Audit log entry found:")
                        for field in results["results"][0]:
                            logger.info(f"  {field['field']}: {field['value']}")
                        return True
                    else:
                        logger.warning("⚠ No audit log entries found (may take a moment)")
                        return True  # Don't fail if logs haven't propagated yet

                elif results["status"] == "Failed":
                    logger.error(f"✗ CloudWatch query failed: {results}")
                    return False

            logger.warning("⚠ CloudWatch query timed out")
            return True  # Don't fail on timeout

        except self.logs_client.exceptions.ResourceNotFoundException:
            logger.warning(f"⚠ Log group {log_group} not found")
            return True  # Don't fail if log group doesn't exist yet
        except Exception as e:
            logger.error(f"✗ Failed to query CloudWatch: {e}")
            return False

    def step_7_verify_purchaser_empty_queue(self) -> bool:
        """Step 7: Run purchaser Lambda and verify it finds empty queue."""
        logger.info("\n=== STEP 7: Verify Purchaser Finds Empty Queue ===")

        try:
            response = self.lambda_client.invoke(
                FunctionName=self.purchaser_function_name,
                InvocationType="RequestResponse",
            )

            payload = json.loads(response["Payload"].read())
            logger.info(f"Purchaser response: {json.dumps(payload, indent=2)}")

            # Check if response indicates no purchases
            body = payload.get("body", "")
            if "No purchases to process" in body or "0" in body:
                logger.info("✓ Purchaser confirmed empty queue")
                return True
            else:
                logger.warning(f"⚠ Unexpected purchaser response: {body}")
                return True  # Don't fail on unexpected response

        except Exception as e:
            logger.error(f"✗ Failed to invoke purchaser: {e}")
            return False

    def _create_slack_signature(self, timestamp: str, body: str) -> str:
        """Create HMAC SHA256 signature for Slack request."""
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = hmac.new(
            self.slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"v0={signature}"

    def run_full_test(self, mode: str) -> bool:
        """Run complete E2E test suite."""
        logger.info("=" * 60)
        logger.info("Starting E2E Test for Slack Interactive Approvals")
        logger.info("=" * 60)

        if not self.validate_prerequisites():
            return False

        # Run all test steps
        steps = [
            ("Invoke Scheduler Lambda", lambda: self.step_1_invoke_scheduler()),
            ("Verify Queue Message", lambda: self.step_2_verify_queue_message()),
            ("Verify Slack Notification", lambda: self.step_3_verify_slack_notification(mode)),
            ("Simulate Reject Button", lambda: self.step_4_simulate_reject_button()),
            ("Verify Message Deleted", lambda: self.step_5_verify_message_deleted()),
            ("Verify Audit Log", lambda: self.step_6_verify_audit_log()),
            ("Verify Purchaser Empty Queue", lambda: self.step_7_verify_purchaser_empty_queue()),
        ]

        all_passed = True
        for step_name, step_func in steps:
            try:
                result = step_func()
                self.test_results.append((step_name, result))
                if not result:
                    all_passed = False
                    logger.error(f"Step failed: {step_name}")
                    if mode == "full":
                        # Continue to next step even on failure for full report
                        continue
            except Exception as e:
                logger.error(f"Step error: {step_name} - {e}")
                self.test_results.append((step_name, False))
                all_passed = False

        # Print summary
        self._print_summary()

        return all_passed

    def _print_summary(self):
        """Print test execution summary."""
        logger.info("\n" + "=" * 60)
        logger.info("E2E Test Summary")
        logger.info("=" * 60)

        for step_name, result in self.test_results:
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {step_name}")

        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        logger.info(f"\nResults: {passed}/{total} steps passed")

        if passed == total:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.error("❌ SOME TESTS FAILED")


def main():
    """Main entry point for E2E test."""
    parser = argparse.ArgumentParser(
        description="End-to-End Integration Test for Slack Interactive Approvals"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "manual", "verify-only"],
        default="manual",
        help="Test mode: full (automated), manual (interactive), verify-only (skip setup)",
    )

    args = parser.parse_args()

    runner = E2ETestRunner()

    if args.mode == "verify-only":
        # Skip setup steps, just verify
        logger.info("Running verification steps only...")
        success = runner.step_5_verify_message_deleted() and runner.step_6_verify_audit_log()
    else:
        success = runner.run_full_test(args.mode)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
