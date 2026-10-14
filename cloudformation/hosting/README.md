# Hosting the CloudFormation template

The README's Launch Stack link opens CloudFormation's quick-create page on the latest release's template. CloudFormation only takes a quick-create template [stored in S3](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-using-console-create-stack-template.html), so each release uploads its `sp-autopilot.yaml` to a public bucket. The Lambda packages stay on the GitHub release: the template downloads them from there and checks their SHA-256s. See [the design](../DESIGN.md), §5.

Until the steps below are done, every release still attaches a deployable `sp-autopilot.yaml`, and `release.yml`'s `publish-template` job is skipped.

## Turning it on

1. **Deploy the hosting stack** once, in the AWS account that should host the template. Any region works: a console in any region reads a template from a bucket in another.

   ```bash
   aws cloudformation deploy --region eu-central-1 --stack-name sp-autopilot-template-hosting --template-file cloudformation/hosting/template-hosting.yaml --capabilities CAPABILITY_IAM --parameter-overrides BucketName=sp-autopilot-templates
   ```

   Add `CreateGitHubOidcProvider=no` if the account already has the `token.actions.githubusercontent.com` OIDC provider, for instance because cost-goblin's hosting stack is in the same account. If the account blocks public access at the account level, allow it for this bucket: its `templates/` folder must be publicly readable.

2. **Create the `release` environment and keep it protected**, under GitHub → Settings → Environments: a required reviewer, and deployment branches and tags limited to `main` and `v*` tags. The upload role trusts any job that runs in that environment, so without these protections a workflow on any branch that declares `environment: release` could replace the template users' consoles load.

   Then **set the repository variables** from the stack's outputs, under GitHub → Settings → Secrets and variables → Actions → Variables. They are identifiers, not secrets: no AWS key is stored anywhere, as the job exchanges GitHub's per-run OIDC token for 15-minute credentials:

   | Variable | Output |
   |---|---|
   | `TEMPLATE_BUCKET` | `TemplateBucket` |
   | `TEMPLATE_ROLE_ARN` | `ReleaseRoleArn` |
   | `TEMPLATE_REGION` | `TemplateRegion` |

3. **Check the README's Launch Stack link** points at the `TemplateBaseUrl` output, followed by `/latest/sp-autopilot.yaml`.

The next release tag then uploads `templates/<tag>/sp-autopilot.yaml` and `templates/latest/sp-autopilot.yaml`, which the Launch Stack link opens.

## What the release job can do

`publish-template` runs in the `release` environment with only `id-token: write`, after you approve it. It exchanges GitHub's OIDC token for 15-minute credentials of `ReleaseUploadRole`, which trusts only this repository's `release` environment and can only write under `templates/` in this bucket. It runs no repository code: it downloads the `sp-autopilot.yaml` the release job just attached and copies it. `cloudformation/tests/test_release_workflow.py` pins all of this.
