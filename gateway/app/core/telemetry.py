"""OpenTelemetry traces and SLO metrics for the gateway.

Development prints spans to the terminal. Staging and production export OTLP/HTTP.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from opentelemetry import metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("app.core.telemetry")

SERVICE_NAME = "genomiq.gateway"
_READY = False


def setup_telemetry(environment: str, otlp_endpoint: str) -> None:
    """Install the global tracer and meter providers. Safe to call once."""
    global _READY
    if _READY:
        return

    resource = Resource.create({"service.name": SERVICE_NAME})
    tracer_provider = TracerProvider(resource=resource)
    if environment == "development":
        # Immediate console output so a local run shows the trace without a collector.
        tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        metric_reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=30_000,
        )
    else:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_url(otlp_endpoint, "traces")))
        )
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=_otlp_url(otlp_endpoint, "metrics"))
        )

    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
    _READY = True


def shutdown_telemetry() -> None:
    tracer_provider = trace.get_tracer_provider()
    shutdown = getattr(tracer_provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
    meter_provider = metrics.get_meter_provider()
    meter_shutdown = getattr(meter_provider, "shutdown", None)
    if callable(meter_shutdown):
        meter_shutdown()


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(SERVICE_NAME)


def request_duration_histogram() -> metrics.Histogram:
    return metrics.get_meter(SERVICE_NAME).create_histogram(
        name="gateway.http.request.duration",
        unit="ms",
        description="HTTP request duration in milliseconds",
    )


def fhir_validation_failures() -> metrics.Counter:
    return metrics.get_meter(SERVICE_NAME).create_counter(
        name="fhir.validation.failure_rate",
        description="Count of FHIR Bundle validation failures",
    )


def mark_span_error(span: Span, exc: BaseException) -> None:
    """Mark a span failed without copying an exception message (it may contain PHI)."""
    error_class = type(exc).__name__
    span.set_attribute("error_class", error_class)
    span.set_status(Status(StatusCode.ERROR, error_class))
    span.record_exception(type(exc)(error_class))


def inject_trace_context() -> dict[str, str]:
    """Serialize the current W3C trace context. Values are header strings, never PHI."""
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier


def extract_trace_context(carrier: dict[str, Any] | None) -> Any:
    clean: dict[str, str] = {}
    if isinstance(carrier, dict):
        for key, value in carrier.items():
            if isinstance(key, str) and isinstance(value, str):
                clean[key] = value
    return propagate.extract(clean)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Assign X-Request-ID and record gateway.http.request.duration. Does not read the body."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = _correlation_id_from_header(request.headers.get("X-Request-ID"))
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            request_duration_histogram().record(
                duration_ms,
                {"http.method": request.method, "http.status_code": status_code},
            )


def correlation_id_from_request(request: Request) -> str:
    existing = getattr(request.state, "correlation_id", None)
    if isinstance(existing, str) and existing.strip():
        return existing.strip()[:64]
    return _correlation_id_from_header(request.headers.get("X-Request-ID"))


def _correlation_id_from_header(header: str | None) -> str:
    if isinstance(header, str) and header.strip():
        return header.strip()[:64]
    return str(uuid.uuid4())


def _otlp_url(endpoint: str, signal: str) -> str:
    base = endpoint.rstrip("/")
    suffix = f"/v1/{signal}"
    if base.endswith(suffix):
        return base
    return f"{base}{suffix}"
