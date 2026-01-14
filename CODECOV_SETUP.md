# Codecov Setup Instructions

To enable dynamic code coverage badges, you need to connect your repository to Codecov.

## Steps to Enable Codecov

### 1. Sign Up / Log In to Codecov

Visit [codecov.io](https://codecov.io) and sign in with your GitHub account.

### 2. Add Your Repository

1. Go to https://app.codecov.io/gh/etiennechabert
2. Click "Add new repository"
3. Find and enable `terraform-aws-sp-autopilot`

### 3. Get Your Upload Token (Optional)

For public repositories, **no token is required**. The GitHub Actions workflow will work automatically.

For private repositories:
1. Go to your repository settings in Codecov
2. Copy the upload token
3. Add it to your GitHub repository secrets:
   - Go to: `Settings` → `Secrets and variables` → `Actions`
   - Click "New repository secret"
   - Name: `CODECOV_TOKEN`
   - Value: [paste your token]

### 4. Update Workflow (Already Done)

The `.github/workflows/tests.yml` has been updated to upload coverage reports to Codecov.

### 5. Wait for Next CI Run

After the next push to `main` or `develop`, Codecov will:
- ✅ Receive coverage data
- ✅ Generate coverage reports
- ✅ Update the badge automatically

## What You Get

- **Dynamic Badge**: Updates automatically with each CI run
- **Coverage Reports**: Detailed line-by-line coverage at codecov.io
- **PR Comments**: Codecov bot comments on PRs with coverage changes
- **Coverage Trends**: Track coverage over time
- **Branch Comparison**: Compare coverage across branches

## Verify It's Working

After the next CI run, visit:
https://app.codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot

You should see your coverage reports and graphs.

## Badge in README

The README now uses a dynamic Codecov badge:

```markdown
[![codecov](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot/branch/main/graph/badge.svg)](https://codecov.io/gh/etiennechabert/terraform-aws-sp-autopilot)
```

This badge will:
- ✅ Show real-time coverage percentage from latest CI run
- ✅ Update automatically with each push
- ✅ Link to detailed coverage reports
- ✅ Work for free on public repositories

---

**Note**: Since this is a public repository, no token configuration is needed. The integration will work automatically once you enable the repository on Codecov.
