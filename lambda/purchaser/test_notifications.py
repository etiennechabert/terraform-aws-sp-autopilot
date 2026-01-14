"""
Comprehensive unit tests for Slack notification formatting with color-coded severity.

Tests cover format_slack_message() with all severity levels and edge cases.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import notifications


# ============================================================================
# format_slack_message Tests - Severity Levels
# ============================================================================

def test_format_slack_message_success_severity():
    """Test format_slack_message with success severity."""
    subject = "Deployment Successful"
    body_lines = ["Application deployed successfully", "Version: 1.2.3"]

    result = notifications.format_slack_message(subject, body_lines, severity='success')

    # Verify structure
    assert 'attachments' in result
    assert len(result['attachments']) == 1

    attachment = result['attachments'][0]

    # Verify color code for success (green)
    assert attachment['color'] == '#36a64f'

    # Verify blocks structure
    assert 'blocks' in attachment
    assert len(attachment['blocks']) == 2

    # Verify emoji prepended to subject
    header_block = attachment['blocks'][0]
    assert header_block['type'] == 'header'
    assert '✅' in header_block['text']['text']
    assert subject in header_block['text']['text']
    assert header_block['text']['emoji'] is True

    # Verify body content
    section_block = attachment['blocks'][1]
    assert section_block['type'] == 'section'
    assert section_block['text']['type'] == 'mrkdwn'
    assert body_lines[0] in section_block['text']['text']
    assert body_lines[1] in section_block['text']['text']


def test_format_slack_message_warning_severity():
    """Test format_slack_message with warning severity."""
    subject = "High Usage Alert"
    body_lines = ["CPU usage at 85%", "Consider scaling"]

    result = notifications.format_slack_message(subject, body_lines, severity='warning')

    attachment = result['attachments'][0]

    # Verify color code for warning (orange)
    assert attachment['color'] == '#ff9900'

    # Verify warning emoji
    header_block = attachment['blocks'][0]
    assert '⚠️' in header_block['text']['text']
    assert subject in header_block['text']['text']


def test_format_slack_message_error_severity():
    """Test format_slack_message with error severity."""
    subject = "Deployment Failed"
    body_lines = ["Error: Connection timeout", "Rollback initiated"]

    result = notifications.format_slack_message(subject, body_lines, severity='error')

    attachment = result['attachments'][0]

    # Verify color code for error (red)
    assert attachment['color'] == '#ff0000'

    # Verify error emoji
    header_block = attachment['blocks'][0]
    assert '❌' in header_block['text']['text']
    assert subject in header_block['text']['text']


def test_format_slack_message_info_severity():
    """Test format_slack_message with info severity."""
    subject = "Scheduled Maintenance"
    body_lines = ["Maintenance window: 2AM-4AM", "Expected downtime: 2 hours"]

    result = notifications.format_slack_message(subject, body_lines, severity='info')

    attachment = result['attachments'][0]

    # Verify color code for info (blue)
    assert attachment['color'] == '#0078D4'

    # Verify info emoji
    header_block = attachment['blocks'][0]
    assert 'ℹ️' in header_block['text']['text']
    assert subject in header_block['text']['text']


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

def test_format_slack_message_no_severity_defaults_to_info():
    """Test format_slack_message without severity parameter defaults to info."""
    subject = "Default Message"
    body_lines = ["This message has no severity specified"]

    # Call without severity parameter
    result = notifications.format_slack_message(subject, body_lines)

    attachment = result['attachments'][0]

    # Should default to info severity (blue color, info emoji)
    assert attachment['color'] == '#0078D4'

    header_block = attachment['blocks'][0]
    assert 'ℹ️' in header_block['text']['text']


def test_format_slack_message_invalid_severity_defaults_to_info():
    """Test format_slack_message with invalid severity falls back to info."""
    subject = "Unknown Severity"
    body_lines = ["Testing invalid severity level"]

    # Call with invalid severity
    result = notifications.format_slack_message(subject, body_lines, severity='critical')

    attachment = result['attachments'][0]

    # Should fall back to info severity
    assert attachment['color'] == '#0078D4'

    header_block = attachment['blocks'][0]
    assert 'ℹ️' in header_block['text']['text']


# ============================================================================
# Message Structure Tests
# ============================================================================

def test_format_slack_message_blocks_structure():
    """Test that message blocks are correctly structured."""
    subject = "Test Structure"
    body_lines = ["Line 1", "Line 2", "Line 3"]

    result = notifications.format_slack_message(subject, body_lines, severity='success')

    attachment = result['attachments'][0]
    blocks = attachment['blocks']

    # Verify header block structure
    header = blocks[0]
    assert header['type'] == 'header'
    assert 'text' in header
    assert header['text']['type'] == 'plain_text'
    assert header['text']['emoji'] is True

    # Verify section block structure
    section = blocks[1]
    assert section['type'] == 'section'
    assert 'text' in section
    assert section['text']['type'] == 'mrkdwn'

    # Verify all body lines are joined with newlines
    body_text = section['text']['text']
    for line in body_lines:
        assert line in body_text


def test_format_slack_message_empty_body_lines():
    """Test format_slack_message with empty body lines."""
    subject = "Empty Body"
    body_lines = []

    result = notifications.format_slack_message(subject, body_lines, severity='info')

    attachment = result['attachments'][0]

    # Should still have proper structure
    assert attachment['color'] == '#0078D4'
    assert len(attachment['blocks']) == 2

    # Section text should be empty string
    section_block = attachment['blocks'][1]
    assert section_block['text']['text'] == ''


def test_format_slack_message_single_body_line():
    """Test format_slack_message with single body line."""
    subject = "Single Line"
    body_lines = ["Only one line of content"]

    result = notifications.format_slack_message(subject, body_lines, severity='warning')

    attachment = result['attachments'][0]
    section_block = attachment['blocks'][1]

    assert section_block['text']['text'] == body_lines[0]


def test_format_slack_message_multiple_body_lines():
    """Test format_slack_message with multiple body lines joined correctly."""
    subject = "Multiple Lines"
    body_lines = ["First line", "Second line", "Third line", "Fourth line"]

    result = notifications.format_slack_message(subject, body_lines, severity='error')

    attachment = result['attachments'][0]
    section_block = attachment['blocks'][1]

    # Verify lines are joined with newlines
    expected_text = "\n".join(body_lines)
    assert section_block['text']['text'] == expected_text


# ============================================================================
# Color Code Verification Tests
# ============================================================================

def test_all_severity_color_codes():
    """Test that all severity levels have correct color codes."""
    test_cases = [
        ('success', '#36a64f'),  # Green
        ('warning', '#ff9900'),  # Orange
        ('error', '#ff0000'),    # Red
        ('info', '#0078D4')      # Blue
    ]

    for severity, expected_color in test_cases:
        result = notifications.format_slack_message(
            "Test",
            ["Test message"],
            severity=severity
        )

        assert result['attachments'][0]['color'] == expected_color, \
            f"Color mismatch for severity '{severity}'"


# ============================================================================
# Emoji Verification Tests
# ============================================================================

def test_all_severity_emoji_indicators():
    """Test that all severity levels have correct emoji indicators."""
    test_cases = [
        ('success', '✅'),
        ('warning', '⚠️'),
        ('error', '❌'),
        ('info', 'ℹ️')
    ]

    subject = "Test Subject"

    for severity, expected_emoji in test_cases:
        result = notifications.format_slack_message(
            subject,
            ["Test message"],
            severity=severity
        )

        header_text = result['attachments'][0]['blocks'][0]['text']['text']

        assert expected_emoji in header_text, \
            f"Emoji '{expected_emoji}' not found for severity '{severity}'"
        assert subject in header_text, \
            f"Subject not found in header for severity '{severity}'"


# ============================================================================
# Edge Cases
# ============================================================================

def test_format_slack_message_special_characters_in_subject():
    """Test format_slack_message handles special characters in subject."""
    subject = "Alert: <System> & \"Critical\" Issue!"
    body_lines = ["Special characters in subject"]

    result = notifications.format_slack_message(subject, body_lines, severity='error')

    header_text = result['attachments'][0]['blocks'][0]['text']['text']
    assert subject in header_text


def test_format_slack_message_special_characters_in_body():
    """Test format_slack_message handles special characters in body."""
    subject = "Test"
    body_lines = [
        "Line with <tags>",
        "Line with & ampersand",
        "Line with \"quotes\"",
        "Line with 'apostrophes'"
    ]

    result = notifications.format_slack_message(subject, body_lines, severity='info')

    section_text = result['attachments'][0]['blocks'][1]['text']['text']
    for line in body_lines:
        assert line in section_text


def test_format_slack_message_unicode_in_content():
    """Test format_slack_message handles unicode characters."""
    subject = "Unicode Test: 日本語"
    body_lines = ["Content with émojis 🚀", "Greek: Ω", "Math: ∑"]

    result = notifications.format_slack_message(subject, body_lines, severity='success')

    header_text = result['attachments'][0]['blocks'][0]['text']['text']
    section_text = result['attachments'][0]['blocks'][1]['text']['text']

    assert "日本語" in header_text
    assert "🚀" in section_text
    assert "Ω" in section_text
    assert "∑" in section_text
