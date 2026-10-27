# Postmortem: catalogue down after a memory-limit change (incident drill)

| | |
|---|---|
| **Date** | 27 October 2026 (times in UTC) |
| **Type** | Planned incident drill: the fault was injected on purpose, everything after it was handled as a real incident |
| **Severity** | High: browsing, cart and checkout unusable while catalogue was down |
| **Duration** | 15:16:43 → 19:33:56 by the clock (4 h 17 min); about **38 min** of that with the cluster actually running (see "What made it longer") |
| **Error budget used** | ≈ 1,100 failed requests ≈ **2.7 %** of the 28-day budget |
| **Author** | Tivere Madagwa · blameless: this is about the system and the process, not about who typed the change |
| **Evidence** | [docs/evidence/c2-7-incident-drill.txt](../evidence/c2-7-incident-drill.txt) |

## Summary

A Helm release (revision 10) lowered the memory limit of the **catalogue** service from 100Mi to 24Mi to save memory on the crowded cluster. Catalogue needs about 37 MiB idle and 51 MiB under load, so the kernel killed it (OOMKilled) every time it started. Because catalogue had **no readiness probe**, Kubernetes treated the new pod as ready the moment its container started and removed the old, healthy pod. Every `/api/catalogue` request then failed with 502. The load generator's user journeys start by browsing the catalogue, so traffic to cart, shipping and payment fell to zero: nobody could buy anything. The slow-burn SLO alert reached Slack 22½ minutes after the release; the release was rolled back with `helm rollback`.

## Impact

- `/api/catalogue`: 100 % of requests failed (502 Bad Gateway from `web`'s nginx).
- No orders: the last successful payment trace in Jaeger started at **15:17:09**, 26 s after the release.
- Cart, shipping, payment, ratings: 0 requests/s (from 0.6–0.9 req/s each), because user journeys stopped at the product list.
- Overall `/api` error ratio rose from ~1 % to **~52 %** (5-minute window).

## Timeline (UTC)

| Time | Event |
|---|---|
| 15:15:30 | Baseline: catalogue running, `/api` errors 0 % over 5 min. |
| **15:16:43** | **Release 10 deployed** (`helm upgrade` without `--wait`): catalogue memory limit 100Mi → 24Mi. Helm reports "deployed" one second later. |
| 15:17:01 | New catalogue pod `OOMKilled`; old pod already terminating. |
| 15:17:09 | Last payment trace in Jaeger (no checkouts after this). |
| 15:19:03 | 5-minute error ratio passes 7 %. |
| 15:23:14 | `RobotShopErrorBudgetSlowBurn` pending. |
| 15:26 | catalogue in `CrashLoopBackOff` (restart 6). Error ratio ~50 %. |
| 15:38:14 | `RobotShopErrorBudgetFastBurn` pending (1-hour window passes 7.2 %). |
| **15:39:16** | **Slack: `[FIRING] RobotShopErrorBudgetSlowBurn`** with runbook link (detection: 22½ min after the release). |
| ~15:39 | Investigation following the runbook (see below). The laptop then went to sleep, which paused the Minikube cluster. |
| 16:28:14 | Slack: **false** `[RESOLVED] RobotShopErrorBudgetSlowBurn`: during the sleep Prometheus had no data, the alert expression returned nothing, and Alertmanager treated that as resolved. The outage was still going on. |
| 18:04, 18:38 | Short wake-ups: catalogue still crash-looping (restarts 17, 20). |
| 19:09:26 | Slack: `[FIRING] RobotShopErrorBudgetSlowBurn` again. |
| **19:33:53** | **Mitigation: `helm rollback robot-shop 9`** → revision 11. |
| 19:33:56 | Healthy catalogue pod running; 502s stop. |
| 19:35:04 | **Fix deployed** (revision 12): readiness probe + `maxUnavailable: 0` for catalogue. |
| 19:35:16–19:37:18 | **Fix verified**: the same bad release again, with `--wait --rollback-on-failure`. The bad pod never became ready, the old pod kept serving (96 × 200, 0 × 502), Helm rolled back by itself (revision 13 failed → 14). |
| 19:36:23 | Slack: `[FIRING] RobotShopErrorBudgetFastBurn`, 2½ minutes *after* the rollback (its windows still contained the errors). |
| 19:39 | Alert rules changed: `keep_firing_for: 10m` so a data gap no longer sends a false RESOLVED. |
| 19:41:23 | Slack: `[RESOLVED] RobotShopErrorBudgetFastBurn`. |

## How it was investigated (runbook steps)

1. **Which API?** Prometheus: `/api/catalogue` 100 % 5xx (502); the other APIs had almost no traffic left.
2. **Pods?** `catalogue` `OOMKilled`, exit code 137, 9 restarts, `Limits: memory 24Mi`.
3. **What changed?** `helm history`: revision 10 at 15:16:43. `helm get values` diff 9 → 10: `memory: 100Mi → 24Mi` (limit) and `50Mi → 24Mi` (request). Nothing else.
4. **Logs (Loki)** `{service="web", level="error"}`: `connect() failed (111: Connection refused) while connecting to upstream` and `GET /api/catalogue/products ... 502`. Catalogue's own logs stop during start-up: the kernel kills the process before it logs anything.
5. **Traces (Jaeger)**: payment traces stop at 15:17:09. Payment itself was healthy; it simply received no requests.

## Root cause

The memory limit set for catalogue (24Mi) was below the memory the Node.js process needs to start (~37 MiB), so it was killed on every start.

## Contributing factors

1. **No readiness probe on catalogue.** Kubernetes only keeps the old pod until the new one is *ready*. Without a probe, "ready" means "the container started", so a pod that crashes seconds later still replaced the healthy one. (The default rolling update would have kept the old pod if readiness had meant "can serve requests".)
2. **The release did not wait.** `helm upgrade` without `--wait` reports success as soon as the objects are created, so nothing checked that catalogue still worked and nothing rolled back automatically.
3. **The new limit was not checked against real usage.** The dashboard's *Memory as % of limit* panel shows catalogue at ~37 % of 100Mi (51 MiB peak); 24Mi is below that.
4. **Detection was slow.** The fast-burn alert needs the 1-hour error ratio above 7.2 %; starting from ~1 %, that took 21 minutes, and then its 2-minute `for` was interrupted by the sleep. The slow-burn alert (22½ min) paged first.

## What made it longer: the laptop slept

The cluster runs inside Docker Desktop on a laptop. While the laptop slept (about 15:39–19:32, with short wake-ups) the cluster was paused: no traffic, no Prometheus scrapes (76 of 515 scrape slots have data). That turned a ~25-minute drill into 4 hours by the clock, sent a false RESOLVED, and delayed the fast-burn page until after the fix. In a real environment the monitoring would not sleep, but the false RESOLVED shows a real weakness: **missing data must not look like recovery**.

## What went well

- The slow-burn alert reached Slack (via the Slack route) with the runbook link, and the runbook led straight to the cause: metrics → pod status → `helm history` → values diff took a few minutes.
- Logs and traces agreed with the metrics: nginx "connection refused" in Loki, payments stopping in Jaeger.
- `helm rollback` fixed it in 3 seconds.

## Action items

| # | Action | Type | Owner | Status |
|---|---|---|---|---|
| 1 | Readiness probe on catalogue (`/health`) and `maxUnavailable: 0` | prevent | Tivere | **Done** (chart 1.3.0, revision 12); verified by replaying the bad release |
| 2 | Release with `helm upgrade --wait --rollback-on-failure` | prevent | Tivere | **Done** in the demo script; verified (revision 13 rolled back automatically) |
| 3 | `keep_firing_for: 10m` on both SLO alerts so a data gap does not send RESOLVED | detect | Tivere | **Done** (loaded in Prometheus at 19:39) |
| 4 | Readiness probes for the other services that have none (cart, user, payment, shipping, ratings, dispatch, web) | prevent | Tivere | Open |
| 5 | Before lowering a resource limit, check the *Memory as % of limit* panel (peak over 24 h) and keep at least 30 % headroom | process | Tivere | Open (added to the runbook's common causes) |
| 6 | Alert when Prometheus has no recent Traefik data (`absent_over_time(traefik_router_requests_total[5m])`), so monitoring gaps are visible | detect | Tivere | Open |
| 7 | Keep the laptop awake during drills and demos (for example `caffeinate -dimsu`) | environment | Tivere | Open |

## Lessons

- A readiness probe is what lets Kubernetes protect you from a bad release. Without one, a crash-looping pod is "ready".
- Burn-rate alerts trade speed for fewer false alarms: from a quiet start, even a 50 % error rate took ~20 minutes to page.
- Missing data must not look like recovery.
