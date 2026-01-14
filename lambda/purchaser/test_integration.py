#!/usr/bin/env python3
"""
Integration test script for Purchaser Lambda.

This script performs manual integration testing with mocked AWS services
to verify all required behaviors:
1. Empty queue exits silently
2. Valid purchases execute or skip correctly
3. Cap enforcement works
4. Messages deleted appropriately
5. Emails sent correctly
6. Input validation rejects malformed messages
7. Failed validation messages are NOT deleted (kept for retry)
"""

import json
import os
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import handler


class TestScenario:
    """Helper class to run test scenarios"""

    def __init__(self, name):
        self.name = name
        self.passed = False
        self.errors = []

    def log(self, message):
        print(f"  {message}")

    def assert_true(self, condition, error_message):
        if not condition:
            self.errors.append(error_message)

    def complete(self):
        if not self.errors:
            self.passed = True
            print(f"✓ {self.name} PASSED\n")
        else:
            print(f"✗ {self.name} FAILED:")
            for error in self.errors:
                print(f"    - {error}")
            print()


def test_empty_queue():
    """Test 1: Empty queue should exit silently without error or email"""
    scenario = TestScenario("Test 1: Empty Queue")
    scenario.log("Testing empty queue behavior...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns:

        # Mock empty queue
        mock_sqs.receive_message.return_value = {'Messages': []}

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            'No purchases to process' in response['body'],
            "Expected 'No purchases to process' in response body"
        )
        scenario.assert_true(
            not mock_sns.publish.called,
            "SNS publish should NOT be called for empty queue"
        )
        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_valid_purchase_execution():
    """Test 2: Valid purchase should execute successfully"""
    scenario = TestScenario("Test 2: Valid Purchase Execution")
    scenario.log("Testing valid purchase execution...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS message with valid purchase intent
        purchase_intent = {
            'client_token': 'test-token-123',
            'offering_id': 'sp-offering-123',
            'commitment': '1.50',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,  # 3 years
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 75.0
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(purchase_intent),
                    'ReceiptHandle': 'receipt-handle-123'
                }
            ]
        }

        # Mock current coverage (low coverage, won't exceed cap)
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '50.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Mock successful purchase
        mock_sp.create_savings_plan.return_value = {
            'savingsPlanId': 'sp-12345678'
        }

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            mock_sp.create_savings_plan.called,
            "CreateSavingsPlan should be called"
        )
        scenario.assert_true(
            mock_sqs.delete_message.called,
            "Message should be deleted from queue"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify CreateSavingsPlan parameters
        create_call = mock_sp.create_savings_plan.call_args
        scenario.assert_true(
            create_call[1]['clientToken'] == 'test-token-123',
            "client_token should be used for idempotency"
        )
        scenario.assert_true(
            create_call[1]['savingsPlanOfferingId'] == 'sp-offering-123',
            "offering_id should match intent"
        )

        # Verify email content
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'sp-12345678' in email_call[1]['Message'],
            "Email should contain Savings Plan ID"
        )
        scenario.assert_true(
            'Successful Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 successful purchase"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_cap_enforcement():
    """Test 3: Purchase exceeding cap should be skipped"""
    scenario = TestScenario("Test 3: Cap Enforcement")
    scenario.log("Testing coverage cap enforcement...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS message with purchase that would exceed cap
        purchase_intent = {
            'client_token': 'test-token-456',
            'offering_id': 'sp-offering-456',
            'commitment': '5.00',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 98.0  # Exceeds 95% cap
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(purchase_intent),
                    'ReceiptHandle': 'receipt-handle-456'
                }
            ]
        }

        # Mock current coverage
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '85.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            not mock_sp.create_savings_plan.called,
            "CreateSavingsPlan should NOT be called when exceeding cap"
        )
        scenario.assert_true(
            mock_sqs.delete_message.called,
            "Message should still be deleted even when skipped"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify email content mentions skip
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Skipped Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 skipped purchase"
        )
        scenario.assert_true(
            'Would exceed max_coverage_cap' in email_call[1]['Message'],
            "Email should mention cap reason"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_multiple_messages():
    """Test 4: Multiple messages should be processed and one email sent"""
    scenario = TestScenario("Test 4: Multiple Messages")
    scenario.log("Testing multiple message processing...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS with multiple messages
        purchase_intent_1 = {
            'client_token': 'test-token-1',
            'offering_id': 'sp-offering-1',
            'commitment': '1.00',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 60.0
        }

        purchase_intent_2 = {
            'client_token': 'test-token-2',
            'offering_id': 'sp-offering-2',
            'commitment': '1.50',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 75.0
        }

        purchase_intent_3 = {
            'client_token': 'test-token-3',
            'offering_id': 'sp-offering-3',
            'commitment': '2.00',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 97.0  # Exceeds cap
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {'Body': json.dumps(purchase_intent_1), 'ReceiptHandle': 'receipt-1'},
                {'Body': json.dumps(purchase_intent_2), 'ReceiptHandle': 'receipt-2'},
                {'Body': json.dumps(purchase_intent_3), 'ReceiptHandle': 'receipt-3'}
            ]
        }

        # Mock current coverage
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '40.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Mock successful purchases
        mock_sp.create_savings_plan.side_effect = [
            {'savingsPlanId': 'sp-111'},
            {'savingsPlanId': 'sp-222'}
        ]

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            mock_sp.create_savings_plan.call_count == 2,
            f"Expected 2 CreateSavingsPlan calls, got {mock_sp.create_savings_plan.call_count}"
        )
        scenario.assert_true(
            mock_sqs.delete_message.call_count == 3,
            f"Expected 3 delete_message calls, got {mock_sqs.delete_message.call_count}"
        )
        scenario.assert_true(
            mock_sns.publish.call_count == 1,
            f"Expected 1 email (aggregated), got {mock_sns.publish.call_count}"
        )

        # Verify email content
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Successful Purchases: 2' in email_call[1]['Message'],
            "Email should show 2 successful purchases"
        )
        scenario.assert_true(
            'Skipped Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 skipped purchase"
        )
        scenario.assert_true(
            'sp-111' in email_call[1]['Message'] and 'sp-222' in email_call[1]['Message'],
            "Email should contain both Savings Plan IDs"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_api_error():
    """Test 5: API error should send error email and raise exception"""
    scenario = TestScenario("Test 5: API Error Handling")
    scenario.log("Testing API error handling...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce:

        # Mock SQS message
        purchase_intent = {
            'client_token': 'test-token-error',
            'offering_id': 'sp-offering-error',
            'commitment': '1.00',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 60.0
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(purchase_intent),
                    'ReceiptHandle': 'receipt-error'
                }
            ]
        }

        # Mock API error
        from botocore.exceptions import ClientError
        mock_ce.get_savings_plans_coverage.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetSavingsPlansCoverage'
        )

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler - should raise exception
        exception_raised = False
        try:
            response = handler.handler({}, {})
        except ClientError as e:
            exception_raised = True
            scenario.log(f"Exception raised as expected: {e}")

        # Verify
        scenario.assert_true(
            exception_raised,
            "Exception should be raised on API error"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Error email should be sent"
        )

        # Verify error email content
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'ERROR' in email_call[1]['Subject'],
            "Email subject should contain 'ERROR'"
        )
        scenario.assert_true(
            'Access denied' in email_call[1]['Message'],
            "Email should contain error message"
        )
        scenario.assert_true(
            'Queue URL' in email_call[1]['Message'],
            "Email should contain queue URL for investigation"
        )

    scenario.complete()
    return scenario.passed


def test_database_sp_purchase():
    """Test 6: Database Savings Plan purchase should execute successfully"""
    scenario = TestScenario("Test 6: Database SP Purchase")
    scenario.log("Testing Database Savings Plan purchase...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS message with Database SP purchase intent
        purchase_intent = {
            'client_token': 'test-db-token-123',
            'offering_id': 'sp-db-offering-123',
            'commitment': '2.00',
            'sp_type': 'DatabaseSavingsPlans',
            'term_seconds': 94608000,  # 3 years
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 80.0
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(purchase_intent),
                    'ReceiptHandle': 'receipt-handle-db-123'
                }
            ]
        }

        # Mock current coverage (low database coverage, won't exceed cap)
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '60.0'}
                        },
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'DatabaseSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '45.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Mock successful purchase
        mock_sp.create_savings_plan.return_value = {
            'savingsPlanId': 'sp-db-12345678'
        }

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            mock_sp.create_savings_plan.called,
            "CreateSavingsPlan should be called for Database SP"
        )
        scenario.assert_true(
            mock_sqs.delete_message.called,
            "Message should be deleted from queue"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify CreateSavingsPlan parameters
        create_call = mock_sp.create_savings_plan.call_args
        scenario.assert_true(
            create_call[1]['clientToken'] == 'test-db-token-123',
            "client_token should be used for idempotency"
        )
        scenario.assert_true(
            create_call[1]['savingsPlanOfferingId'] == 'sp-db-offering-123',
            "offering_id should match Database SP intent"
        )

        # Verify email content
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'sp-db-12345678' in email_call[1]['Message'],
            "Email should contain Database SP Savings Plan ID"
        )
        scenario.assert_true(
            'Successful Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 successful purchase"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_database_sp_cap_enforcement():
    """Test 7: Database SP purchase exceeding cap should be skipped"""
    scenario = TestScenario("Test 7: Database SP Cap Enforcement")
    scenario.log("Testing Database SP coverage cap enforcement...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS message with Database SP purchase that would exceed cap
        purchase_intent = {
            'client_token': 'test-db-token-456',
            'offering_id': 'sp-db-offering-456',
            'commitment': '5.00',
            'sp_type': 'DatabaseSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 97.0  # Exceeds 95% cap
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(purchase_intent),
                    'ReceiptHandle': 'receipt-handle-db-456'
                }
            ]
        }

        # Mock current coverage (high database coverage)
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '70.0'}
                        },
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'DatabaseSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '88.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            not mock_sp.create_savings_plan.called,
            "CreateSavingsPlan should NOT be called when Database SP exceeds cap"
        )
        scenario.assert_true(
            mock_sqs.delete_message.called,
            "Message should still be deleted even when skipped"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify email content mentions skip
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Skipped Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 skipped purchase"
        )
        scenario.assert_true(
            'Would exceed max_coverage_cap' in email_call[1]['Message'],
            "Email should mention cap reason"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_mixed_compute_and_database_sp():
    """Test 8: Mixed Compute and Database SP purchases with separate coverage tracking"""
    scenario = TestScenario("Test 8: Mixed Compute and Database SP")
    scenario.log("Testing mixed Compute and Database SP purchases...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns, \
         patch.object(handler, 'ce_client') as mock_ce, \
         patch.object(handler, 'savingsplans_client') as mock_sp:

        # Mock SQS with mixed Compute and Database SP messages
        compute_intent = {
            'client_token': 'test-compute-token-1',
            'offering_id': 'sp-compute-offering-1',
            'commitment': '1.00',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 70.0
        }

        database_intent = {
            'client_token': 'test-database-token-1',
            'offering_id': 'sp-database-offering-1',
            'commitment': '2.00',
            'sp_type': 'DatabaseSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 85.0
        }

        # Database SP that would exceed cap
        database_intent_exceeds = {
            'client_token': 'test-database-token-2',
            'offering_id': 'sp-database-offering-2',
            'commitment': '3.00',
            'sp_type': 'DatabaseSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 96.5  # Exceeds 95% cap
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {'Body': json.dumps(compute_intent), 'ReceiptHandle': 'receipt-compute-1'},
                {'Body': json.dumps(database_intent), 'ReceiptHandle': 'receipt-database-1'},
                {'Body': json.dumps(database_intent_exceeds), 'ReceiptHandle': 'receipt-database-2'}
            ]
        }

        # Mock current coverage (different levels for Compute and Database)
        mock_ce.get_savings_plans_coverage.return_value = {
            'SavingsPlansCoverages': [
                {
                    'Groups': [
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'ComputeSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '50.0'}
                        },
                        {
                            'Attributes': {'SAVINGS_PLANS_TYPE': 'DatabaseSavingsPlans'},
                            'Coverage': {'CoveragePercentage': '60.0'}
                        }
                    ]
                }
            ]
        }

        # Mock no expiring plans
        mock_sp.describe_savings_plans.return_value = {'savingsPlans': []}

        # Mock successful purchases (2 should succeed, 1 should be skipped)
        mock_sp.create_savings_plan.side_effect = [
            {'savingsPlanId': 'sp-compute-111'},
            {'savingsPlanId': 'sp-database-222'}
        ]

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            mock_sp.create_savings_plan.call_count == 2,
            f"Expected 2 CreateSavingsPlan calls (1 Compute + 1 Database), got {mock_sp.create_savings_plan.call_count}"
        )
        scenario.assert_true(
            mock_sqs.delete_message.call_count == 3,
            f"Expected 3 delete_message calls, got {mock_sqs.delete_message.call_count}"
        )
        scenario.assert_true(
            mock_sns.publish.call_count == 1,
            f"Expected 1 email (aggregated), got {mock_sns.publish.call_count}"
        )

        # Verify email content
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Successful Purchases: 2' in email_call[1]['Message'],
            "Email should show 2 successful purchases (1 Compute + 1 Database)"
        )
        scenario.assert_true(
            'Skipped Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 skipped purchase (Database exceeding cap)"
        )
        scenario.assert_true(
            'sp-compute-111' in email_call[1]['Message'],
            "Email should contain Compute SP ID"
        )
        scenario.assert_true(
            'sp-database-222' in email_call[1]['Message'],
            "Email should contain Database SP ID"
        )

        # Verify coverage is reported for both types
        scenario.assert_true(
            'Compute Savings Plans:' in email_call[1]['Message'],
            "Email should report Compute coverage"
        )
        scenario.assert_true(
            'Database Savings Plans:' in email_call[1]['Message'],
            "Email should report Database coverage"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_malformed_message():
    """Test 9: Malformed message (missing required fields) should fail validation"""
    scenario = TestScenario("Test 9: Malformed Message Validation")
    scenario.log("Testing malformed message with missing required fields...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns:

        # Mock SQS message with missing required fields (no client_token, no offering_id)
        malformed_intent = {
            'commitment': '1.50',
            'sp_type': 'ComputeSavingsPlans',
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'projected_coverage_after': 75.0
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(malformed_intent),
                    'ReceiptHandle': 'receipt-handle-malformed'
                }
            ]
        }

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            not mock_sqs.delete_message.called,
            "Message should NOT be deleted from queue (kept for retry)"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify email content shows failed purchase
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Failed Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 failed purchase"
        )
        scenario.assert_true(
            'Validation error' in email_call[1]['Message'],
            "Email should mention validation error"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def test_invalid_sp_type():
    """Test 10: Invalid sp_type should fail validation"""
    scenario = TestScenario("Test 10: Invalid SP Type Validation")
    scenario.log("Testing invalid sp_type value...")

    with patch.object(handler, 'sqs_client') as mock_sqs, \
         patch.object(handler, 'sns_client') as mock_sns:

        # Mock SQS message with invalid sp_type
        invalid_sp_type_intent = {
            'client_token': 'test-token-invalid',
            'offering_id': 'sp-offering-invalid',
            'commitment': '1.50',
            'sp_type': 'InvalidSavingsPlans',  # Invalid type
            'term_seconds': 94608000,
            'payment_option': 'NO_UPFRONT',
            'upfront_amount': None,
            'projected_coverage_after': 75.0
        }

        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'Body': json.dumps(invalid_sp_type_intent),
                    'ReceiptHandle': 'receipt-handle-invalid'
                }
            ]
        }

        # Set environment variables
        os.environ['QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
        os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'
        os.environ['MAX_COVERAGE_CAP'] = '95'

        # Execute handler
        response = handler.handler({}, {})

        # Verify
        scenario.assert_true(
            response['statusCode'] == 200,
            f"Expected statusCode 200, got {response['statusCode']}"
        )
        scenario.assert_true(
            not mock_sqs.delete_message.called,
            "Message should NOT be deleted from queue (kept for retry)"
        )
        scenario.assert_true(
            mock_sns.publish.called,
            "Summary email should be sent"
        )

        # Verify email content shows failed purchase with sp_type validation error
        email_call = mock_sns.publish.call_args
        scenario.assert_true(
            'Failed Purchases: 1' in email_call[1]['Message'],
            "Email should show 1 failed purchase"
        )
        scenario.assert_true(
            'Validation error' in email_call[1]['Message'],
            "Email should mention validation error"
        )
        scenario.assert_true(
            'sp_type' in email_call[1]['Message'].lower(),
            "Email should mention sp_type validation issue"
        )

        scenario.log(f"Response: {response}")

    scenario.complete()
    return scenario.passed


def main():
    """Run all integration tests"""
    print("=" * 70)
    print("PURCHASER LAMBDA - INTEGRATION TESTS")
    print("=" * 70)
    print()

    results = {
        'Test 1: Empty Queue': test_empty_queue(),
        'Test 2: Valid Purchase': test_valid_purchase_execution(),
        'Test 3: Cap Enforcement': test_cap_enforcement(),
        'Test 4: Multiple Messages': test_multiple_messages(),
        'Test 5: API Error': test_api_error(),
        'Test 6: Database SP Purchase': test_database_sp_purchase(),
        'Test 7: Database SP Cap': test_database_sp_cap_enforcement(),
        'Test 8: Mixed Compute/Database': test_mixed_compute_and_database_sp(),
        'Test 9: Malformed Message': test_malformed_message(),
        'Test 10: Invalid SP Type': test_invalid_sp_type()
    }

    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All integration tests PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
