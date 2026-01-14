"""
Email template utilities for building consistent email bodies across Lambda functions.

This module provides helper functions for constructing email bodies with consistent
formatting patterns. All three Lambda handlers (scheduler, purchaser, reporter) use
these utilities to generate standardized email notifications.

Example Usage:
    # Build a simple email with header and key-value pairs
    lines = []
    lines.extend(build_header("Purchase Summary", width=60))
    lines.extend(build_key_value_section({
        'Total Purchases': 5,
        'Successful': 4,
        'Failed': 1
    }))
    lines.extend(build_footer())
    email_body = "\\n".join(lines)

    # Build a complex email with multiple sections
    lines = []
    lines.extend(build_header("Savings Plans Report", width=60))
    lines.extend(build_key_value_section({
        'Report Generated': '2024-01-15 10:30:00 UTC',
        'Reporting Period': '30 days'
    }))
    lines.append("")
    lines.extend(build_list_section(
        "SUCCESSFUL PURCHASES",
        items=['Compute SP - $1.50/hour', 'Database SP - $0.75/hour'],
        width=60
    ))
    lines.extend(build_footer())
    email_body = "\\n".join(lines)
"""

import logging
from typing import Any, Dict, List, Optional, Union


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def build_header(title: str, width: int = 50) -> List[str]:
    """
    Build an email header with title and separator line.

    Creates a two-line header consisting of the title followed by an equals
    separator line. This is the standard header format used across all email
    notifications.

    Args:
        title: The header title text
        width: Width of the separator line (default: 50)

    Returns:
        List[str]: Two-line header [title, separator]

    Examples:
        >>> build_header("Purchase Summary")
        ['Purchase Summary', '==================================================']

        >>> build_header("Report Generated", width=60)
        ['Report Generated', '============================================================']
    """
    if not title:
        logger.warning("Empty title provided to build_header, using empty string")
        title = ""

    return [
        title,
        "=" * width
    ]


def build_separator(width: int = 50, char: str = "-") -> List[str]:
    """
    Build a separator line for email sections.

    Creates a single-line separator using the specified character. Commonly used
    to separate different sections within an email body.

    Args:
        width: Width of the separator line (default: 50)
        char: Character to use for the separator (default: "-")

    Returns:
        List[str]: Single-line separator

    Examples:
        >>> build_separator()
        ['--------------------------------------------------']

        >>> build_separator(width=60, char="=")
        ['============================================================']
    """
    return [char * width]


def build_key_value_section(
    data: Dict[str, Any],
    indent: str = "",
    format_numbers: bool = True
) -> List[str]:
    """
    Build a section with key-value pairs.

    Creates formatted lines for displaying key-value data. Supports automatic
    number formatting for floats (2 decimal places) and proper string conversion
    for all value types.

    Args:
        data: Dictionary of key-value pairs to format
        indent: Optional indentation prefix for each line (default: "")
        format_numbers: Whether to format float values with 2 decimals (default: True)

    Returns:
        List[str]: Formatted key-value lines

    Examples:
        >>> build_key_value_section({
        ...     'Total Plans': 5,
        ...     'Coverage': 85.75,
        ...     'Status': 'Active'
        ... })
        ['Total Plans: 5', 'Coverage: 85.75', 'Status: Active']

        >>> build_key_value_section(
        ...     {'Compute SP': 75.5, 'Database SP': 82.3},
        ...     indent='  '
        ... )
        ['  Compute SP: 75.50', '  Database SP: 82.30']
    """
    lines = []

    for key, value in data.items():
        # Format value based on type
        if format_numbers and isinstance(value, float):
            formatted_value = f"{value:.2f}"
        else:
            formatted_value = str(value)

        lines.append(f"{indent}{key}: {formatted_value}")

    return lines


def build_list_section(
    section_title: str,
    items: List[str],
    width: int = 50,
    include_separator: bool = True
) -> List[str]:
    """
    Build a titled list section with optional separator.

    Creates a formatted section with a title, optional separator line, and a list
    of items. Commonly used for sections like "SUCCESSFUL PURCHASES" or
    "FAILED OPERATIONS".

    Args:
        section_title: Title for the list section
        items: List of item strings to include
        width: Width of the separator line (default: 50)
        include_separator: Whether to include a separator after the title (default: True)

    Returns:
        List[str]: Formatted list section lines

    Examples:
        >>> build_list_section(
        ...     "SUCCESSFUL PURCHASES",
        ...     ["1. Compute SP - $1.50/hour", "2. Database SP - $0.75/hour"]
        ... )
        ['SUCCESSFUL PURCHASES', '--------------------------------------------------',
         '1. Compute SP - $1.50/hour', '2. Database SP - $0.75/hour']

        >>> build_list_section(
        ...     "Notes",
        ...     ["First note", "Second note"],
        ...     include_separator=False
        ... )
        ['Notes', 'First note', 'Second note']
    """
    lines = [section_title]

    if include_separator:
        lines.append("-" * width)

    lines.extend(items)

    return lines


def build_footer(
    custom_message: Optional[str] = None,
    width: int = 50,
    include_separator: bool = True
) -> List[str]:
    """
    Build a standard email footer.

    Creates a standard footer with optional separator and default or custom message.
    The default message identifies the email as automated from AWS Savings Plans
    Automation.

    Args:
        custom_message: Optional custom footer message. If None, uses default message.
        width: Width of the separator line (default: 50)
        include_separator: Whether to include a separator before the message (default: True)

    Returns:
        List[str]: Formatted footer lines

    Examples:
        >>> build_footer()
        ['--------------------------------------------------',
         'This is an automated message from AWS Savings Plans Automation.']

        >>> build_footer(custom_message="End of report", width=60)
        ['------------------------------------------------------------', 'End of report']

        >>> build_footer(include_separator=False)
        ['This is an automated message from AWS Savings Plans Automation.']
    """
    default_message = "This is an automated message from AWS Savings Plans Automation."
    message = custom_message if custom_message is not None else default_message

    lines = []

    if include_separator:
        lines.append("-" * width)

    lines.append(message)

    return lines


def format_currency(
    amount: float,
    hourly: bool = False,
    monthly: bool = False
) -> str:
    """
    Format a currency amount with proper precision and optional rate suffix.

    Provides consistent currency formatting across all email templates. Supports
    different precision levels for hourly rates (4 decimals) vs. monthly/annual
    amounts (2 decimals with thousands separators).

    Args:
        amount: The numeric amount to format
        hourly: Whether to format as hourly rate with '/hour' suffix (default: False)
        monthly: Whether to format as monthly amount with '/month' suffix (default: False)

    Returns:
        str: Formatted currency string

    Examples:
        >>> format_currency(1234.56)
        '$1,234.56'

        >>> format_currency(1.5, hourly=True)
        '$1.5000/hour'

        >>> format_currency(5000, monthly=True)
        '$5,000.00/month'
    """
    if hourly:
        # Hourly rates use 4 decimal precision
        formatted = f"${amount:.4f}/hour"
    elif monthly:
        # Monthly amounts use 2 decimals with thousands separator
        formatted = f"${amount:,.2f}/month"
    else:
        # Default: 2 decimals with thousands separator
        formatted = f"${amount:,.2f}"

    return formatted


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format a percentage value with consistent precision.

    Args:
        value: The numeric percentage value (e.g., 85.5 for 85.5%)
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted percentage string with '%' symbol

    Examples:
        >>> format_percentage(85.5)
        '85.50%'

        >>> format_percentage(100.0, decimals=0)
        '100%'
    """
    return f"{value:.{decimals}f}%"
