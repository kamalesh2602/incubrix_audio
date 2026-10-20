from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings


class SectionSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Section name or role, e.g. 'intro', 'verse'")
    start_s: float = Field(..., ge=0.0, description="Start timestamp in seconds (>= 0)")
    end_s: float = Field(..., gt=0.0, description="End timestamp in seconds (> start_s)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Section name cannot be empty or whitespace only")
        return s

    @model_validator(mode="after")
    def validate_start_before_end(self) -> "SectionSchema":
        if self.start_s >= self.end_s:
            raise ValueError(
                f"Section '{self.name}': start_s ({self.start_s}) must be strictly less than end_s ({self.end_s})"
            )
        return self


class OutputSchema(BaseModel):
    sample_rate: int = Field(
        default=44100,
        description="Audio sample rate (supported: 22050, 44100, 48000)",
    )
    target_lufs: float = Field(
        default=-14.0,
        ge=-30.0,
        le=-6.0,
        description="Target integrated loudness in LUFS (-30 to -6)",
    )
    formats: List[str] = Field(
        default_factory=lambda: ["wav"],
        description="Audio export formats (supported: 'wav')",
    )

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: int) -> int:
        if v not in settings.SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                f"Unsupported sample rate: {v}. Supported sample rates are: {settings.SUPPORTED_SAMPLE_RATES}"
            )
        return v

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Formats list cannot be empty. Supported formats: ['wav']")
        normalized = [fmt.strip().lower() for fmt in v]
        for fmt in normalized:
            if fmt not in settings.SUPPORTED_FORMATS:
                raise ValueError(
                    f"Unsupported format: '{fmt}'. Supported formats are: {settings.SUPPORTED_FORMATS}"
                )
        return normalized


class MusicJobRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000, description="Text prompt describing the desired background music")
    duration_s: float = Field(..., ge=5.0, le=300.0, description="Duration in seconds (5-300 seconds)")
    sections: Optional[List[SectionSchema]] = Field(None, description="Optional timeline section breakdown")
    tempo_bpm: Optional[int] = Field(None, ge=30, le=300, description="Optional tempo in BPM (30-300)")
    key: Optional[str] = Field(None, max_length=50, description="Optional musical key (e.g. 'C major', 'A minor')")
    loopable: Optional[bool] = Field(False, description="Whether the audio should be seamlessly loopable")
    narration_url: Optional[str] = Field(None, description="Optional URL to narration voiceover audio")
    seed: Optional[int] = Field(None, ge=0, le=4294967295, description="Optional seed for deterministic generation")
    output: Optional[OutputSchema] = Field(default_factory=OutputSchema, description="Output audio configuration")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Prompt cannot be empty or whitespace only")
        return s

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        return s

    @field_validator("narration_url")
    @classmethod
    def validate_narration_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        parsed = urlparse(s)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("narration_url must be a valid HTTP or HTTPS URL")
        return s

    @model_validator(mode="after")
    def validate_sections_fit_duration(self) -> "MusicJobRequest":
        if self.sections:
            prev_end = 0.0
            for idx, sec in enumerate(self.sections):
                if sec.end_s > self.duration_s:
                    raise ValueError(
                        f"Section '{sec.name}' end_s ({sec.end_s}) exceeds job duration_s ({self.duration_s})"
                    )
                if sec.start_s < prev_end:
                    raise ValueError(
                        f"Section #{idx + 1} '{sec.name}' start_s ({sec.start_s}) overlaps with preceding section ending at {prev_end}"
                    )
                prev_end = sec.end_s
        return self


class MusicJobResponse(BaseModel):
    job_id: str
    status: str = "queued"
    created_at: datetime
    message: str = "Job accepted and queued for processing"
    job_url: str


class JobResultSchema(BaseModel):
    audio_url: str
    stems: Dict[str, str]
    manifest_url: str
    duration_s: float
    sample_rate: int
    channels: int = 1
    format: str = "wav"
    stem_gains: Dict[str, float]


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[JobResultSchema] = None


class AudioUploadResponse(BaseModel):
    upload_id: str
    filename: str
    content_type: str
    size_bytes: int
    url: str
    message: str = "Audio file uploaded successfully"
