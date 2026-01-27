# S3 bucket for report storage

# checkov:skip=CKV_AWS_18:S3 access logging is optional via s3_access_logging variable (disabled by default for cost optimization)
resource "aws_s3_bucket" "reports" {
  bucket = "${local.module_name}-reports-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reports"
    }
  )
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  count = local.s3_encryption_enabled ? 1 : 0

  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.s3_kms_key != null ? "aws:kms" : "AES256"
      kms_master_key_id = local.s3_kms_key # Only used when sse_algorithm is "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "reports_https_only" {
  bucket = aws_s3_bucket.reports.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPSRequests"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.reports.arn,
          "${aws_s3_bucket.reports.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# S3 bucket for access logs (only created if logging is enabled)
resource "aws_s3_bucket" "reports_logs" {
  count  = var.s3_access_logging.enabled ? 1 : 0
  bucket = "${local.module_name}-reports-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.module_name}-reports-logs"
    }
  )
}

resource "aws_s3_bucket_public_access_block" "reports_logs" {
  count  = var.s3_access_logging.enabled ? 1 : 0
  bucket = aws_s3_bucket.reports_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports_logs" {
  count  = var.s3_access_logging.enabled ? 1 : 0
  bucket = aws_s3_bucket.reports_logs[0].id

  rule {
    id     = "cleanup-old-logs"
    status = "Enabled"

    expiration {
      days = var.s3_access_logging.expiration_days
    }
  }
}

resource "aws_s3_bucket_logging" "reports" {
  count         = var.s3_access_logging.enabled ? 1 : 0
  bucket        = aws_s3_bucket.reports.id
  target_bucket = aws_s3_bucket.reports_logs[0].id
  target_prefix = var.s3_access_logging.target_prefix
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "cleanup-old-reports"
    status = "Enabled"

    # Transition to cheaper storage after configured days
    transition {
      days          = local.s3_lifecycle_transition_ia_days
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after configured days
    transition {
      days          = local.s3_lifecycle_transition_glacier_days
      storage_class = "GLACIER"
    }

    # Delete reports after configured days
    expiration {
      days = local.s3_lifecycle_expiration_days
    }

    # Clean up old versions
    noncurrent_version_expiration {
      noncurrent_days = local.s3_lifecycle_noncurrent_expiration_days
    }
  }
}
