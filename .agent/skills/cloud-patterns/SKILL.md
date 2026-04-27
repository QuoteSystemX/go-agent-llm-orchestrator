---
name: cloud-patterns
description: Multi-cloud engineering for AWS/GCP/Azure — IAM least-privilege, VPC networking, cost optimization (spot/reserved/commitments), KMS secrets rotation, CDN/edge, managed databases, container registries, serverless, multi-cloud abstraction patterns.
version: 1.0.0
---

# Cloud Patterns Skill

> Multi-cloud infrastructure: secure by default, cost-aware, provider-agnostic where possible.
> **Vendor lock-in is a trade-off, not a crime — document it explicitly.**

---

## 1. IAM — Least Privilege

### AWS

```hcl
# Task-specific role — no wildcard actions
resource "aws_iam_role" "app" {
  name               = "${local.name_prefix}-app"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${aws_iam_openid_connect_provider.eks.url}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account}"]
    }
  }
}

data "aws_iam_policy_document" "app" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/app/*"]   # scoped, not bucket-wide
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app.arn]
  }
}
```

### GCP — Workload Identity Federation

```hcl
resource "google_service_account" "app" {
  account_id   = "${var.name_prefix}-app"
  display_name = "App service account"
}

resource "google_service_account_iam_member" "wi_binding" {
  service_account_id = google_service_account.app.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project}.svc.id.goog[${var.namespace}/${var.k8s_sa}]"
}

# Grant only required roles — avoid Editor/Owner
resource "google_project_iam_member" "app_storage" {
  project = var.project
  role    = "roles/storage.objectCreator"   # not objectAdmin
  member  = "serviceAccount:${google_service_account.app.email}"
}
```

### Azure — Managed Identity

```hcl
resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.name_prefix}-app-identity"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
}

resource "azurerm_role_assignment" "app_blob" {
  scope                = azurerm_storage_container.data.resource_manager_id
  role_definition_name = "Storage Blob Data Contributor"   # not Owner
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}
```

---

## 2. Networking — VPC / Virtual Network

### AWS VPC — 3-tier layout

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.1"

  name = local.name_prefix
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  intra_subnets   = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]  # DB tier

  enable_nat_gateway     = true
  single_nat_gateway     = false   # HA: one per AZ
  enable_vpn_gateway     = false

  # Tags required for EKS
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
}
```

### VPC Peering / Private Endpoints

```hcl
# Private endpoint for S3 — keeps traffic off internet
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
}

# Interface endpoint for Secrets Manager
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
}
```

### GCP VPC — Shared VPC pattern

```hcl
resource "google_compute_network" "main" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false   # always manual subnets
}

resource "google_compute_subnetwork" "app" {
  name          = "${var.name_prefix}-app"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id

  private_ip_google_access = true   # access GCP APIs without NAT

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# Private Service Connect for Cloud SQL
resource "google_service_networking_connection" "private_sql" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_range.name]
}
```

---

## 3. Cost Optimization

### Spot / Preemptible Strategy

| Workload | AWS | GCP | Azure |
|----------|-----|-----|-------|
| Stateless services | Spot + On-Demand mix (70/30) | Preemptible + Standard mix | Spot + Regular mix |
| Batch / CI runners | 100% Spot with retry | 100% Preemptible | 100% Spot |
| Databases | Never Spot | Never Preemptible | Never Spot |
| ML training | Spot with checkpointing | Preemptible with restart | Spot with checkpoint |

```hcl
# AWS: mixed instance policy for EKS node group
resource "aws_eks_node_group" "workers" {
  scaling_config {
    desired_size = 3
    min_size     = 1
    max_size     = 10
  }

  instance_types = ["m5.xlarge", "m5a.xlarge", "m4.xlarge"]   # multiple for spot availability

  capacity_type = "SPOT"   # or "ON_DEMAND"

  # Taint spot nodes so only spot-tolerant workloads land here
  taint {
    key    = "node.kubernetes.io/capacity-type"
    value  = "spot"
    effect = "NO_SCHEDULE"
  }
}
```

### Reserved Instances / Committed Use

```
Decision framework:
  - Baseline steady-state load → 1-year RI / Committed Use (40-60% savings)
  - Predictable growth         → 1-year convertible RI (flex to change family)
  - Unknown/variable           → Savings Plans (AWS) / CUDs (GCP)
  - Never commit on:           → dev/staging, batch workloads, experimental services
```

### Right-sizing checklist

```bash
# AWS: identify over-provisioned instances
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --period 86400 --statistics Average \
  --dimensions Name=InstanceId,Value=<id>

# Rule: P95 CPU < 20% for 2+ weeks → downsize one class
# Rule: Memory < 30% → downsize (use CloudWatch agent for memory metrics)

# GCP: use Recommender API
gcloud recommender recommendations list \
  --recommender=google.compute.instance.MachineTypeRecommender \
  --location=us-central1-a \
  --project=$PROJECT
```

---

## 4. KMS & Secrets Rotation

### AWS — Automatic rotation

```hcl
resource "aws_secretsmanager_secret" "db" {
  name                    = "${local.name_prefix}/db/password"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.arn
}

resource "aws_secretsmanager_secret_rotation" "db" {
  secret_id           = aws_secretsmanager_secret.db.id
  rotation_lambda_arn = aws_lambda_function.rotate_db.arn

  rotation_rules {
    automatically_after_days = 30
  }
}

resource "aws_kms_key" "secrets" {
  description             = "Secrets Manager encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true   # annual rotation of the CMK itself
}
```

### GCP — Secret Manager with versions

```hcl
resource "google_secret_manager_secret" "db" {
  secret_id = "${var.name_prefix}-db-password"

  replication {
    auto {}   # or user_managed for specific regions
  }
}

resource "google_secret_manager_secret_version" "db_v1" {
  secret      = google_secret_manager_secret.db.id
  secret_data = var.db_password   # passed via TF_VAR_ env var
}

# Cloud Scheduler + Cloud Functions for rotation
resource "google_cloud_scheduler_job" "rotate_secrets" {
  name     = "rotate-db-password"
  schedule = "0 2 1 * *"   # 02:00 on 1st of each month
  http_target {
    uri         = google_cloudfunctions2_function.rotate.url
    http_method = "POST"
  }
}
```

### Azure — Key Vault with auto-rotation

```hcl
resource "azurerm_key_vault" "main" {
  name                = "${var.name_prefix}-kv"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_retention_days = 7
  purge_protection_enabled   = true   # prevents accidental permanent deletion
}

resource "azurerm_key_vault_secret" "db" {
  name         = "db-password"
  value        = var.db_password
  key_vault_id = azurerm_key_vault.main.id

  expiration_date = timeadd(timestamp(), "720h")   # 30d — triggers rotation alert
}
```

---

## 5. CDN & Edge

### AWS CloudFront

```hcl
resource "aws_cloudfront_distribution" "app" {
  origin {
    domain_name = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id   = "s3-assets"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }

  origin {
    domain_name = aws_lb.app.dns_name
    origin_id   = "alb-app"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
    }
  }

  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "alb-app"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
  }

  ordered_cache_behavior {
    path_pattern     = "/static/*"
    target_origin_id = "s3-assets"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]

    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 86400    # 1 day
    max_ttl     = 31536000 # 1 year
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
```

### GCP Cloud CDN

```hcl
resource "google_compute_backend_bucket" "assets" {
  name        = "${var.name_prefix}-assets"
  bucket_name = google_storage_bucket.assets.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching  = true
    serve_while_stale = 86400
  }
}
```

---

## 6. Container Registries

```hcl
# AWS ECR with lifecycle policy
resource "aws_ecr_repository" "app" {
  name                 = var.app_name
  image_tag_mutability = "IMMUTABLE"   # prevent tag overwrites

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 tagged images"
      selection = {
        tagStatus   = "tagged"
        tagPrefixList = ["v"]
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
```

---

## 7. Multi-cloud Abstraction Patterns

### When to abstract vs. go native

```
✅ Abstract:
  - Secret retrieval interface (same API regardless of provider)
  - Object storage client (same S3-compatible API via MinIO/LocalStack in dev)
  - DNS management (provider-agnostic via external-dns)

🚫 Don't abstract:
  - IAM/permissions (too provider-specific — accept duplication)
  - Networking constructs (VPC ≠ VNet ≠ GCP VPC — pretending otherwise causes bugs)
  - Managed services (RDS ≠ Cloud SQL — feature sets diverge)
```

### Portable secret client (Go)

```go
type SecretClient interface {
    Get(ctx context.Context, name string) (string, error)
}

type awsSecrets struct{ client *secretsmanager.Client }
type gcpSecrets struct{ client *secretmanager.Client; project string }
type azureSecrets struct{ client *azsecrets.Client }

func (s *awsSecrets) Get(ctx context.Context, name string) (string, error) {
    out, err := s.client.GetSecretValue(ctx, &secretsmanager.GetSecretValueInput{
        SecretId: aws.String(name),
    })
    if err != nil { return "", fmt.Errorf("aws secret %s: %w", name, err) }
    return aws.ToString(out.SecretString), nil
}
```

---

## 8. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Public S3 bucket | `block_public_acls = true` + bucket policy |
| IAM `*` actions | Enumerate required actions; use IAM Access Analyzer |
| Single NAT Gateway | One per AZ for HA (`single_nat_gateway = false`) |
| Secrets in env vars (plaintext) | Pull from KMS/SecretManager at runtime |
| No lifecycle policy on ECR/GCR | Unbounded storage cost over time |
| CloudFront without WAF | Add `aws_wafv2_web_acl_association` for public APIs |
| Spot without fallback | Always configure mixed instance types / capacity types |
| KMS key without rotation | `enable_key_rotation = true` on every CMK |
