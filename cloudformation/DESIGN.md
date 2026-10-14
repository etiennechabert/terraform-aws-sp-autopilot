# CloudFormation edition: design

Status: **implemented**. The stack, its packaging, the release assets and the hosting template are in this repository. The Launch Stack link works once the hosting stack is deployed and its repository variables are set ([hosting/README.md](hosting/README.md)).

## 1. Goal

Let someone who doesn't use Terraform run SP Autopilot from one CloudFormation stack, launched from a link in the README, with the same behaviour as the Terraform module. The approach follows [cost-goblin's one-click AWS setup](https://github.com/etiennechabert/cost-goblin/blob/main/docs/aws-one-click-setup-design.md): a template people review and create in their own console, published per release to a public S3 bucket so a quick-create link can open it.

## 2. What the stack creates

The module's resources, one for one:

| Module file | Stack resources |
|---|---|
| `sns.tf` | `NotificationsTopic`, `EmailSubscription` |
| `sqs.tf` | `PurchaseIntentsQueue`, `PurchaseIntentsDlq`, `PurchaseIntentsQueuePolicy`, `DlqDepthAlarm` |
| `s3.tf` | `ReportsBucket` and its policy; `ReportsLogsBucket` and its policy when access logging is on |
| `lambda.tf`, `iam.tf`, `cloudwatch.tf`, `eventbridge.tf` | per function: log group, role with the same inline policies, function, EventBridge rule and permission, error alarm |

Names, IAM actions, Lambda environment variables, defaults, runtime and log retention match the module. `tests/test_terraform_parity.py` reads the `.tf` files and fails when either side changes alone.

On top of that, four resources get the Lambda code into the stack's region (§4): `LambdaCodeBucket` and its policy, and `CodeCopierFunction` with its role and log group, run through the `LambdaCode` custom resource.

## 3. Parameters

CloudFormation parameters are flat strings, so the module's nested inputs become one parameter each, grouped in the console in the README's order. Where the stack differs:

- **The purchaser is off by default.** The module enables all three functions. A stack someone creates from a link shouldn't buy Savings Plans, which can't be cancelled, before they have seen what the scheduler queues. Its defaults are the README's *Recommended Rollout* step 2.
- **Compute defaults to `no_upfront_one_year`**, the README's suggested start. The module has no default.
- **One email address.** CloudFormation can't loop over a list without the `AWS::LanguageExtensions` transform; more subscriptions can be added to the topic.
- **One memory size, timeout and error-alarm switch** for all three functions, instead of one per function.
- **Two management-account roles**, read-only for the scheduler and reporter and one for the purchaser, as the README's *AWS Organizations Setup* describes, instead of one per function.
- **No `tags` input.** Stack tags propagate to the resources. Purchased plans get the module's `ManagedBy` and `Module` tags.
- **Constraints the module doesn't check:** S3 refuses a Standard-IA transition under 30 days, and `NamePrefix` is capped at 37 characters so the bucket names fit. Rules the console can't express (one lookback longer than the other, for instance) are still checked by the Lambdas at run time, as they are for the module.

Plan types keep the module's values (`no_upfront_one_year`...). Mapping keys can't contain underscores, so Conditions turn them into term and payment option.

## 4. Lambda code in any region

The Lambdas are Python packages of 50 to 90 KB, too many files for inline `ZipFile` code, and Lambda only reads code from an S3 bucket in its own region. Options considered:

| Option | Why not |
|---|---|
| One region only, like cost-goblin's us-east-1 stack | Savings Plans and Cost Explorer are global, but organizations that keep workloads in one region by SCP couldn't deploy it. |
| A public bucket per region, filled by the release | Fifteen-plus buckets and uploads to keep in step; new regions need setup. |
| AWS Serverless Application Repository | Limits the resource types, and adds a publishing step outside GitHub. |
| **Copy into a bucket the stack owns (chosen)** | One inline function in the user's account, the pattern AWS Quick Starts use. |

How it works:

- The release attaches `sp-autopilot-{scheduler,purchaser,reporter}.zip` to the GitHub release, with the same files as the module's `archive_file`s. `build.py` writes them reproducibly: fixed timestamps and order.
- `build.py` writes the download URL (the release's assets) and each zip's SHA-256 into the template's `Release` mapping. The stack's `CodeCopierFunction` downloads each zip over HTTPS, refuses one whose SHA-256 differs, then writes them to `LambdaCodeBucket`. A replaced release asset can't reach a function, and nothing is written unless all three check out.
- Keys are named after a hash of all three checksums. A new release copies to new keys, and the functions' `S3Key` changes, which is what makes CloudFormation update their code. CloudFormation's cleanup of the previous `LambdaCode` then deletes only the old keys. With per-package keys, an unchanged package would share its key with the old release and be deleted.
- The download URL lives in the mapping, not a parameter. On a stack update the console keeps previous parameter values, so a parameter would keep pointing at the old release while the checksums move on.
- Deleting the stack deletes the copied keys, then the bucket. A failing delete still answers `SUCCESS`, so cleanup never blocks a stack deletion.
- The copier needs outbound HTTPS to github.com during creates and updates; it runs outside any VPC.

The GitHub release, rather than the hosting bucket, holds the zips, so a release's template works even before hosting exists, and each release has one origin. Self-hosting is a rebuild: `make cfn-package CFN_CODE_SOURCE_URL=https://...` points the template at your copy, with the same checksums.

The repository's `sp-autopilot.yaml` is the source; the release's copy is the deployable one. The `PackagedTemplate` rule makes the source refuse to deploy, with a message saying which file to use.

## 5. Hosting and release

Quick-create links only take a template [stored in S3](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-using-console-create-stack-template.html), as cost-goblin found. The same setup:

- `hosting/template-hosting.yaml`: a bucket whose `templates/` folder is publicly readable, and `ReleaseUploadRole`, which trusts only this repository's `release` environment and can only write under `templates/`.
- `release.yml`: the `release` job runs `build.py` and attaches its output to the release. `publish-template` holds only `id-token: write`, runs no repository code, downloads the template the release just attached and uploads it to `templates/<tag>/` and `templates/latest/`. It is skipped until `TEMPLATE_BUCKET`, `TEMPLATE_ROLE_ARN` and `TEMPLATE_REGION` are set. `tests/test_release_workflow.py` pins this.

## 6. Tests

`make cfn-test`, and the *CloudFormation Template* CI job, which also runs `cfn-lint` on the packaged and hosting templates:

- `test_template.py` evaluates the template (`tests/cfn_eval.py`: Conditions, Rules, `Fn::If`, `Fn::Sub`...) for parameter sets, and checks the resources created, every function's environment against `main.tf`'s logic for each plan type and strategy combination, encryption, logging, the code wiring, IAM scoping and name lengths.
- `test_terraform_parity.py`: IAM actions, environment variable names, defaults, names, runtime and retention, read from the `.tf` files.
- `test_build.py`: the zips match `lambda.tf`'s archives and their handlers import on their own; builds are reproducible; placeholders are all filled.
- `test_code_copier.py` runs the template's inline code with S3 and HTTP faked: copying, checksum refusal, key naming across releases, deletes, malformed requests.

## 7. Open

- **No deployment test.** The stack has been linted and evaluated, not created in an AWS account by CI. The Terratest suite could create it from the CI build in the test account.
- **Alarm notifications and the `aws/sns` key.** The topic defaults to the AWS managed `alias/aws/sns` key, as in the module. CloudWatch alarms can't publish to a topic encrypted with an AWS managed key, so the error and DLQ alarms may not notify until the topic uses a customer managed key. This affects the module the same way and should be settled for both.
