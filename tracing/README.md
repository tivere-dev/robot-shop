# Tracing: OpenTelemetry Collector and Jaeger

```
payment (OpenTelemetry SDK) --OTLP/HTTP--> otel-collector --OTLP/gRPC--> Jaeger (in memory) --> Jaeger UI, Grafana
```

| File | What it is |
|---|---|
| `otel-collector-values.yaml` | OpenTelemetry Collector chart 0.177.0: OTLP in, adds Kubernetes pod details, batches, sends to Jaeger |
| `jaeger-values.yaml` | Jaeger chart 4.16.1 with Jaeger **2.20.0**, all-in-one, in-memory storage (20,000 traces) |
| `robot-shop-tracing-values.yaml` | Extra values for the Robot Shop chart: use the traced payment image and turn tracing on |
| `../payment/tracing.py`, `../payment/Dockerfile.otel` | The instrumentation and the image build |

Only **payment** is instrumented. It was chosen because the dashboard showed its latency (p95 8-10 s) as the slowest API, and a trace answers why: the call to the external payment gateway (`GET https://paypal.com/`) takes about 95 % of each request.

## Install (from the repository root)

```bash
alias k='kubectl --context capstone'

# 1. Jaeger and the collector
helm install jaeger jaeger --repo https://jaegertracing.github.io/helm-charts \
  --version 4.16.1 -n tracing --create-namespace -f tracing/jaeger-values.yaml
helm install otel-collector opentelemetry-collector \
  --repo https://open-telemetry.github.io/opentelemetry-helm-charts \
  --version 0.177.0 -n tracing -f tracing/otel-collector-values.yaml

# 2. Build the traced payment image inside Minikube (no registry needed)
minikube -p capstone image build -t robot-shop/rs-payment:2.1.0-otel \
  -f Dockerfile.otel payment

# 3. Switch payment to it
helm upgrade robot-shop K8s/helm -n robot-shop -f tracing/robot-shop-tracing-values.yaml

# 4. Grafana datasources (Loki + Jaeger)
k apply -k monitoring/datasources
```

## Look at a trace

```bash
k -n tracing port-forward svc/jaeger 16686:16686
# a trace ID from the payment logs:
k -n robot-shop logs deploy/payment | grep -o 'trace_id=[0-9a-f]*' | tail -1
```

Open `http://localhost:16686/trace/<id>`, or in Grafana → Explore → Loki, query `{service="payment"} |= "trace_id"` and click the **TraceID** link next to a line.

## Why Jaeger 2.20.0 and not the chart's 2.22.0

Jaeger 2.21 removed the old `/api/services` and `/api/traces?service=` endpoints. Grafana 13.2's Jaeger datasource still uses them for its health check, service list and search, so with 2.22.0 they return "404 Not Found" ([grafana/grafana-jaeger-datasource#87](https://github.com/grafana/grafana-jaeger-datasource/issues/87)). Opening a trace by ID still worked. Move to a newer Jaeger once the Grafana plugin uses the `/api/v3` endpoints.

## Python 3.9

The payment image runs Python 3.9.6. The newest OpenTelemetry releases that still support it are SDK **1.41.1** and instrumentation **0.62b1**, so `payment/requirements.txt` pins those.
