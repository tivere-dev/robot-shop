# Runbook: Robot Shop API availability (error budget burn)

Alerts that link here: `RobotShopErrorBudgetFastBurn` (critical), `RobotShopErrorBudgetSlowBurn` (warning).
SLO and policy: [docs/slo.md](../slo.md).

**What the alert means:** too many `/api/*` requests are returning 5xx (more than 7.2 % over the last hour for the fast burn, more than 3 % over 6 hours for the slow burn). Users see failed pages: the product list, the cart, login or checkout stop working.

**Goal:** stop the errors first (mitigate), find the cause second.

## 0. Before you start (local cluster)

```bash
alias k='kubectl --context capstone'
k -n monitoring port-forward svc/monitoring-grafana 3000:80 &      # Grafana
k -n monitoring port-forward svc/monitoring-prometheus 9090:9090 & # Prometheus
k -n tracing port-forward svc/jaeger 16686:16686 &                 # Jaeger
```

## 1. Which API is failing? (2 minutes)

Open the dashboard **Robot Shop: requests, errors and latency** (`http://localhost:3000/d/robot-shop-red`) and look at **5xx error rate by API** and **Responses by status code**. Or in Prometheus:

```promql
sum by (router, code) (rate(traefik_router_requests_total{router=~"robot-shop-.*", code=~"5.."}[5m]))
```

| Status | Usually means |
|---|---|
| 502 | `web` (nginx) could not reach the backend service: the pod is crashing or restarting |
| 503 | no ready pod behind a Service |
| 504 | the backend is too slow (CPU throttling, a slow dependency) |
| 500 | the service itself failed: read its logs |

## 2. Is a pod crashing or restarting?

```bash
k -n robot-shop get pods                       # look for CrashLoopBackOff, high RESTARTS
k -n robot-shop describe pod -l service=<name> | grep -A5 'Last State'   # OOMKilled? exit code?
```

Dashboard row **Service health**: *Restarts in the last hour*, *Memory as % of limit* (near 100 % = OOM risk), *Available replicas*.

## 3. Did something just change? (most incidents are changes)

```bash
helm --kube-context capstone -n robot-shop history robot-shop | tail -5
helm --kube-context capstone -n robot-shop get values robot-shop --revision <N>   # compare with N-1
```

If a release went out shortly before the errors started, **roll it back now** and investigate afterwards:

```bash
helm --kube-context capstone -n robot-shop rollback robot-shop <last-good-revision> --wait
```

## 4. Read the logs (Grafana → Explore → Loki)

```logql
{namespace="robot-shop", service="<name>", level=~"error|fatal"}
{namespace="robot-shop", level=~"error|fatal", instana_noise="false"}   # all real errors
{namespace="robot-shop", service="web"} |= " 502 "                      # nginx upstream failures
```

`instana_noise="true"` marks leftover Instana-agent lookups; they are never the cause.

## 5. Slow rather than failing? Look at a trace (payment)

Jaeger (`http://localhost:16686`, service `payment`) or Grafana → Explore → Jaeger. Payment logs `trace_id=<id>`; in Grafana the ID is a link to the trace. The external payment gateway call (`GET https://paypal.com/`) normally takes ~2 s of each payment.

## 6. Common causes and fixes

| Cause | Sign | Fix |
|---|---|---|
| Bad release | errors start right after `helm upgrade` | `helm rollback` to the previous revision |
| Memory limit too low | `OOMKilled`, restarts climbing, memory near 100 % of limit | roll back, or raise the limit in `K8s/helm/values.yaml` |
| CPU throttling | 504s, latency up, CPU flat at the limit | raise the CPU limit (shipping needed 1000m) |
| Database not ready | MySQL/MongoDB errors in ratings, shipping, user, catalogue logs | wait for `mysql`/`mongodb` to be ready; check their pods |
| Node out of memory | many pods restarting at once | `docker stats capstone`; scale down something non-essential |

## 7. After it is fixed

1. Check the alert has resolved (Slack shows `[RESOLVED]`, or Prometheus → Alerts).
2. Check how much budget was used: dashboard **28-day budget used by the last 24 hours**.
3. If more than 20 % of the budget was used, write a blameless postmortem in `docs/postmortems/` (see the [policy](../slo.md#error-budget-policy)).

## Slack set-up

Alertmanager reads the webhook from the Secret `monitoring/alertmanager-slack` (never commit it):

```bash
k -n monitoring create secret generic alertmanager-slack \
  --from-literal=webhook-url='https://hooks.slack.com/services/...' \
  --dry-run=client -o yaml | k apply -f -
```

Kubernetes updates the mounted file within about a minute. To be sure Alertmanager uses the new URL, restart it: `k -n monitoring rollout restart statefulset alertmanager-monitoring-alertmanager`. In this local setup the Secret points at the in-cluster `slack-mock`, which logs each message: `k -n monitoring logs deploy/slack-mock`.
