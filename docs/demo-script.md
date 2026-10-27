# Capstone 2 demo script (about 10 minutes)

Everything runs on the local Minikube profile `capstone`; nothing runs in the cloud.

## Setup (before the demo)

```bash
cd capstone-2-robot-shop
alias k='kubectl --context capstone'
minikube start -p capstone --cpus=4 --memory=7168 --keep-context
k -n voting-app scale deploy --all --replicas=0      # free memory (Capstone 1 app)
k get pods -A | grep -vE 'Running|Completed'          # should print only the header

k -n monitoring port-forward svc/monitoring-grafana 3000:80 &
k -n monitoring port-forward svc/monitoring-prometheus 9090:9090 &
k -n tracing port-forward svc/jaeger 16686:16686 &
k -n traefik port-forward svc/traefik 8085:80 &      # the shop itself: http://localhost:8085
```

Grafana login: `admin`, password from
`k -n monitoring get secret monitoring-grafana -o jsonpath='{.data.admin-password}' | base64 -d` (do not show it on screen).

## 1. The app is running and busy (1 min)

- `k -n robot-shop get pods`: 12 services, all Running.
- Open `http://localhost:8085`, click a robot, add it to the cart.
- Say: load-gen sends about 3.4 requests/s through Traefik all the time.

## 2. Metrics (2 min)

Grafana → **Robot Shop: requests, errors and latency**.

- Summary row: requests/s, 5xx %, payment p95, containers ready.
- Per-API panels: "Traefik has one route per API, so we get request rate, errors and latency per API without changing the services."
- Point at **payment p95** (seconds, the slowest): "Why? Tracing answers that."
- SLO row at the bottom: availability, burn rate, budget used.

## 3. Traces (2 min)

```bash
k -n robot-shop logs deploy/payment | grep -o 'trace_id=[0-9a-f]*' | tail -1
```

Open `http://localhost:16686/trace/<id>`: `POST /pay/<id>` with child spans. The `GET https://paypal.com/` span is ~95 % of the time: the slowness is the external gateway, not our code.

## 4. Logs (2 min)

Grafana → Explore → Loki:

```logql
sum by (service, level) (count_over_time({namespace="robot-shop"}[5m]))
{namespace="robot-shop", level=~"error|fatal", instana_noise="false"}
{namespace="robot-shop"} |= "<the trace id from step 3>"
```

The last query finds the same request in user, payment, cart and dispatch logs. On a payment line, click **TraceID** to jump to the trace.

## 5. Alerting and the incident (3 min)

- Prometheus → Alerts: `RobotShopErrorBudgetFastBurn`, `RobotShopErrorBudgetSlowBurn` (inactive).
- `k -n monitoring logs deploy/slack-mock`: the Slack messages from the drill (firing and resolved), each with the runbook link.
- Open the postmortem `docs/postmortems/2026-10-27-catalogue-oom.md`: the timeline, root cause, and the readiness-probe fix.
- Optional live replay (takes ~15 min for the alert to fire):

  ```bash
  helm upgrade robot-shop K8s/helm -n robot-shop -f tracing/robot-shop-tracing-values.yaml \
    -f docs/drills/2026-10-27-bad-release-values.yaml --wait --timeout 2m --rollback-on-failure
  ```

  With the readiness probe in place, the bad pod never becomes ready, the old pod keeps serving, and Helm rolls the release back by itself.

## Wrap-up

`docs/slo.md` (SLO + error-budget policy), `docs/runbooks/robot-shop-availability.md`, `docs/evidence/` (what was run and its output).
