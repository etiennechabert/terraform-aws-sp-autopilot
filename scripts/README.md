# Utility Scripts

## discover_services.py

Discovers all AWS services in your account that have Savings Plans coverage data.

### Purpose

Use this script to identify which AWS services appear in your Cost Explorer data. This helps you customize the service constants in `lambda/shared/spending_analyzer.py` for your specific AWS usage patterns.

### Usage

```bash
# Set AWS credentials
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret

# Run the discovery script
python3 scripts/discover_services.py
```

Or with assume role:
```bash
export MANAGEMENT_ACCOUNT_ROLE_ARN=arn:aws:iam::123456789012:role/YourRole
python3 scripts/discover_services.py
```

### Output

The script will:
1. Query Cost Explorer for the last 30 days
2. Aggregate spending by service
3. Display a table of all services with SP coverage data
4. Generate Python constants you can copy to `spending_analyzer.py`
5. Auto-categorize services into Compute/Database/SageMaker

### Example Output

```
==========================================================================================
ALL SERVICES WITH SAVINGS PLANS COVERAGE DATA (sorted by spend)
==========================================================================================

Service Name                                                  Total Spend      Covered      %
------------------------------------------------------------------------------------------
Amazon Elastic Container Service                             $   22933.56 $   19800.11  86.3%
Amazon Relational Database Service                           $   15695.70 $       0.00   0.0%
Amazon Elastic Compute Cloud - Compute                       $    3380.22 $    3179.44  94.1%
...

==========================================================================================
PYTHON CONSTANTS FORMAT
==========================================================================================

# Compute SP Services:
COMPUTE_SP_SERVICES = [
    "Amazon Elastic Container Service",
    "Amazon Elastic Compute Cloud - Compute",
    "AWS Lambda",
]
```

### Next Steps

1. Copy the service names from the output
2. Update the constants in `lambda/shared/spending_analyzer.py`
3. Uncomment any commented services that appear in your data
4. Test your configuration

### Requirements

- AWS credentials with Cost Explorer API access
- At least 30 days of usage data in your AWS account
- Python 3.9+
