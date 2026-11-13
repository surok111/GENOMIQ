import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.logging import REDACTED, configure_logging, get_logger, redact_phi
from app.core.telemetry import extract_trace_context, inject_trace_context
from app.workers.task_worker import _parse_message


def test_redact_phi_replaces_deny_listed_keys_recursively() -> None:
    event = {
        "event": "task_accepted",
        "task_id": "abc",
        "correlation_id": "corr-1",
        "status": "queued",
        "nested": {
            "patient_reference": "Patient/123",
            "raw_data": "CT",
            "callback_url": "https://lis.example/cb",
            "specimen": "Specimen/9",
            "payload": {"raw_data": "CT"},
            "notes": ["ok", {"patient": "hidden"}],
        },
    }

    cleaned = redact_phi(None, "info", event)

    assert cleaned["task_id"] == "abc"
    assert cleaned["correlation_id"] == "corr-1"
    assert cleaned["nested"]["patient_reference"] == REDACTED
    assert cleaned["nested"]["raw_data"] == REDACTED
    assert cleaned["nested"]["callback_url"] == REDACTED
    assert cleaned["nested"]["specimen"] == REDACTED
    assert cleaned["nested"]["payload"] == REDACTED
    assert cleaned["nested"]["notes"][1]["patient"] == REDACTED
    assert cleaned["nested"]["notes"][0] == "ok"


def test_json_log_line_does_not_contain_raw_genomic_input(capsys) -> None:  # type: ignore[no-untyped-def]
    configure_logging()
    get_logger("test").info(
        "task_accepted",
        task_id="abc",
        correlation_id="corr-1",
        status="queued",
        raw_data="rs1801133:CT",
        patient_reference="Patient/secret",
    )
    line = capsys.readouterr().out
    payload = json.loads(line)
    assert payload["task_id"] == "abc"
    assert payload["raw_data"] == REDACTED
    assert payload["patient_reference"] == REDACTED
    assert "rs1801133" not in line
    assert "Patient/secret" not in line


def test_trace_context_round_trip_keeps_the_same_trace() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("gateway.payload.validate"):
        carrier = inject_trace_context()

    assert "traceparent" in carrier
    parent = extract_trace_context(carrier)
    with tracer.start_as_current_span("worker.task", context=parent):
        pass

    spans = exporter.get_finished_spans()
    assert spans[0].context.trace_id == spans[1].context.trace_id
    assert spans[1].parent is not None
    assert spans[1].parent.span_id == spans[0].context.span_id


def test_parse_message_keeps_correlation_id_and_trace_context() -> None:
    import uuid

    task_id = uuid.uuid4()
    raw = json.dumps(
        {
            "task_id": str(task_id),
            "correlation_id": "corr-9",
            "trace_context": {"traceparent": "00-abc-def-01"},
            "payload": {"raw_data": "CT"},
        }
    )
    job = _parse_message(raw)
    assert job.task_id == task_id
    assert job.correlation_id == "corr-9"
    assert job.trace_context == {"traceparent": "00-abc-def-01"}
    assert job.payload["raw_data"] == "CT"
