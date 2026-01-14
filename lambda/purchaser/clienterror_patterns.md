# ClientError Handling Patterns - Purchaser Lambda

## Overview
Analysis of all ClientError exception handling in `lambda/purchaser/handler.py`

## Pattern Summary
- **Total ClientError handlers**: 11
- **Error extraction pattern**: `e.response.get('Error', {}).get('Code', 'Unknown')`
- **Common actions**: Log error, re-raise (except in error paths and batch processing)

---

## Detailed Patterns

### 1. get_assumed_role_session() - Lines 71-75
**Context**: STS AssumeRole operation

```python
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
    error_message = e.response.get('Error', {}).get('Message', str(e))
    logger.error(f"Failed to assume role {role_arn} - Code: {error_code}, Message: {error_message}")
    raise
```

**Pattern**:
- ✅ Extracts error code
- ✅ Extracts error message
- ✅ Logs with context (role ARN, code, message)
- ✅ Re-raises exception

**Possible Errors**:
- `AccessDenied` - Insufficient permissions
- `InvalidIdentityToken` - Invalid credentials
- `RegionDisabledException` - STS not available in region

---

### 2. handler() - Lines 135-141
**Context**: Client initialization with assume role

```python
except ClientError as e:
    error_msg = f"Failed to initialize AWS clients: {str(e)}"
    if config.get('management_account_role_arn'):
        error_msg = f"Failed to assume role {config['management_account_role_arn']}: {str(e)}"
    logger.error(error_msg, exc_info=True)
    send_error_email(error_msg)
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message separately
- ✅ Constructs context-aware error message
- ✅ Logs with full stack trace (exc_info=True)
- ✅ Sends error notification email
- ✅ Re-raises exception

**Possible Errors**:
- Same as #1 (STS errors from get_assumed_role_session)

---

### 3. receive_messages() - Lines 222-224
**Context**: SQS ReceiveMessage operation

```python
except ClientError as e:
    logger.error(f"Failed to receive messages: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- `QueueDoesNotExist` - Queue deleted or wrong URL
- `AccessDenied` - Insufficient SQS permissions
- `OverLimit` - Too many in-flight messages

---

### 4. get_current_coverage() - Lines 261-263
**Context**: Coverage calculation orchestration

```python
except ClientError as e:
    logger.error(f"Failed to calculate coverage: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- Propagates errors from get_ce_coverage() or get_expiring_plans()
- See #5 and #6 for specific errors

---

### 5. get_ce_coverage() - Lines 315-317
**Context**: Cost Explorer GetSavingsPlansCoverage operation

```python
except ClientError as e:
    logger.error(f"Failed to get Cost Explorer coverage: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- `DataUnavailableException` - Coverage data not yet available
- `LimitExceededException` - API rate limit
- `InvalidParameterException` - Invalid date range or parameters
- `AccessDeniedException` - Insufficient CE permissions

---

### 6. get_expiring_plans() - Lines 358-360
**Context**: Savings Plans DescribeSavingsPlans operation

```python
except ClientError as e:
    logger.error(f"Failed to get Savings Plans: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- `ValidationException` - Invalid filter parameters
- `InternalServerException` - AWS service error
- `ResourceNotFoundException` - No plans found (rare, returns empty list)
- `AccessDeniedException` - Insufficient Savings Plans permissions

---

### 7. process_purchase_messages() - Lines 466-473
**Context**: Purchase processing loop (batch operation)

```python
except ClientError as e:
    logger.error(f"Failed to process purchase: {str(e)}")
    results['failed'].append({
        'intent': purchase_intent if 'purchase_intent' in locals() else {},
        'error': str(e)
    })
    results['failed_count'] += 1
    # Message stays in queue for retry
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error
- ✅ Records failure in results
- ✅ Increments failed count
- ❌ Does NOT re-raise (allows batch processing to continue)
- ✅ Leaves message in queue for retry

**Special Behavior**:
- Graceful degradation - one failure doesn't stop entire batch
- Message visibility timeout controls retry timing

**Possible Errors**:
- Propagates from execute_purchase() - see #8

---

### 8. execute_purchase() - Lines 587-591
**Context**: Savings Plans CreateSavingsPlan operation

```python
except ClientError as e:
    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
    error_message = e.response.get('Error', {}).get('Message', str(e))
    logger.error(f"CreateSavingsPlan failed - Code: {error_code}, Message: {error_message}")
    raise
```

**Pattern**:
- ✅ Extracts error code
- ✅ Extracts error message
- ✅ Logs with context (code, message)
- ✅ Re-raises exception

**Possible Errors**:
- `ValidationException` - Invalid offering ID or commitment
- `InternalServerException` - AWS service error
- `ResourceNotFoundException` - Offering not found or expired
- `ServiceQuotaExceededException` - Too many active plans
- `InvalidParameterException` - Invalid payment option or term

---

### 9. delete_message() - Lines 650-652
**Context**: SQS DeleteMessage operation

```python
except ClientError as e:
    logger.error(f"Failed to delete message: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- `InvalidIdFormat` - Malformed receipt handle
- `ReceiptHandleIsInvalid` - Receipt handle expired (>12 hours old)
- `QueueDoesNotExist` - Queue deleted

**Impact**: Message may be reprocessed if delete fails

---

### 10. send_summary_email() - Lines 766-768
**Context**: SNS Publish operation (success notification)

```python
except ClientError as e:
    logger.error(f"Failed to send summary email: {str(e)}")
    raise
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error with context
- ✅ Re-raises exception

**Possible Errors**:
- `NotFound` - Topic ARN invalid or deleted
- `InvalidParameter` - Invalid message format
- `AuthorizationError` - Insufficient SNS permissions
- `EndpointDisabled` - Topic endpoint disabled

---

### 11. send_error_email() - Lines 832-834
**Context**: SNS Publish operation (error notification)

```python
except ClientError as e:
    logger.error(f"Failed to send error notification email: {str(e)}")
    # Don't raise - we're already in error handling, don't want to mask the original error
```

**Pattern**:
- ❌ Does NOT extract error code/message
- ✅ Logs error
- ❌ Does NOT re-raise (in error path)
- ✅ Documented reasoning for not re-raising

**Special Behavior**:
- Prevents masking the original error
- Silent failure acceptable since already in error state

**Possible Errors**:
- Same as #10 (SNS errors)

---

## Pattern Analysis

### Error Code Extraction
**Functions that extract error code**:
- get_assumed_role_session() (#1)
- execute_purchase() (#8)

**Functions that DON'T extract error code**:
- All others (9 out of 11)

**Recommendation**: Standardize on extracting error code/message for better debugging

### Re-raise Behavior
**Always re-raises**:
- #1, #2, #3, #4, #5, #6, #8, #9, #10

**Never re-raises** (by design):
- #7 - Batch processing, allows continuation
- #11 - Error notification path, prevents masking

### Logging Patterns
**With error code extraction**:
```python
error_code = e.response.get('Error', {}).get('Code', 'Unknown')
error_message = e.response.get('Error', {}).get('Message', str(e))
logger.error(f"Operation failed - Code: {error_code}, Message: {error_message}")
```

**Simple string interpolation**:
```python
logger.error(f"Operation failed: {str(e)}")
```

**With stack trace**:
```python
logger.error(error_msg, exc_info=True)  # Only in handler() #2
```

---

## Error Code Reference Needs

Based on the patterns above, documentation should cover:

### STS Errors (Assume Role)
- AccessDenied
- InvalidIdentityToken
- RegionDisabledException

### SQS Errors
- QueueDoesNotExist
- AccessDenied
- OverLimit
- InvalidIdFormat
- ReceiptHandleIsInvalid

### Cost Explorer Errors
- DataUnavailableException
- LimitExceededException
- InvalidParameterException
- AccessDeniedException

### Savings Plans Errors
- ValidationException
- InternalServerException
- ResourceNotFoundException
- ServiceQuotaExceededException
- InvalidParameterException

### SNS Errors
- NotFound
- InvalidParameter
- AuthorizationError
- EndpointDisabled

---

## Recommendations for Error Messages Reference

1. **Group by AWS Service**:
   - STS (AssumeRole)
   - SQS (ReceiveMessage, DeleteMessage)
   - Cost Explorer (GetSavingsPlansCoverage)
   - Savings Plans (DescribeSavingsPlans, CreateSavingsPlan)
   - SNS (Publish)

2. **For Each Error Code Document**:
   - Description of when it occurs
   - Common causes
   - Resolution steps
   - Whether it's retryable
   - Impact on system behavior

3. **Include Context**:
   - Which Lambda function (purchaser)
   - Which operation triggers the error
   - Line numbers for reference

4. **Add Troubleshooting Flow**:
   - Check CloudWatch Logs for error code
   - Look up error code in reference
   - Follow resolution steps
   - Verify IAM permissions if AccessDenied
