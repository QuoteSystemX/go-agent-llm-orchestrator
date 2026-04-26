---
name: k8s-patterns
description: Deep Kubernetes expertise — Helm, Operators, RBAC, HPA/VPA, Ingress, NetworkPolicy, namespace isolation, CRDs, service mesh, cluster hardening, observability. Universal — works in Antigravity (Gemini) and Claude Code.
---

# Kubernetes Patterns Skill

Production-grade Kubernetes knowledge covering cluster design, workload management, security hardening, and operational practices.

---

## 🏗️ CORE CONCEPTS & OBJECT MODEL

### Workload Hierarchy

```
Cluster
└── Namespace
    ├── Deployment → ReplicaSet → Pod → Container
    ├── StatefulSet → Pod (stable identity, PVC binding)
    ├── DaemonSet → Pod (one per node)
    ├── Job / CronJob → Pod (batch)
    └── Service → Endpoints → Pod (network abstraction)
```

### Resource Requests vs Limits (ALWAYS SET BOTH)

```yaml
resources:
  requests:
    cpu: "100m"      # scheduler uses this for placement
    memory: "128Mi"
  limits:
    cpu: "500m"      # hard cap; throttled if exceeded
    memory: "256Mi"  # hard cap; OOMKilled if exceeded
```

**Rules:**
- Never omit `requests` — scheduler blindly places pods → node starvation
- Memory limit = memory request × 2 is a safe starting point
- CPU throttling is silent; memory over-limit = OOMKill (loud)

### QoS Classes

| Class | Condition | Eviction Priority |
|-------|-----------|------------------|
| `Guaranteed` | requests == limits for all containers | Last evicted |
| `Burstable` | requests < limits | Middle |
| `BestEffort` | no requests/limits | First evicted |

---

## 🔐 RBAC (Role-Based Access Control)

### Object Hierarchy

```
ServiceAccount → RoleBinding → Role          (namespace-scoped)
ServiceAccount → ClusterRoleBinding → ClusterRole  (cluster-scoped)
```

### Principle of Least Privilege

```yaml
# Role: read-only pods in specific namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: monitoring-sa
    namespace: monitoring
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

### Common RBAC Mistakes

| ❌ Don't | ✅ Do |
|----------|-------|
| `verbs: ["*"]` on `ClusterRole` | List exact verbs needed |
| Bind to `cluster-admin` for apps | Create minimal Role |
| Share ServiceAccounts across apps | One SA per workload |
| `automountServiceAccountToken: true` (default) | Set `false` if token unused |

### Audit RBAC

```bash
# Who can do what
kubectl auth can-i --list --as=system:serviceaccount:production:my-sa

# Find all RoleBindings for a ServiceAccount
kubectl get rolebindings,clusterrolebindings -A \
  -o jsonpath='{range .items[?(@.subjects[*].name=="my-sa")]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'
```

---

## 🌐 INGRESS & NETWORKING

### Ingress Controllers (choose by use case)

| Controller | Best For |
|-----------|----------|
| `ingress-nginx` | General-purpose, battle-tested |
| `traefik` | Dynamic config, middlewares |
| `aws-load-balancer-controller` | AWS ALB/NLB native integration |
| `contour` | HTTPProxy CRD, envoy-based |
| `istio-ingress` | Service mesh + ingress combined |

### Ingress Patterns

```yaml
# TLS termination + routing
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 8080
```

### NetworkPolicy (default-deny is a must for production)

```yaml
# Deny all ingress, allow only from specific namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}     # applies to ALL pods in namespace
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: frontend
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

---

## 📦 HELM

### Chart Structure

```
my-chart/
├── Chart.yaml           # metadata: name, version, appVersion
├── values.yaml          # default values
├── values-prod.yaml     # environment overrides (not in chart)
├── templates/
│   ├── _helpers.tpl     # named templates (reusable snippets)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── serviceaccount.yaml
│   ├── rbac.yaml
│   └── NOTES.txt        # post-install instructions
└── charts/              # sub-charts (dependencies)
```

### Helm Best Practices

```yaml
# values.yaml — always expose these as configurable
image:
  repository: myrepo/myapp
  tag: "1.0.0"      # pin exact tag, never "latest"
  pullPolicy: IfNotPresent

replicaCount: 2

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi

autoscaling:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### Helm Commands Cheatsheet

```bash
# Render templates without installing (dry-run + debug)
helm template my-release ./my-chart -f values-prod.yaml

# Diff before upgrade (requires helm-diff plugin)
helm diff upgrade my-release ./my-chart -f values-prod.yaml

# Install with atomic (rollback on failure)
helm upgrade --install my-release ./my-chart \
  -f values-prod.yaml \
  --namespace production \
  --create-namespace \
  --atomic \
  --timeout 5m

# Rollback
helm rollback my-release 1  # 1 = revision number

# Inspect release history
helm history my-release -n production
```

### Helm Hooks

```yaml
# Run DB migration before app starts
annotations:
  "helm.sh/hook": pre-upgrade,pre-install
  "helm.sh/hook-weight": "-5"
  "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
```

---

## ⚖️ HPA & VPA (Autoscaling)

### HPA (Horizontal Pod Autoscaler)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: AverageValue
          averageValue: 200Mi
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # wait 5m before scale-down
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
```

### VPA (Vertical Pod Autoscaler)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  updatePolicy:
    updateMode: "Off"   # "Off"=recommend only | "Auto"=apply+restart
  resourcePolicy:
    containerPolicies:
      - containerName: api
        minAllowed:
          cpu: 50m
          memory: 64Mi
        maxAllowed:
          cpu: 2
          memory: 2Gi
```

**HPA vs VPA rules:**
- Never use HPA + VPA `Auto` on the same deployment (conflict)
- HPA + VPA `Off` (recommendations only) is safe
- KEDA extends HPA with custom metrics (queue depth, HTTP RPS, etc.)

### KEDA (Kubernetes Event-Driven Autoscaling)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: rabbitmq-consumer-scaler
spec:
  scaleTargetRef:
    name: rabbitmq-consumer
  minReplicaCount: 0   # scale to zero!
  maxReplicaCount: 30
  triggers:
    - type: rabbitmq
      metadata:
        queueName: orders
        queueLength: "10"
```

---

## 🗂️ NAMESPACE ISOLATION

### Namespace Strategy

| Approach | Use Case |
|----------|----------|
| Per environment (`dev`, `staging`, `prod`) | Single team, multiple envs |
| Per team (`team-payments`, `team-auth`) | Multi-team cluster |
| Per application (`app-frontend`, `app-backend`) | Strict isolation |
| Hierarchical (HNC) | Large organizations |

### Isolation Checklist

```yaml
# 1. ResourceQuota per namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    pods: "50"
    services: "20"
    persistentvolumeclaims: "10"

---
# 2. LimitRange — default requests/limits for containers without explicit values
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "2"
        memory: 2Gi
```

---

## 🤖 OPERATORS & CRDs

### Operator Pattern

```
CRD (defines new resource type, e.g. "Database")
    ↓
Custom Resource (instance of CRD)
    ↓
Operator (controller watches CRD, reconciles desired → actual state)
```

### Common Production Operators

| Operator | Manages |
|----------|---------|
| `cert-manager` | TLS certificates (ACME/Let's Encrypt) |
| `external-secrets-operator` | Sync secrets from Vault/AWS SM/GCP SM |
| `prometheus-operator` | Prometheus stack (ServiceMonitor, PrometheusRule) |
| `strimzi` | Apache Kafka on K8s |
| `postgres-operator` (Zalando) | PostgreSQL clusters |
| `argo-cd` | GitOps deployments |
| `crossplane` | Infrastructure as code (cloud resources as CRDs) |

### Writing a Simple Operator (controller-runtime pattern)

```go
// Reconcile loop — the core of every operator
func (r *MyAppReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. Fetch the CR
    myApp := &myv1.MyApp{}
    if err := r.Get(ctx, req.NamespacedName, myApp); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. Compare desired vs actual state
    // 3. Create/update/delete child resources
    // 4. Update CR status
    // 5. Return: Result{} = done, Result{RequeueAfter: 30s} = retry
}
```

---

## 🔒 SECURITY HARDENING

### Pod Security Standards (PSS)

```yaml
# Enforce restricted policy at namespace level
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### Secure Pod Spec Checklist

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault

  containers:
    - name: app
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: [ALL]
          add: []   # add only what's needed, e.g. [NET_BIND_SERVICE]

      volumeMounts:
        - name: tmp
          mountPath: /tmp    # writable tmp when rootfs is readonly

  volumes:
    - name: tmp
      emptyDir: {}

  automountServiceAccountToken: false
  hostNetwork: false
  hostPID: false
  hostIPC: false
```

### Secrets Management (never store in Git)

```yaml
# external-secrets-operator: pull from AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secretsmanager
  target:
    name: db-secret
    creationPolicy: Owner
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: production/db
        property: password
```

---

## 📊 OBSERVABILITY

### Prometheus ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-monitor
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: api
  namespaceSelector:
    matchNames: [production]
  endpoints:
    - port: metrics
      path: /metrics
      interval: 15s
```

### PrometheusRule (alerting)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: api-alerts
  namespace: monitoring
spec:
  groups:
    - name: api.rules
      rules:
        - alert: HighErrorRate
          expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "High error rate on {{ $labels.service }}"
```

### Key Metrics to Always Watch

| Metric | Alert Threshold |
|--------|----------------|
| Pod restart count | > 3 in 15m |
| CPU throttling | > 25% |
| Memory usage vs limit | > 85% |
| PVC usage | > 80% |
| Node NotReady | Any |
| HPA at maxReplicas | Duration > 5m |

---

## 🚀 DEPLOYMENT STRATEGIES

### Rolling Update (default)

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # extra pods during update
      maxUnavailable: 0  # zero-downtime
```

### Blue-Green with Argo Rollouts

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api-rollout
spec:
  strategy:
    blueGreen:
      activeService: api-active
      previewService: api-preview
      autoPromotionEnabled: false   # manual gate
      scaleDownDelaySeconds: 30
```

### Canary with Argo Rollouts

```yaml
  strategy:
    canary:
      steps:
        - setWeight: 5      # 5% traffic to new version
        - pause: {duration: 5m}
        - setWeight: 20
        - pause: {duration: 10m}
        - analysis:
            templates:
              - templateName: success-rate
        - setWeight: 100
```

---

## 🛠️ TROUBLESHOOTING PLAYBOOK

### Pod Won't Start

```bash
# Step 1: describe for events
kubectl describe pod <name> -n <ns>

# Step 2: logs (init containers first)
kubectl logs <pod> -n <ns> --previous          # crashed pod
kubectl logs <pod> -n <ns> -c init-container   # init container

# Step 3: exec in (if running)
kubectl exec -it <pod> -n <ns> -- sh

# Step 4: ephemeral debug container (K8s 1.23+)
kubectl debug -it <pod> -n <ns> --image=busybox --target=<container>
```

### Common Error States

| State | Likely Cause | Fix |
|-------|-------------|-----|
| `CrashLoopBackOff` | App crashes on start | Check logs, fix app |
| `ImagePullBackOff` | Wrong image tag or registry auth | Check `imagePullSecrets` |
| `Pending` (no node) | Insufficient resources | Check `kubectl describe pod` events |
| `OOMKilled` | Memory limit too low | Increase `limits.memory` |
| `Evicted` | Node memory pressure | Increase requests, use `Guaranteed` QoS |
| `CreateContainerConfigError` | Missing secret/configmap | Check referenced secrets exist |

### Networking Debug

```bash
# Test connectivity between pods
kubectl run netdebug --rm -it --image=nicolaka/netshoot -- bash
curl http://service-name.namespace.svc.cluster.local:8080/health

# DNS lookup
kubectl run dnstest --rm -it --image=busybox -- nslookup kubernetes.default

# Port-forward for local testing
kubectl port-forward svc/api 8080:8080 -n production
```

### Node Troubleshooting

```bash
# Node resource usage
kubectl top nodes
kubectl top pods -n production --sort-by=memory

# Events across cluster (sorted by time)
kubectl get events -A --sort-by='.lastTimestamp' | tail -20

# Resource allocation per node
kubectl describe node <name> | grep -A 10 "Allocated resources"
```

---

## 📋 PRODUCTION READINESS CHECKLIST

### Workload

- [ ] `resources.requests` and `limits` set on all containers
- [ ] `readinessProbe` and `livenessProbe` configured
- [ ] `startupProbe` for slow-starting apps
- [ ] `podDisruptionBudget` defined (minAvailable ≥ 1)
- [ ] `topologySpreadConstraints` or `podAntiAffinity` for HA
- [ ] Image tag pinned (no `latest`)
- [ ] `imagePullPolicy: IfNotPresent` (avoid `Always` in prod)

### Security

- [ ] `runAsNonRoot: true` + explicit `runAsUser`
- [ ] `readOnlyRootFilesystem: true`
- [ ] `allowPrivilegeEscalation: false`
- [ ] `capabilities.drop: [ALL]`
- [ ] `automountServiceAccountToken: false` (if not needed)
- [ ] Secrets from Vault/ESO, not plain K8s Secrets in Git
- [ ] NetworkPolicy: default-deny + explicit allows
- [ ] PSS namespace labels enforced

### Scaling & Resilience

- [ ] HPA configured (CPU ≥ 70% target)
- [ ] minReplicas ≥ 2 for production workloads
- [ ] PodDisruptionBudget covers upgrade scenarios
- [ ] Resource quotas on namespace

### Observability

- [ ] `/metrics` endpoint exposed (Prometheus)
- [ ] `ServiceMonitor` created
- [ ] Alerting rules for error rate, OOMKill, pod restarts
- [ ] Structured logs (JSON) to stdout

<!-- EMBED_END -->
