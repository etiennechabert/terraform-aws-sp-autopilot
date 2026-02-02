terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 6.30" # Allow v5.x and v6.0-6.29 (excluding buggy 6.30.x)
    }
  }
}
