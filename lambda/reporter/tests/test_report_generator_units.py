"""Unit tests for report_generator internal functions."""

import os
import sys
from datetime import UTC, datetime


os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("REPORTS_BUCKET", "test-bucket")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report_generator import _parse_plan_dates


class TestParsePlanDates:
    """Test _parse_plan_dates function with various date scenarios."""

    def test_parse_dates_with_iso_format(self):
        """Test parsing dates in ISO format with timezone."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-12-31T23:59:59Z"

        start, end, days, expiring, tooltip = _parse_plan_dates(
            start_date, end_date, now, three_months
        )

        assert start == "2024-01-01"
        assert end == "2024-12-31"
        assert days == "213 days"
        assert expiring is False
        assert tooltip == "Start: 2024-01-01 | End: 2024-12-31"

    def test_parse_dates_without_time(self):
        """Test parsing dates without time component."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-12-31"

        start, end, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert start == "2024-01-01"
        assert end == "2024-12-31"
        assert days == "213 days"
        assert expiring is False

    def test_expired_plan(self):
        """Test plan that has already expired."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-05-31"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "Expired"
        assert expiring is True

    def test_expiring_today(self):
        """Test plan expiring today."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-06-01"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "Today"
        assert expiring is True

    def test_expiring_in_one_day(self):
        """Test plan expiring in exactly one day."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-06-02"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert days == "1 day"
        assert expiring is True

    def test_expiring_soon(self):
        """Test plan expiring within 3 months."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2024-08-15"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert "days" in days
        assert expiring is True

    def test_not_expiring_soon(self):
        """Test plan not expiring within 3 months."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01"
        end_date = "2025-01-01"

        _, _, days, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert "days" in days
        assert expiring is False

    def test_invalid_date_format(self):
        """Test handling of invalid date format."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "invalid-date"
        end_date = "also-invalid"

        start, end, days, expiring, tooltip = _parse_plan_dates(
            start_date, end_date, now, three_months
        )

        assert start == "invalid-date"
        assert end == "also-invalid"
        assert days == "N/A"
        assert expiring is False
        assert tooltip == ""

    def test_mixed_date_formats(self):
        """Test with start date having time and end date without."""
        now = datetime(2024, 6, 1, tzinfo=UTC)
        three_months = datetime(2024, 9, 1, tzinfo=UTC)

        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-07-15"

        start, end, _, expiring, _ = _parse_plan_dates(start_date, end_date, now, three_months)

        assert start == "2024-01-01"
        assert end == "2024-07-15"
        assert expiring is True
