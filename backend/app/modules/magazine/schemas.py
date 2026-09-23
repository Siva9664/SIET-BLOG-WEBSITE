from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types.content import ContentStatus, MagazineType


class MagazineAchievementBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None


class MagazineProjectLinkBase(BaseModel):
    title: str = Field(..., max_length=255)
    url: str = Field(..., max_length=500)


class MagazineBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    event_name: str | None = Field(None, max_length=255)
    event_date: datetime | None = None
    department_id: int | None = None
    department_name: str | None = Field(None, max_length=150)
    target_page_budget: int = 4
    magazine_type: MagazineType = MagazineType.SPECIAL
    publication_year: int
    cover_image_id: int | None = None
    pdf_file_id: int | None = None
    cover_image_url: str | None = None
    pdf_url: str | None = None


class MagazineCreate(MagazineBase):
    achievements: list[MagazineAchievementBase] | None = []
    project_links: list[MagazineProjectLinkBase] | None = []


class EventMagazineCreate(BaseModel):
    event_name: str = Field(..., max_length=255)
    title: str = Field(..., max_length=255)
    description: str | None = None
    event_date: str | None = None
    publication_year: int = Field(default_factory=lambda: datetime.now().year)
    magazine_type: str = "special"
    department_id: int | None = None
    department_name: str | None = None
    target_page_budget: int = 4
    gallery_images_json: str | None = None
    writeup_headline: str | None = None
    writeup_text: str | None = None
    writeup_html: str | None = None


class MagazineUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    event_name: str | None = Field(None, max_length=255)
    event_date: datetime | None = None
    department_id: int | None = None
    department_name: str | None = None
    target_page_budget: int | None = None
    magazine_type: MagazineType | None = None
    publication_year: int | None = None
    cover_image_id: int | None = None
    pdf_file_id: int | None = None
    cover_image_url: str | None = None
    pdf_url: str | None = None
    is_featured: bool | None = None


class MagazinePublish(BaseModel):
    status: ContentStatus


class MagazineAchievementResponse(MagazineAchievementBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MagazineProjectLinkResponse(MagazineProjectLinkBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MagazinePageResponse(BaseModel):
    id: int
    magazine_id: int
    page_number: int
    image_url: str
    extracted_text: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MagazineTOCEntryResponse(BaseModel):
    id: int
    magazine_id: int
    page_number: int
    heading: str
    model_config = ConfigDict(from_attributes=True)


class MagazineResponse(MagazineBase):
    id: int
    slug: str
    status: str
    published_at: datetime | None = None
    processed_at: datetime | None = None
    is_featured: bool = True
    featured_until: datetime | None = None
    page_count: int = 0
    failure_reason: str | None = None
    cover_pages: list[dict[str, Any]] | None = None
    body_pages: list[dict[str, Any]] | None = None
    gallery_images: list[dict[str, Any]] | None = None
    editorial_plan: dict[str, Any] | None = None
    orchestrator_score: float | None = None
    pages: list[MagazinePageResponse] = []
    toc_entries: list[MagazineTOCEntryResponse] = []
    achievements: list[MagazineAchievementResponse] = []
    project_links: list[MagazineProjectLinkResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MagazineTemplateResponse(BaseModel):
    id: int
    name: str
    department_id: int | None = None
    department_slug: str | None = None
    template_family: str = "academic_digest"
    page_budget: int = 4
    description: str | None = None
    is_active: bool = True
    section_schema: list[dict[str, Any]] = []
    style_rules: dict[str, Any] = {}
    template_metadata: dict[str, Any] | None = None
    example_outputs: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class TemplateMetadataSchema(BaseModel):
    template_id: str
    name: str
    department: str | None = None
    lab: str | None = None
    department_or_lab: str | None = None
    section: str | None = None
    page_type: str = "article"
    supported_content_types: list[str] = []
    style: str | None = None
    image_count: int = 0
    text_capacity: dict[str, int] = {}
    layout_constraints: dict[str, Any] = {}
    version: int = 1

    model_config = ConfigDict(from_attributes=True)


class TemplateSelectionRequest(BaseModel):
    content: str | dict[str, Any]
    department: str | None = None
    lab: str | None = None
    department_or_lab: str | None = None
    section: str | None = None
    page_type: str | None = None
    available_images: list[Any] = []
    candidate_templates: list[int | str | dict[str, Any]] | None = None
    use_llm: bool = True


class TemplateSelectionResponse(BaseModel):
    template_id: str
    page_type: str
    confidence: float
    reason: str
    metadata: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class MagazineTemplateCreate(BaseModel):
    name: str
    department_id: int | None = None
    department_slug: str | None = None
    lab_id: int | None = None
    is_global: bool = False
    template_family: str = "academic_digest"
    page_budget: int = 4
    description: str | None = None
    section_schema: list[dict[str, Any]] = []
    style_rules: dict[str, Any] = {}
    template_metadata: dict[str, Any] | None = None
    example_outputs: dict[str, Any] | None = None


class PhotoQualityAnalysisSchema(BaseModel):
    width: int
    height: int
    aspect_ratio: float
    orientation: str
    sharpness: float
    brightness: float
    contrast: float
    exposure_status: str
    quality_score: float

    model_config = ConfigDict(from_attributes=True)


class PhotoRankResult(BaseModel):
    photo_id: str
    filename: str
    url: str | None = None
    local_path: str | None = None
    relevance_score: float
    quality_score: float
    combined_score: float
    is_duplicate: bool = False
    duplicate_of: str | None = None
    orientation: str = "landscape"
    recommended_slot: str = "feature_story"
    quality: PhotoQualityAnalysisSchema | None = None
    match_reason: str = ""

    model_config = ConfigDict(from_attributes=True)


class PhotoSelectionRequest(BaseModel):
    article_content: str | dict[str, Any]
    photos: list[dict[str, Any]]
    top_k: int = 5
    filter_duplicates: bool = True
    min_quality_threshold: float = 0.20


class PhotoSelectionResponse(BaseModel):
    ranked_photos: list[PhotoRankResult]
    selected_hero: PhotoRankResult | None = None
    selected_features: list[PhotoRankResult] = []
    selected_gallery: list[PhotoRankResult] = []
    duplicates_detected: int = 0

    model_config = ConfigDict(from_attributes=True)


class PlannedRegion(BaseModel):
    region_id: str
    type: str  # "image" | "headline" | "body" | "caption" | "pullquote" | "kicker" | "stats"
    content: str | None = None
    asset: str | None = None
    aspect_ratio: float | None = None
    caption: str | None = None
    word_count: int | None = None
    role: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PagePlan(BaseModel):
    page_type: str
    template_id: str
    regions: list[PlannedRegion]
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class PlanValidationReport(BaseModel):
    is_valid: bool
    violations: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class LayoutPlanRequest(BaseModel):
    content: str | dict[str, Any]
    department_or_lab: str | None = None
    selected_template: str | dict[str, Any] | None = None
    available_images: list[dict[str, Any]] = []
    template_regions: list[dict[str, Any]] | None = None
    text_limits: dict[str, int] | None = None
    image_constraints: dict[str, Any] | None = None
    use_llm: bool = True


class LayoutPlanResponse(BaseModel):
    plan: PagePlan
    validation: PlanValidationReport

    model_config = ConfigDict(from_attributes=True)


class MultiPagePlannedPage(BaseModel):
    page_number: int
    template_id: str
    content_ids: list[Any]
    section: str | None = None
    page_type: str | None = None
    layout_variant: str | None = None
    assigned_images: list[str] = []
    word_count: int = 0
    items_count: int = 0
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class MultiPagePlanRequest(BaseModel):
    structured_content: dict[str, Any] | list[Any]
    department_or_lab: str | None = None
    available_images: list[Any] = []
    available_templates: list[Any] | None = None
    template_constraints: dict[str, Any] | None = None
    magazine_section_order: list[str] | None = None
    max_pages: int | None = None
    start_page_number: int = 1


class MultiPagePlanResponse(BaseModel):
    pages: list[MultiPagePlannedPage]
    total_pages: int
    section_sequence: list[str] = []
    section_breakdown: dict[str, int] = {}
    department_or_lab: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class VisualQCThresholds(BaseModel):
    min_overall_score: int = 80
    min_dpi: float = 96.0
    min_fontsize: float = 5.5
    max_empty_space_ratio: float = 0.75
    max_distortion_tolerance: float = 0.08
    max_margin_variance: float = 15.0

    model_config = ConfigDict(from_attributes=True)


class VisualQualityReport(BaseModel):
    page: int
    layout_score: int
    image_score: int
    text_fit_score: int
    overall_score: int
    is_valid: bool
    issues: list[str] = []
    metrics: dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class PageRecoveryResult(BaseModel):
    page_num: int
    final_template_id: str
    final_layout_variant: str | None = None
    attempts_taken: int = 1
    passed: bool = True
    initial_report: VisualQualityReport
    final_report: VisualQualityReport
    regeneration_history: list[dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class PageQCRequest(BaseModel):
    plan: PagePlan | dict[str, Any]
    template_metadata: dict[str, Any] | None = None
    thresholds: VisualQCThresholds | None = None
    page_num: int = 1
    with_recovery: bool = False
    max_attempts: int = 3

    model_config = ConfigDict(from_attributes=True)


PIPELINE_STAGES = [
    "Reading documents",
    "Extracting content",
    "Understanding sections",
    "Selecting templates",
    "Matching photographs",
    "Planning pages",
    "Rendering pages",
    "Validating pages",
    "Finalizing magazine",
]


class PipelineProgressStage(BaseModel):
    stage_number: int
    stage_name: str
    status: str = "pending"  # pending, in_progress, completed, failed
    message: str = ""
    details: dict[str, Any] = {}
    elapsed_seconds: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class EndToEndMagazineRequest(BaseModel):
    event_name: str | None = None
    event_date: str | None = None
    department_or_lab: str | None = "AI & Data Science Lab"
    raw_notes: str | None = None
    source_filename: str | None = None
    source_file_base64: str | None = None
    photos: list[dict[str, Any]] = []
    custom_templates: list[dict[str, Any]] = []
    target_page_budget: int = 5
    template_id: int | str | None = None
    publish_immediately: bool = True
    use_llm: bool = True
    max_qc_attempts: int = 3

    model_config = ConfigDict(from_attributes=True)


class EndToEndMagazineResponse(BaseModel):
    magazine_id: int | None = None
    title: str
    slug: str
    department_or_lab: str
    status: str
    pdf_url: str | None = None
    cover_image_url: str | None = None
    total_pages: int
    page_previews: list[str] = []
    toc_entries: list[dict[str, Any]] = []
    stage_telemetry: list[PipelineProgressStage] = []
    qc_reports: list[dict[str, Any]] = []
    overall_quality_score: float = 0.0
    execution_time_seconds: float = 0.0
    notes: str = ""

    model_config = ConfigDict(from_attributes=True)
