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

## Checklist

- [ ] Self-review completed
- [ ] Tests pass locally (run `pytest` in lambda directory)
- [ ] For Lambda changes: Followed [TESTING.md](../TESTING.md) guidelines:
  - Tests call `handler.handler()` as entry point (not internal functions)
  - Only AWS client responses are mocked (not shared modules or internal code)

## Related Issues

<!-- Link to related issues using #issue_number -->

Fixes #

## Additional Notes

<!-- Any additional information that reviewers should know -->
