# Release Process

This document describes the release process for the AWS Savings Plans Autopilot Terraform module.

## Versioning

This module follows [semantic versioning](https://semver.org/) (SemVer):

- **MAJOR** version (v1.0.0 → v2.0.0): Breaking changes that require user action
  - Examples: Removing variables, changing variable types, renaming resources
- **MINOR** version (v1.0.0 → v1.1.0): New features that are backward compatible
  - Examples: Adding new variables with defaults, new outputs, enhanced functionality
- **PATCH** version (v1.0.0 → v1.0.1): Bug fixes and minor improvements
  - Examples: Fixing bugs, updating documentation, dependency updates

## Release Workflow

Releases are fully automated via GitHub Actions. When you push a version tag, the workflow:

1. ✅ **Validates** the Terraform configuration
2. 📝 **Generates** a changelog from commit messages
3. 📦 **Creates** a GitHub release with installation instructions
4. 🔄 **Syncs** automatically to the Terraform Registry

## Creating a Release

### 1. Prepare the Release

Ensure all changes are merged to the `main` branch:

```bash
git checkout main
git pull origin main
```

Verify the module is valid:

```bash
terraform init
terraform validate
terraform fmt -check -recursive .
```

### 2. Create and Push the Version Tag

Create an annotated tag following the `vMAJOR.MINOR.PATCH` format:

```bash
# For a new feature (minor version bump)
git tag -a v1.1.0 -m "Release v1.1.0: Add Database Savings Plans support"

# For a bug fix (patch version bump)
git tag -a v1.0.1 -m "Release v1.0.1: Fix coverage calculation bug"

# For breaking changes (major version bump)
git tag -a v2.0.0 -m "Release v2.0.0: Restructure module interface"
```

Push the tag to trigger the release workflow:

```bash
git push origin v1.1.0
```

### 3. Monitor the Release

1. Navigate to **Actions** tab in GitHub
2. Watch the **Release** workflow run
3. Verify all steps complete successfully
4. Check the **Releases** page for the new release

### 4. Verify Terraform Registry Sync

The Terraform Registry automatically syncs when a new tag is pushed:

1. Visit https://registry.terraform.io/modules/etiennechabert/sp-autopilot/aws
2. Verify the new version appears (typically within 5-10 minutes)
3. Confirm the documentation is updated

## Tag Format Requirements

**Valid formats:**
- ✅ `v1.0.0` — Standard release
- ✅ `v1.2.3` — Standard release
- ✅ `v2.0.0` — Major version

**Invalid formats:**
- ❌ `1.0.0` — Missing 'v' prefix
- ❌ `v1.0` — Missing patch version
- ❌ `v1.0.0-beta` — Pre-release tags (not automatically released)

## Commit Message Best Practices

The changelog is generated from commit messages. Use conventional commit format:

```
feat: add database savings plans support
fix: correct coverage calculation for expiring plans
docs: update README with new examples
chore: update dependencies
```

**Commit prefixes:**
- `feat:` — New features (→ "🚀 Features" section)
- `fix:` — Bug fixes (→ "🐛 Bug Fixes" section)
- `docs:` — Documentation (→ "📚 Documentation" section)
- `chore:` — Maintenance (→ "🔧 Maintenance" section)

## Hotfix Process

For urgent bug fixes that need immediate release:

1. Create a branch from the latest release tag:
   ```bash
   git checkout -b hotfix/1.0.1 v1.0.0
   ```

2. Make the fix and commit:
   ```bash
   git commit -m "fix: critical bug in purchaser lambda"
   ```

3. Merge to main and tag:
   ```bash
   git checkout main
   git merge --no-ff hotfix/1.0.1
   git tag -a v1.0.1 -m "Release v1.0.1: Critical purchaser bug fix"
   git push origin main v1.0.1
   ```

## Pre-Release Versions

For beta or release candidate versions, use pre-release tags:

```bash
# These do NOT trigger automatic releases
git tag v2.0.0-beta.1
git tag v2.0.0-rc.1
```

To create a GitHub release for a pre-release version, manually create it in the GitHub UI and mark as "pre-release".

## Rollback Process

If a release has critical issues:

1. **Do not delete the tag** — This breaks Terraform Registry references
2. **Create a new patch release** with the fix
3. **Update documentation** to note the issue in the previous version

Example:
```bash
# If v1.1.0 has a critical bug
git revert <bad-commit>
git commit -m "fix: revert breaking change from v1.1.0"
git tag -a v1.1.1 -m "Release v1.1.1: Fix critical issue from v1.1.0"
git push origin main v1.1.1
```

## Release Checklist

Before creating a release, verify:

- [ ] All tests pass
- [ ] `terraform validate` succeeds
- [ ] `terraform fmt -check` passes
- [ ] CHANGELOG or commit messages clearly describe changes
- [ ] Breaking changes are documented in README
- [ ] Version bump follows semantic versioning rules
- [ ] Tag format is `vMAJOR.MINOR.PATCH`

## Terraform Registry Integration

The module is published at: https://registry.terraform.io/modules/etiennechabert/sp-autopilot/aws

**Automatic sync occurs when:**
- A new tag matching `v[0-9]+.[0-9]+.[0-9]+` is pushed
- The GitHub release is created successfully
- The repository is public and webhook is configured

**Registry updates include:**
- Module version
- README documentation
- Input variables (from variables.tf)
- Output values (from outputs.tf)
- Resource documentation

## Support

For questions about the release process:
- Open an issue on GitHub
- Contact the maintainers

---

**Last Updated:** 2026-01-14
