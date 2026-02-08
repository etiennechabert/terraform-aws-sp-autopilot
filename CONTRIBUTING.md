# Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork and set up the dev environment — see [DEVELOPMENT.md](DEVELOPMENT.md)
3. Create a feature branch from `main`

## Branch Naming

- `feature/` — New features or enhancements
- `fix/` — Bug fixes
- `docs/` — Documentation updates
- `refactor/` — Code refactoring without behavior changes
- `test/` — Adding or updating tests
- `chore/` — Maintenance tasks, dependency updates

## Commit Message Guidelines

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <subject>
```

| Type | Description | Version Impact |
|------|-------------|----------------|
| `feat` | New feature | Minor (1.x.0) |
| `fix` | Bug fix | Patch (1.0.x) |
| `docs` | Documentation only | No bump |
| `refactor` | Refactoring | No bump |
| `test` | Tests | No bump |
| `chore` | Maintenance | No bump |

For breaking changes, add `!` after type and include a `BREAKING CHANGE:` footer:

```
feat(api)!: change coverage calculation to exclude expiring plans

BREAKING CHANGE: Coverage calculation now excludes expiring plans.
```

Optional scopes: `scheduler`, `purchaser`, `terraform`, `ci`, `docs`, `database-sp`, `compute-sp`

## Pull Request Process

1. Sync with upstream: `git fetch origin && git rebase origin/main`
2. Run validations locally (see [DEVELOPMENT.md](DEVELOPMENT.md))
3. Push and open a PR against `main`
4. PR title should use conventional commit format (e.g., `feat(scheduler): add Database SP support`)
5. Include: summary, motivation, testing performed, breaking changes, related issues

### Automated PR Checks

| Check | Description |
|-------|-------------|
| **Terraform Validation** | `terraform fmt -check` and `terraform validate` |
| **Security Scan** | tfsec for HIGH/CRITICAL issues |
| **Lambda Tests** | pytest with coverage |

### Review Process

1. At least one maintainer must approve
2. Address all review comments
3. All automated checks must pass

## Release Process

Releases are automated via [Release Please](https://github.com/googleapis/release-please):

1. Commits to `main` trigger Release Please
2. A Release PR is created/updated with version bump and changelog
3. Merging the Release PR creates a GitHub Release with git tags (`v1.2.3`, `v1.2`, `v1`)

```hcl
module "savings_plans" {
  source = "github.com/etiennechabert/terraform-aws-sp-autopilot?ref=v1.2.3"
}
```
