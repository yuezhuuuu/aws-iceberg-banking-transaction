# AWS Iceberg Banking Transaction Platform

Streaming banking transaction data platform built with AWS, Apache Iceberg, Spark and Terraform.

## Architecture

```
Producer (Python)
    │  generates JSONL locally
    ▼
data/transactions/<date>/transactions_<ts>_<uuid>.jsonl
    │
    ▼ write_to_s3.py
S3 Bucket (Iceberg warehouse)
    │
    ▼ Glue Data Catalog
Iceberg Table (transaction_logs)
    │
    ▼ read_iceberg.py / Spark / Athena
Analytics
```

## Project Structure

```
aws-iceberg-banking-transaction/
├── producer/
│   ├── producer.py            # JSONL transaction generator (local)
│   ├── write_to_s3.py         # Ingest JSONL → Iceberg via PyIceberg
│   ├── read_iceberg.py        # Read Iceberg table (Spark)
│   └── transaction_generator.py
├── config/
│   ├── config.py
│   ├── .dev.env               # Dev credentials (git-ignored)
│   └── .prod.env              # Prod credentials (git-ignored)
├── terraform/
│   ├── main.tf                # Root module — calls storage, catalog, iam modules
│   ├── provider.tf            # AWS provider + S3 remote backend
│   ├── variables.tf
│   ├── locals.tf
│   ├── output.tf              # Aggregates outputs from all modules
│   ├── dev.tfvars
│   ├── prod.tfvars
│   ├── backend-dev.hcl        # Remote state config for dev
│   ├── backend-prod.hcl       # Remote state config for prod
│   ├── modules/
│   │   ├── storage/           # S3 bucket (via terraform-aws-modules/s3-bucket/aws)
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── catalog/           # Glue catalog database (raw resource)
│   │   │   ├── main.tf
│   │   │   ├── variable.tf
│   │   │   └── output.tf
│   │   └── iam/               # IAM user + policy (via terraform-aws-modules/iam/aws)
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── output.tf
│   └── bootstrap/
│       └── main.tf            # One-time: creates state S3 bucket + DynamoDB lock table
│                              # bucket: banking-transaction-platform-20260601-state
└── .github/
    └── workflows/
        ├── terraform-plan.yml # CI: runs on every PR
        ├── deploy-dev.yml     # CD: runs on push to develop
        └── deploy-prod.yml    # CD: runs on push to main
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Poetry
- Terraform >= 1.5
- AWS credentials configured

### Setup

```bash
poetry install
cp config/.dev.env.example config/.dev.env
# fill in AWS credentials and bucket name in config/.dev.env
```

### Run locally

```bash
# Provision AWS infrastructure (dev)
cd terraform
terraform init -backend-config=backend-dev.hcl
terraform apply -var-file=dev.tfvars

# Generate transactions to local JSONL files
poetry run python -m producer.producer

# Ingest JSONL files into Iceberg (S3 + Glue)
poetry run python -m producer.write_to_s3

# Query the Iceberg table
poetry run python -m producer.read_iceberg
```

### Lint / type check / test

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy producer/ config/
poetry run pytest --tb=short -v
```

---

## Branch Strategy

```
feature/*
    │  push
    ▼
develop ──── push ────▶ GitHub Actions: deploy-dev.yml
    │                       └─ terraform apply dev.tfvars
    │                       └─ smoke test (producer → S3 → read)
    │
    │  Pull Request
    ▼
main ──────── push ────▶ GitHub Actions: deploy-prod.yml
                            └─ terraform apply prod.tfvars
                            └─ verify prod Iceberg table
```

PRs to either branch trigger `terraform-plan.yml` (CI checks).

---

## CI/CD Pipeline

### Workflow 1 — `terraform-plan.yml` (CI on every PR)

**Trigger:** `pull_request` to `develop` or `main`

| Job | Runs when | What it does |
|---|---|---|
| `security-scan` | always | Scans PR diff for hardcoded `AKIA…` access keys or raw secret keys. Blocks merge if found. |
| `lint` | always | `ruff check` (lint) + `ruff format --check` (formatting) + `mypy` (type check) |
| `test` | after `lint` passes | `pytest` — uses dummy env vars, no AWS connection required |
| `terraform-plan` | after `security-scan` passes | `terraform fmt -check` + `validate` + `plan` using `backend-dev.hcl` (PR→develop) or `backend-prod.hcl` (PR→main) |

**Job dependency graph:**

```
security-scan ──▶ terraform-plan
lint ────────────▶ test
```

All four jobs must pass before a PR can be merged (configure as required status checks in GitHub branch protection rules).

---

### Workflow 2 — `deploy-dev.yml` (CD to dev)

**Trigger:** `push` to `develop` (i.e. after a feature branch is merged)

#### Job 1 — `terraform-apply-dev`

1. Checkout code
2. Configure AWS credentials (from GitHub Secret `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)
3. `terraform init -backend-config=backend-dev.hcl` — connects to S3 remote state
4. `terraform apply -var-file=dev.tfvars -auto-approve` — creates/updates S3 bucket, Glue database, IAM user
5. `terraform output` — prints resource names (bucket ARN, warehouse path, etc.)

#### Job 2 — `smoke-test` (runs after Job 1)

1. Install Python dependencies via Poetry
2. Run `producer.producer` for 10 seconds at 50 TPS → writes JSONL to `/tmp/smoke-transactions/`
3. Run `producer.write_to_s3` → ingests JSONL into the dev Iceberg table on S3
4. Run `producer.read_iceberg` → reads back from Iceberg to verify the table is healthy

**Full pipeline:**

```
push to develop
    │
    ▼
terraform-apply-dev
    │  (on success)
    ▼
smoke-test
    ├── producer.producer   (generate 10s of data locally)
    ├── write_to_s3         (ingest to Iceberg)
    └── read_iceberg        (verify table is readable)
```

---

### Workflow 3 — `deploy-prod.yml` (CD to prod)

**Trigger:** `push` to `main` (i.e. after a PR from develop is merged)

The `prod` GitHub Environment can be configured with required reviewers so a human must approve before Terraform runs. Set this up in: _Repository Settings → Environments → prod → Required reviewers_.

#### Job 1 — `terraform-apply-prod`

1. Checkout code
2. Configure AWS credentials (from GitHub Secret `PROD_AWS_ACCESS_KEY_ID` / `PROD_AWS_SECRET_ACCESS_KEY`)
3. `terraform init -backend-config=backend-prod.hcl` — connects to prod S3 remote state
4. `terraform plan -var-file=prod.tfvars -out=tfplan` — generates a saved plan
5. `terraform apply tfplan` — applies exactly the saved plan (no surprises)
6. `terraform output` — prints prod resource names

#### Job 2 — `verify-prod` (runs after Job 1)

1. Install Python dependencies
2. Run `producer.read_iceberg` against prod — confirms the Iceberg table exists and is accessible

**Full pipeline:**

```
push to main
    │
    ▼
(GitHub Environment approval gate — optional)
    │
    ▼
terraform-apply-prod
    │  plan → apply → output
    │  (on success)
    ▼
verify-prod
    └── read_iceberg  (confirms prod table is healthy)
```

---

## Terraform Modules

Infrastructure is split into three child modules. The root `main.tf` calls all three, passing variables from the active `.tfvars` file.

```
dev.tfvars / prod.tfvars
        │ variables
        ▼
   root main.tf
   ├── module "storage"  →  modules/storage/  →  terraform-aws-modules/s3-bucket/aws ~> 4.0
   ├── module "catalog"  →  modules/catalog/  →  raw aws_glue_catalog_database resource
   └── module "iam"      →  modules/iam/      →  terraform-aws-modules/iam/aws ~> 5.0
                                                   ├── //modules/iam-policy
                                                   └── //modules/iam-user
        │ outputs
        ▼
   root output.tf
```

### Module responsibilities

| Module | Registry source | Resources managed |
|---|---|---|
| `storage` | `terraform-aws-modules/s3-bucket/aws` | S3 bucket, versioning, SSE, public access block, lifecycle rule |
| `catalog` | raw resource | `aws_glue_catalog_database` |
| `iam` | `terraform-aws-modules/iam/aws` | IAM policy (Spark S3+Glue access), IAM user, policy attachment |

### Why tags are not passed to modules

`provider.tf` uses `default_tags` which automatically applies to every resource created by the AWS provider, including resources inside child modules. Tags do not need to be passed as module inputs.

### Migrating existing state after module refactor

If resources were previously created with the flat structure (before modules), use `terraform state mv` to remap addresses without destroying infrastructure:

```bash
terraform state mv \
  'aws_s3_bucket.banking' \
  'module.storage.module.s3_bucket.aws_s3_bucket.this[0]'

terraform state mv \
  'aws_glue_catalog_database.banking' \
  'module.catalog.aws_glue_catalog_database.this'

terraform state mv \
  'aws_iam_policy.spark_access' \
  'module.iam.module.spark_policy.aws_iam_policy.policy[0]'

terraform state mv \
  'aws_iam_user.spark_user' \
  'module.iam.module.spark_user.aws_iam_user.this[0]'

terraform state mv \
  'aws_iam_user_policy_attachment.spark_s3_access_attach' \
  'module.iam.module.spark_user.aws_iam_user_policy_attachment.this["0"]'
```

After all `state mv` commands, re-run `terraform plan -var-file=dev.tfvars` and confirm there are **no destroy actions** before applying.

---

## Terraform Remote State

State files are stored in S3 with DynamoDB locking to prevent concurrent applies.

| Environment | State key |
|---|---|
| dev | `banking-transaction/dev/terraform.tfstate` |
| prod | `banking-transaction/prod/terraform.tfstate` |

Both use the same S3 bucket (`banking-transaction-platform-20260601-state`) and DynamoDB table (`banking-tf-locks`).

### One-time bootstrap (run once before anything else)

```bash
cd terraform/bootstrap
terraform init
terraform apply -var="state_bucket_name=banking-transaction-platform-20260601-state"
```

### Migrate existing local state to S3

```bash
cd terraform
terraform init -backend-config=backend-dev.hcl
# Terraform prompts: "Do you want to copy existing state?" → yes
```

---

## GitHub Secrets Required

Configure these in _Repository Settings → Secrets and variables → Actions_:

| Secret | Used by | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | deploy-dev, terraform-plan (dev) | Dev IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | deploy-dev, terraform-plan (dev) | Dev IAM user secret key |
| `DEV_BUCKET_NAME` | deploy-dev smoke test | Dev S3 bucket name (e.g. `banking-iceberg-data-dev-20260601`) |
| `PROD_AWS_ACCESS_KEY_ID` | deploy-prod, terraform-plan (prod) | Prod IAM user access key |
| `PROD_AWS_SECRET_ACCESS_KEY` | deploy-prod, terraform-plan (prod) | Prod IAM user secret key |
| `PROD_BUCKET_NAME` | deploy-prod verify job | Prod S3 bucket name (e.g. `banking-iceberg-data-prod-20260601`) |

---

## Manual Operations

### Destroy dev infrastructure

```bash
cd terraform
terraform init -backend-config=backend-dev.hcl
terraform destroy -var-file=dev.tfvars
```

### Delete Glue table manually (if S3 warehouse was deleted outside Terraform)

```bash
aws glue delete-table \
  --database-name transaction_db_dev \
  --name transaction_logs
```

### Pre-push security checks

```bash
git grep AWS_SECRET_ACCESS_KEY
git grep AKIA
```
