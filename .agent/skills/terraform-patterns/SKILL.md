---
name: terraform-patterns
description: Terraform/OpenTofu best practices — HCL modules, state management, workspace strategy, provider patterns (AWS/GCP/Azure), plan/apply safety protocol, secrets hygiene, terratest, checkov. Universal — works in Antigravity (Gemini) and Claude Code.
version: 1.0.0
---

# Terraform Patterns Skill

> Infrastructure as Code discipline: reproducible, safe, auditable.
> **The goal is idempotent infrastructure, not clever HCL.**

---

## 1. Project Structure

```
infra/
├── modules/           # reusable building blocks
│   ├── vpc/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   └── eks-cluster/
├── environments/
│   ├── dev/
│   │   ├── main.tf    # calls modules
│   │   ├── backend.tf # per-env remote state
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
└── .terraform.lock.hcl  # always commit
```

**Rules:**
- One root module per environment, not per resource type
- Modules encapsulate a logical unit (vpc, cluster, database) — not a provider
- `versions.tf` in every module pins `required_providers` + `required_version`
- Never use `source = "../../../modules/foo"` more than 3 `../` deep — restructure instead

---

## 2. HCL Best Practices

### Variables — validate at the boundary

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment: dev, staging, prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "instance_count" {
  type    = number
  default = 1
  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 100
    error_message = "instance_count must be between 1 and 100."
  }
}
```

### Locals — name computed values once

```hcl
locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    CreatedAt   = timestamp()  # avoid in prod — causes drift
  }
}

resource "aws_instance" "app" {
  # Good: reference local, not inline expression
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app" })
}
```

### Outputs — expose only what callers need

```hcl
output "vpc_id" {
  description = "VPC ID for cross-module reference"
  value       = aws_vpc.main.id
  # sensitive = true  ← use for passwords, tokens
}
```

### For-each over count

```hcl
# Prefer: stable resource addresses
resource "aws_iam_user" "team" {
  for_each = toset(var.team_members)
  name     = each.key
}

# Avoid: index-based addresses break on removal
resource "aws_iam_user" "team" {
  count = length(var.team_members)
  name  = var.team_members[count.index]
}
```

---

## 3. State Management

### Remote backend (mandatory for teams)

```hcl
# backend.tf — one per environment
terraform {
  backend "s3" {
    bucket         = "acme-terraform-state-prod"
    key            = "services/api/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"  # state locking
  }
}
```

**GCS equivalent:**
```hcl
terraform {
  backend "gcs" {
    bucket = "acme-tfstate"
    prefix = "services/api"
  }
}
```

### State locking — why it matters

State locking prevents concurrent `apply` from corrupting state. DynamoDB (AWS) and GCS object metadata (GCP) provide this automatically with the backends above. Azure uses blob leases.

**Never run `terraform force-unlock` without confirming the other process is dead.**

### Workspace strategy

| Approach | When to use | Pitfall |
|----------|-------------|---------|
| Separate directories per env | ✅ Different infra per env | More duplication |
| Workspaces | Only for truly identical infra with different vars | Shared backend = shared mistakes |
| Terragrunt | Large mono-repo with many envs | Added complexity |

Default recommendation: **separate directories**, not workspaces. Workspaces share a backend and it's easy to `apply` to prod while on the wrong workspace.

### State manipulation — last resort

```bash
# Move resource to new address (rename)
terraform state mv aws_instance.old aws_instance.new

# Remove from state without destroying (import manually after)
terraform state rm aws_instance.orphaned

# Pull current state for inspection
terraform state pull | jq '.resources[] | select(.type == "aws_instance")'
```

---

## 4. Provider Patterns

### Version pinning

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"   # allows 5.x, blocks 6.x
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
  }
}
```

### Resource naming conventions

```hcl
# Pattern: {project}-{environment}-{resource-type}-{purpose}
resource "aws_s3_bucket" "assets" {
  bucket = "${local.name_prefix}-assets"  # acme-prod-assets
}

resource "google_container_cluster" "main" {
  name = "${local.name_prefix}-gke"  # acme-prod-gke
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project}-${var.environment}"  # rg-acme-prod
  location = var.location
}
```

### Multi-provider (multi-region, multi-account)

```hcl
provider "aws" {
  region = "us-east-1"
  alias  = "primary"
}

provider "aws" {
  region = "eu-west-1"
  alias  = "eu"
  assume_role {
    role_arn = "arn:aws:iam::${var.eu_account_id}:role/terraform"
  }
}

resource "aws_s3_bucket" "eu_backup" {
  provider = aws.eu
  bucket   = "${local.name_prefix}-backup-eu"
}
```

---

## 5. Secrets Hygiene

**The golden rule: secrets never appear in `.tf` files, `.tfvars` files committed to git, or state output.**

### ✅ Correct patterns

```hcl
# 1. Environment variables (CI/CD friendly)
#    TF_VAR_db_password=... terraform apply

variable "db_password" {
  type      = string
  sensitive = true  # redacts from output
}

# 2. Read from Vault at apply time
data "vault_generic_secret" "db" {
  path = "secret/prod/database"
}

resource "aws_db_instance" "main" {
  password = data.vault_generic_secret.db.data["password"]
}

# 3. AWS Secrets Manager
data "aws_secretsmanager_secret_version" "db" {
  secret_id = "prod/database/password"
}
```

### 🚫 Never do

```hcl
# NEVER: hardcoded secrets
resource "aws_db_instance" "main" {
  password = "super-secret-123"   # ← shows in state, git history
}

# NEVER: secrets in terraform.tfvars committed to git
db_password = "super-secret-123"
```

### Protect state from secret leakage

State files contain all resource attributes, including passwords. Ensure:
1. Backend has encryption at rest (S3: `encrypt = true`)
2. IAM/ACL restricts state bucket access
3. State is never printed in CI logs (`terraform show` → pipe to file, not stdout)

---

## 6. Module Versioning

### Registry modules (public/private)

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.1"   # always pin

  name = local.name_prefix
  cidr = "10.0.0.0/16"
}
```

### Git-sourced internal modules

```hcl
module "internal_vpc" {
  source = "git::https://github.com/acme/infra-modules.git//vpc?ref=v2.3.0"
  # ref= can be tag, commit SHA, branch (avoid branch — mutable)
}
```

### When to extract a module

Extract when the same resource group is used in 2+ root modules with different inputs. Do **not** extract for a single use — premature abstraction in HCL is painful to refactor.

---

## 7. Plan/Apply Safety Protocol

```bash
# 1. Always plan first, save output
terraform plan -out=tfplan

# 2. Review the plan — understand every change
terraform show tfplan | grep -E "^\s+[+~-]"

# 3. Count: creates / updates / destroys
terraform show -json tfplan | jq '
  .resource_changes | group_by(.change.actions[])
  | map({action: .[0].change.actions[0], count: length})'

# 4. Apply only the saved plan
terraform apply tfplan
```

### Gate on destroy

Protect critical resources from accidental deletion:

```hcl
resource "aws_rds_cluster" "main" {
  lifecycle {
    prevent_destroy = true
  }
}
```

For CI, require explicit `-target` or approval gate before any plan containing `destroy`.

### Drift detection

```bash
# Refresh state without applying
terraform plan -refresh-only

# Shows what changed outside of Terraform (manual console edits, etc.)
```

---

## 8. Testing

### checkov — static security scanning

```bash
pip install checkov

# Scan before plan
checkov -d infra/environments/prod/ --framework terraform

# In CI (fail on HIGH severity)
checkov -d . --framework terraform --check HIGH --compact
```

Common checks: public S3 buckets, unencrypted storage, open security groups, missing logging.

### terratest — integration testing

```go
// test/vpc_test.go
package test

import (
    "testing"
    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
)

func TestVpcModule(t *testing.T) {
    t.Parallel()

    opts := &terraform.Options{
        TerraformDir: "../modules/vpc",
        Vars: map[string]interface{}{
            "project":     "test",
            "environment": "dev",
            "cidr":        "10.99.0.0/16",
        },
    }

    defer terraform.Destroy(t, opts)
    terraform.InitAndApply(t, opts)

    vpcID := terraform.Output(t, opts, "vpc_id")
    assert.NotEmpty(t, vpcID)
}
```

Run against a real (dev) account — terratest creates and destroys real resources. Budget accordingly.

---

## 9. CI/CD Integration

### GitHub Actions pattern

```yaml
- name: Terraform security scan
  run: checkov -d infra/ --framework terraform --compact

- name: Terraform Init
  run: terraform -chdir=infra/environments/${{ env.TF_ENV }} init

- name: Terraform Plan
  run: terraform -chdir=infra/environments/${{ env.TF_ENV }} plan -out=tfplan
  env:
    TF_VAR_db_password: ${{ secrets.DB_PASSWORD }}

# Require manual approval before apply on prod
- name: Terraform Apply
  if: github.ref == 'refs/heads/main' && env.TF_ENV == 'prod'
  run: terraform -chdir=infra/environments/prod apply tfplan
```

### `terraform fmt` in pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.88.0
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: checkov
```

---

## 10. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| `count` with list — index shifts on removal | Switch to `for_each = toset(...)` |
| `timestamp()` in tags → constant drift | Use `terraform.workspace` or static strings |
| Secrets in `terraform.tfvars` committed | Add `*.tfvars` to `.gitignore`; use env vars |
| No `prevent_destroy` on databases | Add lifecycle block to stateful resources |
| Hardcoded region/account in modules | Parameterize via `data "aws_region"` |
| `terraform apply` without `plan -out` | CI always saves plan; humans always review |
| Provider not pinned → silent upgrade | Pin with `~>` in `versions.tf` |
| Workspace as poor man's environments | Separate directories instead |
