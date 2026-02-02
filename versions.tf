terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 6.29" # Allow v5.x and v6.0-6.28 (6.29+ has SQS policy issues)
    }
  }
}
