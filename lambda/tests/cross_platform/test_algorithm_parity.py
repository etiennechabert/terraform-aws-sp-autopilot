"""
Cross-platform algorithm parity tests.

Verifies that Python and JavaScript implementations produce identical results
for critical algorithms like optimal coverage calculation.

These tests require Node.js to be installed in the CI environment.
"""

import json
import subprocess
from pathlib import Path

import pytest

from shared.optimal_coverage import calculate_optimal_coverage


# Check if Node.js is available
def is_node_available():
    """Check if Node.js is installed and available."""
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip all tests in this module if Node.js is not available
pytestmark = pytest.mark.skipif(
    not is_node_available(),
    reason="Node.js not available - cross-platform tests require Node.js",
)


def run_js_optimal_coverage(hourly_costs: list[float], savings_percentage: float) -> dict:
    """
    Run the JavaScript optimal coverage calculation via Node.js.

    Args:
        hourly_costs: List of hourly costs
        savings_percentage: Savings percentage (0-99)

    Returns:
        JavaScript calculation result as dict

    Raises:
        subprocess.CalledProcessError: If JavaScript execution fails
    """
    # Find the docs/js directory relative to this test file
    test_dir = Path(__file__).parent
    project_root = test_dir.parent.parent.parent
    js_file = project_root / "docs" / "js" / "costCalculator.js"

    if not js_file.exists():
        raise FileNotFoundError(f"JavaScript file not found: {js_file}")

    # Create JavaScript code to execute
    js_code = f"""
    // Load the cost calculator module
    const fs = require('fs');
    const jsCode = fs.readFileSync('{js_file}', 'utf-8');

    // Execute the code to define functions
    eval(jsCode);

    // Call the function
    const result = calculateOptimalCoverage(
        {json.dumps(hourly_costs)},
        {savings_percentage}
    );

    // Output as JSON
    console.log(JSON.stringify(result));
    """

    # Run Node.js
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    # Parse JSON output
    return json.loads(result.stdout)


class TestOptimalCoverageParity:
    """Test that Python and JavaScript optimal coverage algorithms match."""

    # Tolerance for floating point comparison (0.01 = 1 cent)
    TOLERANCE = 0.01

    def test_simple_flat_costs(self):
        """Test with all costs the same."""
        hourly_costs = [100.0] * 24
        savings_percentage = 30.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        # Compare key fields
        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE
        assert (
            abs(python_result["coverage_percentage"] - js_result["coveragePercentage"])
            < self.TOLERANCE
        )

    def test_variable_costs(self):
        """Test with variable hourly costs."""
        hourly_costs = [45.2, 52.1, 48.7, 60.3, 55.8, 42.0, 38.5, 50.0, 65.2, 70.1] * 7  # 70 hours
        savings_percentage = 34.8

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE
        assert (
            abs(python_result["coverage_percentage"] - js_result["coveragePercentage"])
            < self.TOLERANCE
        )
        assert (
            abs(python_result["min_hourly_savings"] - js_result["minHourlySavings"])
            < self.TOLERANCE
        )
        assert abs(python_result["extra_savings"] - js_result["extraSavings"]) < self.TOLERANCE

    def test_weekly_pattern(self):
        """Test with realistic weekly pattern (168 hours)."""
        # Simulate lower usage on weekends
        weekday_pattern = [60.0, 65.0, 70.0, 75.0, 80.0, 75.0, 70.0, 65.0] * 3  # 24 hours
        weekend_pattern = [40.0, 35.0, 38.0, 42.0, 45.0, 43.0, 40.0, 38.0] * 3  # 24 hours

        hourly_costs = weekday_pattern * 5 + weekend_pattern * 2  # 5 weekdays + 2 weekend days
        savings_percentage = 30.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE
        assert (
            abs(python_result["coverage_percentage"] - js_result["coveragePercentage"])
            < self.TOLERANCE
        )

    def test_high_variance(self):
        """Test with high variance in costs."""
        hourly_costs = [10.0, 100.0, 15.0, 95.0, 20.0, 90.0, 25.0, 85.0] * 10  # 80 hours
        savings_percentage = 40.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE

    def test_low_savings_percentage(self):
        """Test with low savings percentage."""
        hourly_costs = [50.0, 60.0, 55.0, 70.0, 65.0, 45.0] * 12  # 72 hours
        savings_percentage = 10.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE

    def test_high_savings_percentage(self):
        """Test with high savings percentage."""
        hourly_costs = [50.0, 60.0, 55.0, 70.0, 65.0, 45.0] * 12  # 72 hours
        savings_percentage = 60.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE

    def test_percentiles_match(self):
        """Test that percentile calculations match."""
        hourly_costs = list(range(1, 101))  # 100 hours from $1 to $100
        savings_percentage = 30.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        # Check percentiles
        assert (
            abs(python_result["percentiles"]["p50"] - js_result["percentiles"]["p50"])
            < self.TOLERANCE
        )
        assert (
            abs(python_result["percentiles"]["p75"] - js_result["percentiles"]["p75"])
            < self.TOLERANCE
        )
        assert (
            abs(python_result["percentiles"]["p90"] - js_result["percentiles"]["p90"])
            < self.TOLERANCE
        )

    def test_edge_case_minimum_costs(self):
        """Test with very small costs."""
        hourly_costs = [0.01, 0.02, 0.015, 0.025] * 24  # 96 hours
        savings_percentage = 30.0

        python_result = calculate_optimal_coverage(hourly_costs, savings_percentage)
        js_result = run_js_optimal_coverage(hourly_costs, savings_percentage)

        assert abs(python_result["coverage_hourly"] - js_result["coverageUnits"]) < self.TOLERANCE
        assert abs(python_result["max_net_savings"] - js_result["maxNetSavings"]) < self.TOLERANCE


def test_node_availability():
    """Verify Node.js is available for cross-platform tests."""
    if not is_node_available():
        pytest.skip("Node.js not available - install Node.js to run cross-platform tests")

    result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
    version = result.stdout.strip()
    print(f"Node.js version: {version}")
