## Description

<!-- Describe your changes in detail -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Test improvements

## Testing Checklist

<!-- ALL Lambda test changes MUST comply with TESTING.md guidelines -->

**⚠️ MANDATORY: Have you read [TESTING.md](../TESTING.md)?**
- [ ] Yes, I have read and understand the testing guidelines

**For Lambda changes, verify:**
- [ ] All tests call `handler.handler(event, context)` as entry point
- [ ] Only AWS client responses are mocked (no internal functions or shared modules)
- [ ] Using `aws_mock_builder` for AWS response structures
- [ ] Verified behavior through handler outputs and AWS call assertions
- [ ] Tests exercise real code paths (deleting used code breaks tests, deleting unused code doesn't)
- [ ] Coverage meets minimum 80% threshold

**General testing:**
- [ ] Added tests for new functionality
- [ ] Updated tests for modified functionality
- [ ] All tests pass locally
- [ ] No decrease in code coverage

## Checklist

- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (if applicable)
- [ ] No new warnings generated
- [ ] Dependent changes merged and published

## Related Issues

<!-- Link to related issues using #issue_number -->

Fixes #

## Additional Notes

<!-- Any additional information that reviewers should know -->
