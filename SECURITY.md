# Security Policy

## Reporting Vulnerabilities

**Email:** etienne.chabert@gmail.com

Include vulnerability description, reproduction steps, and impact assessment.

## Supported Versions

| Version | Security Updates |
|---------|-----------------|
| 1.x.x (latest) | ✅ Active patching |
| < 1.0.0 | ❌ Upgrade required |

## Key Security Considerations

### Financial Risk Controls

This module can make AWS Savings Plans purchases (financial commitments). Default protections:

- **Dry-run mode enabled by default** - No purchases until you set `dry_run = false`
- **Coverage caps** - Hard limit via `max_coverage_cap` parameter
- **Incremental limits** - Max purchase percentage per run via `max_purchase_percent`

The `savingsplans:CreateSavingsPlan` IAM permission is required for purchases. Review and test recommendations in dry-run mode before enabling purchases.

### Dependency Updates

- **Critical vulnerabilities:** Patched within 7 days
- **High vulnerabilities:** Patched within 30 days

Dependabot monitors Python dependencies (`boto3`, `botocore`).

## Version Pinning

Always pin to a specific version:

```hcl
module "savings_plans" {
  source  = "etiennechabert/sp-autopilot/aws"
  version = "~> 1.0"
}
```

---

**Contact:** etienne.chabert@gmail.com
