"""Pydantic models for the NomenAudio API."""

from typing import Literal

from pydantic import BaseModel, Field


class TechnicalInfo(BaseModel):
    """Read-only technical fields from WAV fmt + data chunks."""

    sample_rate: int
    bit_depth: int
    channels: int
    duration_seconds: float
    frame_count: int
    audio_format: str
    file_size_bytes: int


class BextInfo(BaseModel):
    """Read-only BEXT chunk fields."""

    description: str | None = None
    originator: str | None = None
    originator_date: str | None = None
    originator_time: str | None = None
    time_reference: int | None = None
    coding_history: str | None = None


class RiffInfo(BaseModel):
    """Read-only RIFF INFO chunk fields."""

    title: str | None = None
    artist: str | None = None
    genre: str | None = None
    comment: str | None = None
    created_date: str | None = None
    software: str | None = None
    copyright: str | None = None
    product: str | None = None
    keywords: str | None = None


class ClassificationMatch(BaseModel):
    """A single UCS classification result from CLAP."""

    cat_id: str
    category: str
    subcategory: str
    category_full: str
    confidence: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    """Full analysis output for a file."""

    classification: list[ClassificationMatch]
    caption: str | None = None
    model_version: str
    analyzed_at: str


SuggestionSource = Literal["clap", "clapcap", "derived", "generated"]


class Suggestion(BaseModel):
    """A single field suggestion from the ML pipeline."""

    value: str
    source: SuggestionSource
    confidence: float | None = None


class SuggestionsResult(BaseModel):
    """Per-field suggestions derived from analysis."""

    category: Suggestion | None = None
    subcategory: Suggestion | None = None
    cat_id: Suggestion | None = None
    category_full: Suggestion | None = None
    fx_name: Suggestion | None = None
    description: Suggestion | None = None
    keywords: Suggestion | None = None
    suggested_filename: Suggestion | None = None


class AnalyzeRequest(BaseModel):
    """Request body for POST /files/{id}/analyze."""

    tiers: list[int] = [1]
    force: bool = False


class BatchAnalyzeRequest(BaseModel):
    """Request body for POST /files/analyze-batch."""

    file_ids: list[str] = []
    tiers: list[int] = [1]
    force: bool = False


FileStatus = Literal["unmodified", "modified", "saved", "flagged"]


class FileRecord(BaseModel):
    """Central API object — one WAV file and all its metadata."""

    # Identity
    id: str
    path: str
    filename: str
    directory: str

    # Status
    status: FileStatus = "unmodified"
    changed_fields: list[str] = []

    # Technical (read-only)
    technical: TechnicalInfo

    # UCS Classification
    category: str | None = None
    subcategory: str | None = None
    cat_id: str | None = None
    category_full: str | None = None
    user_category: str | None = None

    # Naming & Description
    fx_name: str | None = None
    description: str | None = None
    keywords: str | None = None
    notes: str | None = None

    # Project & Creator
    designer: str | None = None
    library: str | None = None
    project: str | None = None

    # Preserved fields
    microphone: str | None = None
    mic_perspective: str | None = None
    rec_medium: str | None = None
    release_date: str | None = None
    rating: str | None = None
    is_designed: str | None = None

    # ASWG extended fields
    manufacturer: str | None = None
    rec_type: str | None = None
    creator_id: str | None = None
    source_id: str | None = None

    # Custom fields
    custom_fields: dict[str, str] | None = None

    # Filename generation
    suggested_filename: str | None = None
    rename_on_save: bool = True

    # Embedded chunks (read-only)
    bext: BextInfo | None = None
    info: RiffInfo | None = None

    # ML pipeline (Phase 4)
    analysis: AnalysisResult | None = None
    suggestions: SuggestionsResult | None = None


class MetadataUpdate(BaseModel):
    """PUT /files/{id}/metadata body. All fields optional."""

    category: str | None = None
    subcategory: str | None = None
    cat_id: str | None = None
    category_full: str | None = None
    user_category: str | None = None
    fx_name: str | None = None
    description: str | None = None
    keywords: str | None = None
    notes: str | None = None
    designer: str | None = None
    library: str | None = None
    project: str | None = None
    microphone: str | None = None
    mic_perspective: str | None = None
    rec_medium: str | None = None
    release_date: str | None = None
    rating: str | None = None
    is_designed: str | None = None
    manufacturer: str | None = None
    rec_type: str | None = None
    creator_id: str | None = None
    source_id: str | None = None
    suggested_filename: str | None = None
    custom_fields: dict[str, str] | None = None


class SaveRequest(BaseModel):
    """Request body for POST /files/{id}/save."""

    rename: bool = True
    save_copy: bool = False
    copy_path: str | None = None


class SaveResponse(BaseModel):
    """Response body for POST /files/{id}/save."""

    success: bool
    file: FileRecord
    old_path: str
    new_path: str
    renamed: bool
    copied: bool = False
    copy_path: str | None = None


class BatchSaveRequest(BaseModel):
    """Request body for POST /files/save-batch."""

    file_ids: list[str]
    rename: bool = True


class BatchSaveResult(BaseModel):
    """Per-file result in a batch save."""

    id: str
    success: bool
    renamed: bool = False
    new_path: str | None = None
    error: str | None = None


class BatchSaveResponse(BaseModel):
    """Response body for POST /files/save-batch."""

    results: list[BatchSaveResult]
    saved_count: int
    failed_count: int


class ApplyMetadataRequest(BaseModel):
    """Request body for POST /files/apply-metadata."""

    source_id: str
    target_ids: list[str]
    fields: list[str]


class ApplyMetadataResponse(BaseModel):
    """Response body for POST /files/apply-metadata."""

    updated: list[FileRecord]
    count: int


class ImportRequest(BaseModel):
    """Request body for POST /files/import."""

    directory: str
    recursive: bool = True


class ImportResponse(BaseModel):
    """Response body for POST /files/import."""

    files: list[FileRecord]
    count: int
    skipped: int
    skipped_paths: list[str]
    import_time_ms: int


class BatchUpdateRequest(BaseModel):
    """Request body for POST /files/batch-update."""

    file_ids: list[str]
    updates: dict[str, str]


class BatchUpdateResponse(BaseModel):
    """Response body for POST /files/batch-update."""

    updated: list[FileRecord]
    count: int
