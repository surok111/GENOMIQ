from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class GenomicReportRequest(BaseModel):
    """Inbound payload from a Laboratory Information System (LIS)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    patient_reference: str = Field(
        ...,
        description="Opaque patient identifier/reference (never raw demographics).",
    )
    specimen_reference: str = Field(
        ...,
        description="Opaque specimen identifier/reference.",
    )
    # Genomic data is PHI: excluded from repr() so it can't leak via logs/tracebacks.
    raw_data: str = Field(
        ...,
        repr=False,
        description="Raw genomic data payload.",
    )
    callback_url: HttpUrl = Field(
        ...,
        description="URL the interpretation result will be delivered to.",
    )

    @field_validator("patient_reference")
    @classmethod
    def patient_reference_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("patient_reference must not be empty")
        return value


class GenomicReportAccepted(BaseModel):
    """Response returned when a request has been accepted for processing."""

    status: str = "Accepted"
    message: str = "Data received, processing started"