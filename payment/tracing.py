"""OpenTelemetry tracing for the payment service (capstone addition).

Tracing is switched on only when OTEL_EXPORTER_OTLP_ENDPOINT is set, so the
service still runs unchanged without a collector. The other settings come
from the standard OTEL_* environment variables (OTEL_SERVICE_NAME,
OTEL_RESOURCE_ATTRIBUTES, OTEL_TRACES_SAMPLER, ...).

Incoming Flask requests and outgoing `requests` calls (user, cart and the
payment gateway) get spans automatically; payment.py adds a span for
publishing the order to RabbitMQ.
"""
import os

from opentelemetry import trace

tracer = trace.get_tracer('payment')


def init_tracing(app):
    endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
    if not endpoint:
        app.logger.info('tracing disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set')
        return

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # uWSGI runs with lazy-apps, so this runs inside each worker after the
    # fork and the exporter's background thread belongs to that worker
    provider = TracerProvider(resource=Resource.create())
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FlaskInstrumentor().instrument_app(app, excluded_urls='health,metrics')
    RequestsInstrumentor().instrument()
    app.logger.info('tracing enabled: exporting spans to {}'.format(endpoint))


def current_trace_id():
    """Trace ID of the active span as 32 hex digits, or '-' when not traced."""
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, '032x') if ctx.is_valid else '-'
