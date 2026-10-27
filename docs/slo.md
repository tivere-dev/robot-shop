# Robot Shop availability SLO and error-budget policy

Owner: Tivere Madagwa · Applies to: Robot Shop on the local Minikube cluster (profile `capstone`) · Version 1, 27 Oct 2026

## What we promise

| | |
|---|---|
| **SLI** (what we measure) | Share of requests to `/api/*` that do **not** return a 5xx status, measured at the Traefik ingress (`traefik_router_requests_total` for the `robot-shop-robot-shop-api-*` routes). |
| **SLO** (the target) | **99.5 %** of `/api` requests succeed, over a rolling **28 days**. |
| **Error budget** | 0.5 % of requests may fail. At today's ~3.4 requests/s (about 8.2 million requests in 28 days) that is about 41,000 failed requests, or roughly **3 h 22 min** of complete outage. |

Why these choices:

- **Measured at the ingress**, because that is what users see and because the Robot Shop services do not report request metrics themselves. It also counts failures when a pod is down completely (Traefik returns 502/503).
- **`/api/*` only.** The static web pages almost never fail, so including them would hide API problems.
- **5xx only.** 4xx means the client sent something wrong (for example, the user service returns 404 for an unknown user, which is normal).
- **99.5 %, not 99.9 %.** This is a single-node demo cluster with no redundancy; restarting it costs a few minutes of errors (the restart on 27 Oct used about 2 % of the budget in one go). With a 99.9 % target each such restart would use about 11 % of the budget, leaving almost no room for real incidents.

## How it is measured and alerted

Rules: [`monitoring/slo/robot-shop-slo-rules.yaml`](../monitoring/slo/robot-shop-slo-rules.yaml). Dashboard row "SLO" on **Robot Shop: requests, errors and latency**.

| Alert | Fires when | Means | Severity, where it goes |
|---|---|---|---|
| `RobotShopErrorBudgetFastBurn` | error ratio > 7.2 % over **1 h** and over **5 min** (14.4× burn), for 2 min | 2 % of the monthly budget gone in an hour; all of it in ~2 days | critical → Slack `#robot-shop-alerts` |
| `RobotShopErrorBudgetSlowBurn` | error ratio > 3 % over **6 h** and over **30 min** (6× burn), for 15 min | 5 % of the budget gone in 6 hours | warning → Slack `#robot-shop-alerts` |

Each alert links to the runbook: [`docs/runbooks/robot-shop-availability.md`](runbooks/robot-shop-availability.md).

Known limit: Prometheus keeps only 24 hours of data on this laptop cluster, so the full 28-day number cannot be calculated. The dashboard shows **how much of the 28-day budget the last 24 hours used** instead (`robotshop:api_error_budget_used_by_last_1d:ratio`). Spending **3.6 %** in one day is the normal pace (100 % ÷ 28).

## Error-budget policy

What we do depends on how much of the 28-day budget is left:

| Budget left | State | What changes |
|---|---|---|
| **More than 50 %** | Normal | Ship changes as usual. Releases go out with `helm upgrade --wait`; roll back first, investigate second. |
| **25–50 %** | Caution | Every release needs a rollback plan written down before it starts. No risky changes (resource limits, database, ingress) on the same day as other releases. |
| **Less than 25 %** | Freeze on features | Only fixes that improve reliability and security fixes are released. The next piece of work must address the top cause of lost budget. |
| **Used up (0 %)** | Full freeze | No releases except fixes for the incident or security issues until the budget recovers to 25 %. A postmortem is required for every incident that used more than 20 % of the budget. |

Also:

- **Any single incident that uses more than 20 % of the budget** gets a blameless postmortem within 2 working days, with owners and dates for each action item ([example](postmortems/2026-10-27-catalogue-oom.md)).
- **If the SLO is met easily for three months in a row**, review whether the target is too low or whether the time can be spent on features instead.
- **Exceptions**: planned drills and cluster restarts announced in advance still count against the budget (users see them), but they do not trigger the freeze on their own. Note them in the incident log.
- **Who decides**: the service owner applies this policy; disagreements go to the course instructor.
