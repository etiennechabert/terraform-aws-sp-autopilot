"""Unit tests for lambda/reporter/html_sections.py helpers introduced by the
expandable-plan-details feature (MTD pills, details panel, next-expiry cell,
and the nested breakdown section)."""

import os
import sys
from datetime import UTC, datetime


os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("REPORTS_BUCKET", "test-bucket")
os.environ.setdefault("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:test-topic")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from html_sections import (
    _expiration_phrase,
    _format_days_cell,
    _next_expiry_days,
    _next_expiry_end,
    _render_mtd_card,
    _render_next_expiry_cell,
    _render_plan_card_metrics,
    _render_plan_details,
    build_plans_breakdown_section_html,
)


_NOW = datetime(2026, 4, 1, tzinfo=UTC)
_THREE_MONTHS = datetime(2026, 7, 1, tzinfo=UTC)


def _plan(**overrides):
    """Build a plan dict with safe defaults; callers override the fields they exercise."""
    base = {
        "plan_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee1234",
        "plan_type": "Compute",
        "hourly_commitment": 4.31,
        "start_date": "2024-05-03T08:16:14.377Z",
        "end_date": "2027-05-03T08:16:13.377Z",
        "payment_option": "No Upfront",
        "term_years": 3,
        "offering_id": "off-abc",
        "savings_plan_arn": "arn:aws:savingsplans::123456789012:savingsplan/abc",
        "description": "3 year No Upfront Compute Savings Plan",
        "state": "active",
        "product_types": ["EC2", "Lambda", "Fargate"],
        "currency": "USD",
        "upfront_payment_amount": 0.0,
        "recurring_payment_amount": 4.31,
        "term_seconds": 94_608_000,
        "tags": {"team": "sre"},
        "returnable_until": "2024-05-10T08:16:14.377Z",
    }
    base.update(overrides)
    return base


class TestExpirationPhrase:
    def test_days_get_left_suffix(self):
        assert _expiration_phrase("283 days") == "283 days left"

    def test_single_day(self):
        assert _expiration_phrase("1 day") == "1 day left"

    def test_expired_lowercased(self):
        assert _expiration_phrase("Expired") == "expired"

    def test_today(self):
        assert _expiration_phrase("Today") == "expires today"

    def test_na_passes_through(self):
        assert _expiration_phrase("N/A") == "N/A"


class TestFormatDaysCell:
    def test_negative_is_expired_red(self):
        html = _format_days_cell(-5, "2026-01-01T00:00:00Z")
        assert "Expired" in html
        assert "#dc3545" in html

    def test_zero_is_today_red(self):
        html = _format_days_cell(0, "2026-04-01T00:00:00Z")
        assert "Today" in html
        assert "#dc3545" in html

    def test_within_thirty_is_red(self):
        html = _format_days_cell(12, "2026-04-13T00:00:00Z")
        assert "12 days" in html
        assert "#dc3545" in html

    def test_within_ninety_is_amber(self):
        html = _format_days_cell(60, "2026-05-31T00:00:00Z")
        assert "60 days" in html
        assert "#ffc107" in html

    def test_far_future_is_default(self):
        html = _format_days_cell(400, "2027-05-01T00:00:00Z")
        assert "400 days" in html
        assert "#dc3545" not in html
        assert "#ffc107" not in html

    def test_tooltip_contains_date_prefix(self):
        html = _format_days_cell(400, "2027-05-01T08:00:00Z")
        assert "2027-05-01" in html
        # Time portion of the ISO string is stripped out of the tooltip.
        assert "T08" not in html


class TestNextExpiryHelpers:
    def test_next_expiry_days_picks_soonest(self):
        plans = [
            _plan(end_date="2027-01-01T00:00:00Z"),
            _plan(end_date="2026-06-01T00:00:00Z"),
            _plan(end_date="2028-01-01T00:00:00Z"),
        ]
        assert _next_expiry_days(plans, _NOW) == 61  # 2026-04-01 → 2026-06-01 = 61 calendar days

    def test_next_expiry_days_handles_unknown_dates(self):
        plans = [
            _plan(end_date=""),
            _plan(end_date="Unknown"),
        ]
        assert _next_expiry_days(plans, _NOW) is None

    def test_next_expiry_days_empty_list(self):
        assert _next_expiry_days([], _NOW) is None

    def test_next_expiry_days_accepts_date_only_format(self):
        plans = [_plan(end_date="2026-05-01")]
        days = _next_expiry_days(plans, _NOW)
        assert days is not None
        assert days > 0

    def test_next_expiry_end_returns_soonest(self):
        plans = [
            _plan(end_date="2027-01-01T00:00:00Z"),
            _plan(end_date="2026-06-01T00:00:00Z"),
        ]
        assert _next_expiry_end(plans) == "2026-06-01T00:00:00Z"

    def test_next_expiry_end_empty(self):
        assert _next_expiry_end([]) == ""

    def test_render_next_expiry_cell_none_for_empty(self):
        assert "N/A" in _render_next_expiry_cell([], _NOW)

    def test_render_next_expiry_cell_renders_days(self):
        plans = [_plan(end_date="2026-06-01T00:00:00Z")]
        html = _render_next_expiry_cell(plans, _NOW)
        assert "days" in html
        assert "2026-06-01" in html  # tooltip embeds the end date


class TestRenderPlanCardMetrics:
    def test_returns_empty_when_no_mtd_data(self):
        assert _render_plan_card_metrics(_plan()) == ""

    def test_renders_three_pills_when_data_present(self):
        plan = _plan(
            mtd_total_commitment=384.0,
            mtd_utilization_percentage=100.0,
            mtd_net_savings=205.73,
            discount_percentage=34.9,
        )
        html = _render_plan_card_metrics(plan)
        assert "save $206" in html
        assert "util 100%" in html
        assert "disc 34.9%" in html

    def test_utilization_colors(self):
        low = _plan(mtd_total_commitment=10.0, mtd_utilization_percentage=50.0)
        mid = _plan(mtd_total_commitment=10.0, mtd_utilization_percentage=85.0)
        high = _plan(mtd_total_commitment=10.0, mtd_utilization_percentage=99.0)
        assert "#dc3545" in _render_plan_card_metrics(low)
        assert "#ff9900" in _render_plan_card_metrics(mid)
        assert "#28a745" in _render_plan_card_metrics(high)


class TestRenderMtdCard:
    def test_returns_empty_when_no_mtd_data(self):
        assert _render_mtd_card(_plan(), "USD") == ""

    def test_renders_all_four_tiles(self):
        plan = _plan(
            mtd_total_commitment=384.0,
            mtd_utilization_percentage=100.0,
            mtd_net_savings=205.73,
            discount_percentage=34.9,
        )
        html = _render_mtd_card(plan, "USD")
        assert "MTD Net Savings" in html
        assert "MTD Commitment" in html
        assert "MTD Utilization" in html
        assert "Overall Discount" in html
        assert "USD 205.73" in html
        assert "USD 384.00" in html
        assert "100.0%" in html
        assert "34.9%" in html


class TestRenderPlanDetails:
    def test_renders_core_fields(self):
        html = _render_plan_details(_plan())
        assert "3 year No Upfront Compute Savings Plan" in html
        assert "active" in html
        assert "2024-05-03" in html  # start date
        assert "94,608,000 seconds" in html
        assert "USD 4.31000/hour" in html  # commitment
        assert "arn:aws:savingsplans" in html
        assert "off-abc" in html
        assert "EC2" in html
        assert "Lambda" in html

    def test_renders_tags_table(self):
        html = _render_plan_details(_plan(tags={"team": "sre", "env": "prod"}))
        assert "team" in html
        assert "sre" in html
        assert "env" in html
        assert "prod" in html

    def test_renders_empty_tags_placeholder(self):
        html = _render_plan_details(_plan(tags={}))
        assert "none" in html

    def test_includes_mtd_card_when_available(self):
        plan = _plan(
            mtd_total_commitment=100.0,
            mtd_utilization_percentage=95.0,
            mtd_net_savings=30.0,
            discount_percentage=20.0,
        )
        html = _render_plan_details(plan)
        assert "MTD NET SAVINGS" in html.upper()


class TestBuildPlansBreakdownSection:
    def _breakdown(self, **overrides):
        base = {
            "Compute": {
                "plans_count": 1,
                "total_commitment": 4.31,
                "average_utilization": 100.0,
                "savings_percentage": 40.0,
                "net_savings_hourly": 1.72,
                "on_demand_equivalent_hourly": 6.03,
                "actual_sp_cost_hourly": 4.31,
            },
        }
        base.update(overrides)
        return base

    def test_empty_breakdown_returns_empty(self):
        assert build_plans_breakdown_section_html({}, [], 0, 0.0, 0.0, 0.0) == ""

    def test_renders_type_row_and_nested_plan_card(self):
        plans = [_plan()]
        html = build_plans_breakdown_section_html(self._breakdown(), plans, 1, 100.0, 4.31, 40.0)
        # Outer type row
        assert "Compute Savings Plans" in html
        assert "togglePlanDetails" in html
        assert "type-plans-0" in html
        # Next Expiry column rendered
        assert "Next Expiry" in html
        # Nested plan card (new-style, not a sub-table with dark thead)
        assert "plan-card" in html
        assert "$4.31/hr" in html  # commitment promoted to primary
        assert "3&nbsp;year" in html
        assert "No Upfront" in html
        assert "left" in html  # "N days left" in the meta row
        # Short UUID suffix renders (last 5 chars of plan_id)
        assert "…ee1234"[-5:] in html or "e1234" in html

    def test_no_total_row_when_single_type(self):
        html = build_plans_breakdown_section_html(
            self._breakdown(), [_plan()], 1, 100.0, 4.31, 40.0
        )
        assert "<strong>Total</strong>" not in html

    def test_total_row_when_multiple_types(self):
        breakdown = self._breakdown(
            Database={
                "plans_count": 1,
                "total_commitment": 1.0,
                "average_utilization": 100.0,
                "savings_percentage": 30.0,
            }
        )
        db_plan = _plan(
            plan_id="db000000-1111-2222-3333-444455556666",
            plan_type="Database",
            hourly_commitment=1.0,
            end_date="2027-01-01T00:00:00Z",
        )
        html = build_plans_breakdown_section_html(
            breakdown, [_plan(), db_plan], 2, 100.0, 5.31, 38.0
        )
        assert "<strong>Total</strong>" in html
        assert "38.0%" in html  # overall savings %

    def test_type_with_no_metrics_shows_na(self):
        breakdown = {
            "Compute": {
                "plans_count": 2,
                "total_commitment": 19.31,
                # average_utilization missing — simulates disabled type
            },
        }
        html = build_plans_breakdown_section_html(breakdown, [], 2, 0.0, 19.31, 0.0)
        assert "N/A" in html
