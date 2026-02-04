"""
Unit tests for sp_calculations module.

Tests all formula functions for correctness, edge cases, and expected behavior.
"""

from shared import sp_calculations


class TestCoverageFromCommitment:
    """Test coverage_from_commitment() function."""

    def test_standard_conversion(self):
        """Test standard commitment to coverage conversion."""
        # 34.8% savings: $1.00 commitment covers $1.53 on-demand
        result = sp_calculations.coverage_from_commitment(1.00, 34.8)
        assert abs(result - 1.5337) < 0.01

    def test_zero_commitment(self):
        """Test with zero commitment."""
        result = sp_calculations.coverage_from_commitment(0.0, 30.0)
        assert result == 0.0

    def test_zero_savings(self):
        """Test with zero savings percentage."""
        # 0% savings means commitment = coverage
        result = sp_calculations.coverage_from_commitment(100.0, 0.0)
        assert result == 100.0

    def test_high_savings(self):
        """Test with high savings percentage."""
        # 60% savings: $1.00 commitment covers $2.50 on-demand
        result = sp_calculations.coverage_from_commitment(1.00, 60.0)
        assert abs(result - 2.50) < 0.01

    def test_edge_case_100_percent_savings(self):
        """Test edge case of 100% savings."""
        # Should return commitment unchanged to avoid division by zero
        result = sp_calculations.coverage_from_commitment(100.0, 100.0)
        assert result == 100.0

    def test_edge_case_over_100_percent_savings(self):
        """Test edge case of >100% savings."""
        result = sp_calculations.coverage_from_commitment(100.0, 150.0)
        assert result == 100.0

    def test_large_commitment(self):
        """Test with large commitment values."""
        result = sp_calculations.coverage_from_commitment(10000.0, 30.0)
        expected = 10000.0 / 0.7  # 1 / (1 - 0.30)
        assert abs(result - expected) < 0.01


class TestCommitmentFromCoverage:
    """Test commitment_from_coverage() function."""

    def test_standard_conversion(self):
        """Test standard coverage to commitment conversion."""
        # 34.8% savings: $1.53 on-demand requires $1.00 commitment
        result = sp_calculations.commitment_from_coverage(1.5337, 34.8)
        assert abs(result - 1.00) < 0.01

    def test_zero_coverage(self):
        """Test with zero coverage."""
        result = sp_calculations.commitment_from_coverage(0.0, 30.0)
        assert result == 0.0

    def test_zero_savings(self):
        """Test with zero savings percentage."""
        # 0% savings means commitment = coverage
        result = sp_calculations.commitment_from_coverage(100.0, 0.0)
        assert result == 100.0

    def test_high_savings(self):
        """Test with high savings percentage."""
        # 60% savings: $2.50 on-demand requires $1.00 commitment
        result = sp_calculations.commitment_from_coverage(2.50, 60.0)
        assert abs(result - 1.00) < 0.01

    def test_roundtrip_conversion(self):
        """Test that commitment -> coverage -> commitment is consistent."""
        original_commitment = 123.45
        savings_pct = 34.8

        coverage = sp_calculations.coverage_from_commitment(original_commitment, savings_pct)
        roundtrip_commitment = sp_calculations.commitment_from_coverage(coverage, savings_pct)

        assert abs(roundtrip_commitment - original_commitment) < 0.001


class TestCalculateSavingsPercentage:
    """Test calculate_savings_percentage() function."""

    def test_standard_calculation(self):
        """Test standard savings percentage calculation."""
        # Used $1.00 to cover $1.53 on-demand = 34.6% savings
        result = sp_calculations.calculate_savings_percentage(1.53, 1.00)
        assert abs(result - 34.64) < 0.1

    def test_zero_on_demand(self):
        """Test with zero on-demand cost."""
        result = sp_calculations.calculate_savings_percentage(0.0, 0.0)
        assert result == 0.0

    def test_negative_on_demand(self):
        """Test with negative on-demand cost (edge case)."""
        result = sp_calculations.calculate_savings_percentage(-100.0, 50.0)
        assert result == 0.0

    def test_equal_costs(self):
        """Test when commitment equals on-demand (0% savings)."""
        result = sp_calculations.calculate_savings_percentage(100.0, 100.0)
        assert result == 0.0

    def test_no_commitment_used(self):
        """Test when no commitment was used (100% savings)."""
        result = sp_calculations.calculate_savings_percentage(100.0, 0.0)
        assert result == 100.0

    def test_high_savings(self):
        """Test with high savings scenario."""
        # Used $40 to cover $100 on-demand = 60% savings
        result = sp_calculations.calculate_savings_percentage(100.0, 40.0)
        assert result == 60.0

    def test_realistic_aws_values(self):
        """Test with realistic AWS Cost Explorer values."""
        on_demand = 1234.56
        used_commitment = 805.97
        result = sp_calculations.calculate_savings_percentage(on_demand, used_commitment)
        expected = ((1234.56 - 805.97) / 1234.56) * 100
        assert abs(result - expected) < 0.01


class TestAverageToHourly:
    """Test average_to_hourly() function."""

    def test_standard_weekly_to_hourly(self):
        """Test converting weekly total to hourly."""
        result = sp_calculations.average_to_hourly(168.0, 168)
        assert result == 1.0

    def test_zero_hours(self):
        """Test with zero hours (edge case)."""
        result = sp_calculations.average_to_hourly(100.0, 0)
        assert result == 0.0

    def test_monthly_to_hourly(self):
        """Test converting monthly total to hourly (30 days)."""
        monthly_total = 7200.0
        hours_in_month = 30 * 24  # 720 hours
        result = sp_calculations.average_to_hourly(monthly_total, hours_in_month)
        assert result == 10.0

    def test_negative_total(self):
        """Test with negative total (refund scenario)."""
        result = sp_calculations.average_to_hourly(-100.0, 24)
        assert abs(result - (-4.166667)) < 0.01

    def test_fractional_hours(self):
        """Test that fractional hours work correctly."""
        result = sp_calculations.average_to_hourly(7.5, 3)
        assert result == 2.5


class TestCalculateEffectiveSavingsRate:
    """Test calculate_effective_savings_rate() function."""

    def test_full_utilization(self):
        """Test with 100% utilization (no waste)."""
        # $100 on-demand, $65 total commitment (all used) = 35% savings
        result = sp_calculations.calculate_effective_savings_rate(100.0, 65.0)
        assert result == 35.0

    def test_partial_utilization(self):
        """Test with partial utilization (has waste)."""
        # $100 on-demand, $70 total commitment (includes waste) = 30% effective savings
        result = sp_calculations.calculate_effective_savings_rate(100.0, 70.0)
        assert result == 30.0

    def test_over_commitment(self):
        """Test when commitment exceeds on-demand (negative savings)."""
        # Paid more for SP than on-demand would cost
        result = sp_calculations.calculate_effective_savings_rate(100.0, 120.0)
        assert result == -20.0

    def test_zero_on_demand(self):
        """Test with zero on-demand cost."""
        result = sp_calculations.calculate_effective_savings_rate(0.0, 50.0)
        assert result == 0.0

    def test_realistic_scenario(self):
        """Test with realistic values."""
        # On-demand would be $10k, total commitment $7k (includes any waste)
        # Effective savings: (10000 - 7000) / 10000 = 30%
        result = sp_calculations.calculate_effective_savings_rate(10000.0, 7000.0)
        assert result == 30.0


class TestCommitmentToPercentageOfCoverage:
    """Test commitment_to_percentage_of_coverage() function."""

    def test_standard_conversion(self):
        """Test standard conversion."""
        result = sp_calculations.commitment_to_percentage_of_coverage(80.0, 100.0)
        assert result == 80.0

    def test_equal_values(self):
        """Test when commitment equals coverage."""
        result = sp_calculations.commitment_to_percentage_of_coverage(100.0, 100.0)
        assert result == 100.0

    def test_zero_coverage(self):
        """Test with zero coverage (edge case)."""
        result = sp_calculations.commitment_to_percentage_of_coverage(50.0, 0.0)
        assert result == 0.0

    def test_commitment_exceeds_coverage(self):
        """Test when commitment > coverage (shouldn't happen, but handle it)."""
        result = sp_calculations.commitment_to_percentage_of_coverage(120.0, 100.0)
        assert result == 120.0


class TestFormulaConsistency:
    """Test that formulas are consistent with each other."""

    def test_commitment_coverage_bidirectional(self):
        """Test bidirectional conversion between commitment and coverage."""
        for commitment in [1.0, 10.0, 100.0, 1000.0]:
            for savings_pct in [10.0, 30.0, 50.0, 70.0]:
                # Convert commitment -> coverage -> commitment
                coverage = sp_calculations.coverage_from_commitment(commitment, savings_pct)
                back_to_commitment = sp_calculations.commitment_from_coverage(coverage, savings_pct)
                assert abs(back_to_commitment - commitment) < 0.001, (
                    f"Roundtrip failed for commitment={commitment}, savings={savings_pct}"
                )

    def test_savings_calculation_matches_conversion(self):
        """Test that savings percentage matches conversion formulas."""
        on_demand = 153.0
        commitment = 100.0

        # Calculate savings percentage from actual usage
        savings_pct = sp_calculations.calculate_savings_percentage(on_demand, commitment)

        # Verify this matches the coverage conversion
        calculated_coverage = sp_calculations.coverage_from_commitment(commitment, savings_pct)
        assert abs(calculated_coverage - on_demand) < 0.1

    def test_hourly_averaging_reversible(self):
        """Test that hourly averaging is reversible."""
        total = 168.0
        hours = 168

        # Convert to hourly
        hourly = sp_calculations.average_to_hourly(total, hours)

        # Convert back to total
        back_to_total = hourly * hours
        assert abs(back_to_total - total) < 0.001
