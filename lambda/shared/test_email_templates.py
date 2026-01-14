"""
Comprehensive unit tests for email template utilities.

Tests cover all email_templates.py functions with various inputs and edge cases.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared import email_templates


# ============================================================================
# build_header Tests
# ============================================================================

def test_build_header_default_width():
    """Test build_header with default width."""
    result = email_templates.build_header("Purchase Summary")

    # Verify it returns a list with 2 elements
    assert isinstance(result, list)
    assert len(result) == 2

    # Verify title is first line
    assert result[0] == "Purchase Summary"

    # Verify separator is second line with default width of 50
    assert result[1] == "=" * 50
    assert len(result[1]) == 50


def test_build_header_custom_width():
    """Test build_header with custom width."""
    result = email_templates.build_header("Report Generated", width=60)

    assert len(result) == 2
    assert result[0] == "Report Generated"
    assert result[1] == "=" * 60
    assert len(result[1]) == 60


def test_build_header_empty_title():
    """Test build_header with empty title string."""
    result = email_templates.build_header("")

    assert len(result) == 2
    assert result[0] == ""
    assert result[1] == "=" * 50


def test_build_header_long_title():
    """Test build_header with title longer than separator."""
    long_title = "This is a very long title that exceeds the separator width"
    result = email_templates.build_header(long_title, width=30)

    assert len(result) == 2
    assert result[0] == long_title
    assert result[1] == "=" * 30
    assert len(result[0]) > len(result[1])


# ============================================================================
# build_separator Tests
# ============================================================================

def test_build_separator_default_params():
    """Test build_separator with default parameters."""
    result = email_templates.build_separator()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == "-" * 50
    assert len(result[0]) == 50


def test_build_separator_custom_width():
    """Test build_separator with custom width."""
    result = email_templates.build_separator(width=60)

    assert len(result) == 1
    assert result[0] == "-" * 60
    assert len(result[0]) == 60


def test_build_separator_custom_char():
    """Test build_separator with custom character."""
    result = email_templates.build_separator(char="=")

    assert len(result) == 1
    assert result[0] == "=" * 50


def test_build_separator_custom_width_and_char():
    """Test build_separator with both custom width and character."""
    result = email_templates.build_separator(width=40, char="*")

    assert len(result) == 1
    assert result[0] == "*" * 40
    assert len(result[0]) == 40


# ============================================================================
# build_key_value_section Tests
# ============================================================================

def test_build_key_value_section_mixed_types():
    """Test build_key_value_section with mixed value types."""
    data = {
        'Total Plans': 5,
        'Coverage': 85.75,
        'Status': 'Active'
    }

    result = email_templates.build_key_value_section(data)

    assert isinstance(result, list)
    assert len(result) == 3

    # Verify each key-value pair is formatted correctly
    assert 'Total Plans: 5' in result
    assert 'Coverage: 85.75' in result
    assert 'Status: Active' in result


def test_build_key_value_section_float_formatting():
    """Test build_key_value_section formats floats with 2 decimals."""
    data = {
        'Compute SP': 75.5,
        'Database SP': 82.3456789
    }

    result = email_templates.build_key_value_section(data)

    assert len(result) == 2
    assert 'Compute SP: 75.50' in result
    assert 'Database SP: 82.35' in result


def test_build_key_value_section_with_indent():
    """Test build_key_value_section with indentation."""
    data = {
        'Item 1': 'Value 1',
        'Item 2': 'Value 2'
    }

    result = email_templates.build_key_value_section(data, indent='  ')

    assert len(result) == 2
    assert '  Item 1: Value 1' in result
    assert '  Item 2: Value 2' in result
    # Verify indentation is applied
    for line in result:
        assert line.startswith('  ')


def test_build_key_value_section_format_numbers_false():
    """Test build_key_value_section with format_numbers disabled."""
    data = {
        'Value': 85.75678
    }

    result = email_templates.build_key_value_section(data, format_numbers=False)

    assert len(result) == 1
    # Should convert to string without formatting
    assert 'Value: 85.75678' in result


def test_build_key_value_section_empty_dict():
    """Test build_key_value_section with empty dictionary."""
    result = email_templates.build_key_value_section({})

    assert isinstance(result, list)
    assert len(result) == 0


def test_build_key_value_section_integer_values():
    """Test build_key_value_section with integer values only."""
    data = {
        'Count': 100,
        'Total': 500
    }

    result = email_templates.build_key_value_section(data)

    assert len(result) == 2
    assert 'Count: 100' in result
    assert 'Total: 500' in result


# ============================================================================
# build_list_section Tests
# ============================================================================

def test_build_list_section_with_separator():
    """Test build_list_section with separator (default)."""
    items = [
        "1. Compute SP - $1.50/hour",
        "2. Database SP - $0.75/hour"
    ]

    result = email_templates.build_list_section(
        "SUCCESSFUL PURCHASES",
        items
    )

    assert isinstance(result, list)
    assert len(result) == 4  # title + separator + 2 items

    # Verify title
    assert result[0] == "SUCCESSFUL PURCHASES"

    # Verify separator
    assert result[1] == "-" * 50

    # Verify items
    assert result[2] == items[0]
    assert result[3] == items[1]


def test_build_list_section_without_separator():
    """Test build_list_section without separator."""
    items = ["First note", "Second note"]

    result = email_templates.build_list_section(
        "Notes",
        items,
        include_separator=False
    )

    assert len(result) == 3  # title + 2 items
    assert result[0] == "Notes"
    assert result[1] == "First note"
    assert result[2] == "Second note"

    # Verify no separator line
    assert "-" * 50 not in result


def test_build_list_section_custom_width():
    """Test build_list_section with custom width."""
    items = ["Item 1"]

    result = email_templates.build_list_section(
        "Custom Width Section",
        items,
        width=60
    )

    # Verify separator uses custom width
    assert result[1] == "-" * 60
    assert len(result[1]) == 60


def test_build_list_section_empty_items():
    """Test build_list_section with empty items list."""
    result = email_templates.build_list_section(
        "Empty Section",
        []
    )

    assert len(result) == 2  # title + separator only
    assert result[0] == "Empty Section"
    assert result[1] == "-" * 50


def test_build_list_section_single_item():
    """Test build_list_section with single item."""
    result = email_templates.build_list_section(
        "Single Item",
        ["Only one item"]
    )

    assert len(result) == 3
    assert result[0] == "Single Item"
    assert result[1] == "-" * 50
    assert result[2] == "Only one item"


# ============================================================================
# build_footer Tests
# ============================================================================

def test_build_footer_default():
    """Test build_footer with default parameters."""
    result = email_templates.build_footer()

    assert isinstance(result, list)
    assert len(result) == 2  # separator + message

    # Verify separator
    assert result[0] == "-" * 50

    # Verify default message
    expected_message = "This is an automated message from AWS Savings Plans Automation."
    assert result[1] == expected_message


def test_build_footer_custom_message():
    """Test build_footer with custom message."""
    custom_msg = "End of report"

    result = email_templates.build_footer(custom_message=custom_msg)

    assert len(result) == 2
    assert result[0] == "-" * 50
    assert result[1] == custom_msg


def test_build_footer_custom_width():
    """Test build_footer with custom width."""
    result = email_templates.build_footer(width=60)

    assert len(result) == 2
    assert result[0] == "-" * 60
    assert len(result[0]) == 60


def test_build_footer_without_separator():
    """Test build_footer without separator."""
    result = email_templates.build_footer(include_separator=False)

    assert len(result) == 1
    expected_message = "This is an automated message from AWS Savings Plans Automation."
    assert result[0] == expected_message


def test_build_footer_custom_message_and_width():
    """Test build_footer with both custom message and width."""
    result = email_templates.build_footer(
        custom_message="Custom footer",
        width=40
    )

    assert len(result) == 2
    assert result[0] == "-" * 40
    assert result[1] == "Custom footer"


def test_build_footer_all_custom_params():
    """Test build_footer with all parameters customized."""
    result = email_templates.build_footer(
        custom_message="All custom",
        width=30,
        include_separator=False
    )

    assert len(result) == 1
    assert result[0] == "All custom"


# ============================================================================
# format_currency Tests
# ============================================================================

def test_format_currency_default():
    """Test format_currency with default parameters."""
    result = email_templates.format_currency(1234.56)

    # Default: 2 decimals with thousands separator
    assert result == "$1,234.56"


def test_format_currency_hourly_rate():
    """Test format_currency for hourly rates."""
    result = email_templates.format_currency(1.5, hourly=True)

    # Hourly: 4 decimals with /hour suffix
    assert result == "$1.5000/hour"


def test_format_currency_hourly_rate_precise():
    """Test format_currency for hourly rates with precise values."""
    result = email_templates.format_currency(0.1234, hourly=True)

    assert result == "$0.1234/hour"


def test_format_currency_monthly_amount():
    """Test format_currency for monthly amounts."""
    result = email_templates.format_currency(5000, monthly=True)

    # Monthly: 2 decimals with thousands separator and /month suffix
    assert result == "$5,000.00/month"


def test_format_currency_monthly_with_decimals():
    """Test format_currency for monthly amounts with decimal values."""
    result = email_templates.format_currency(12345.67, monthly=True)

    assert result == "$12,345.67/month"


def test_format_currency_large_amount():
    """Test format_currency with large amounts and thousands separators."""
    result = email_templates.format_currency(1234567.89)

    assert result == "$1,234,567.89"


def test_format_currency_zero():
    """Test format_currency with zero value."""
    result = email_templates.format_currency(0.0)

    assert result == "$0.00"


def test_format_currency_small_decimal():
    """Test format_currency with small decimal values."""
    result = email_templates.format_currency(0.01)

    assert result == "$0.01"


def test_format_currency_hourly_zero():
    """Test format_currency with zero hourly rate."""
    result = email_templates.format_currency(0.0, hourly=True)

    assert result == "$0.0000/hour"


def test_format_currency_monthly_zero():
    """Test format_currency with zero monthly amount."""
    result = email_templates.format_currency(0.0, monthly=True)

    assert result == "$0.00/month"


# ============================================================================
# format_percentage Tests
# ============================================================================

def test_format_percentage_default_decimals():
    """Test format_percentage with default 2 decimals."""
    result = email_templates.format_percentage(85.5)

    assert result == "85.50%"


def test_format_percentage_custom_decimals():
    """Test format_percentage with custom decimal places."""
    result = email_templates.format_percentage(100.0, decimals=0)

    assert result == "100%"


def test_format_percentage_zero():
    """Test format_percentage with zero value."""
    result = email_templates.format_percentage(0.0)

    assert result == "0.00%"


def test_format_percentage_one_decimal():
    """Test format_percentage with one decimal place."""
    result = email_templates.format_percentage(75.678, decimals=1)

    assert result == "75.7%"


def test_format_percentage_three_decimals():
    """Test format_percentage with three decimal places."""
    result = email_templates.format_percentage(99.9876, decimals=3)

    assert result == "99.988%"


def test_format_percentage_whole_number():
    """Test format_percentage with whole number value."""
    result = email_templates.format_percentage(50.0)

    assert result == "50.00%"


def test_format_percentage_high_precision():
    """Test format_percentage with high precision value."""
    result = email_templates.format_percentage(33.333333, decimals=4)

    assert result == "33.3333%"


# ============================================================================
# Integration Tests - Complete Email Building
# ============================================================================

def test_build_complete_email_simple():
    """Test building a complete simple email using multiple functions."""
    lines = []
    lines.extend(email_templates.build_header("Purchase Summary", width=60))
    lines.extend(email_templates.build_key_value_section({
        'Total Purchases': 5,
        'Successful': 4,
        'Failed': 1
    }))
    lines.extend(email_templates.build_footer())

    email_body = "\n".join(lines)

    # Verify structure
    assert "Purchase Summary" in email_body
    assert "=" * 60 in email_body
    assert "Total Purchases: 5" in email_body
    assert "Successful: 4" in email_body
    assert "Failed: 1" in email_body
    assert "This is an automated message from AWS Savings Plans Automation." in email_body


def test_build_complete_email_complex():
    """Test building a complex email with multiple sections."""
    lines = []
    lines.extend(email_templates.build_header("Savings Plans Report", width=60))
    lines.extend(email_templates.build_key_value_section({
        'Report Generated': '2024-01-15 10:30:00 UTC',
        'Reporting Period': '30 days'
    }))
    lines.append("")  # Blank line
    lines.extend(email_templates.build_list_section(
        "SUCCESSFUL PURCHASES",
        items=['Compute SP - $1.50/hour', 'Database SP - $0.75/hour'],
        width=60
    ))
    lines.extend(email_templates.build_footer(width=60))

    email_body = "\n".join(lines)

    # Verify all sections are present
    assert "Savings Plans Report" in email_body
    assert "Report Generated: 2024-01-15 10:30:00 UTC" in email_body
    assert "Reporting Period: 30 days" in email_body
    assert "SUCCESSFUL PURCHASES" in email_body
    assert "Compute SP - $1.50/hour" in email_body
    assert "Database SP - $0.75/hour" in email_body

    # Verify structure has separators
    assert email_body.count("=" * 60) == 1  # Header separator
    assert email_body.count("-" * 60) == 2  # List separator + footer separator
