from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    file: str
    title: str
    category: Literal["policy", "curriculum", "schedule", "registration", "order", "contacts"]
    source_url: str = ""
    authority: str
    effective_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: Literal["current", "superseded", "pending_review"] = "current"
    notes: str = ""
    programmes: list[str] = Field(default_factory=list)
    cohorts: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    semesters: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    synthetic: bool = False


class Manifest(StrictModel):
    institution: str
    synthetic: bool = False
    documents: list[Document]
    # An absent semester means the CSV is NOT known to be exhaustive.
    complete_course_semesters: list[str] = Field(default_factory=list)
    # Completeness may be established for one department without asserting a complete institute list.
    complete_department_semesters: dict[str, list[str]] = Field(default_factory=dict)
    # Topic-specific replacements avoid treating a clause amendment as replacement of an entire regulation.
    topic_overrides: list[dict] = Field(default_factory=list)


class Evidence(StrictModel):
    id: str
    document_id: str
    title: str
    locator: str
    text: str
    source_url: str = ""
    synthetic: bool = False
    applicability_note: str = ""


class Support(StrictModel):
    evidence_id: str
    # When omitted, the application attaches the exact retrieved passage. Models need not retype it.
    quote: str | None = Field(default=None, min_length=8)


class Claim(StrictModel):
    text: str = Field(min_length=1)
    supports: list[Support] = Field(min_length=1)


class AgentAnswer(StrictModel):
    status: Literal["answered", "insufficient_evidence", "needs_clarification"]
    claims: list[Claim] = Field(default_factory=list)
    message: str = ""


class Answer(StrictModel):
    status: Literal["answered", "refused", "needs_clarification", "error"]
    answer: str
    reason: str = ""
    route: str
    mode: str
    model: str
    sources: list[Evidence] = Field(default_factory=list)
    draft: str | None = None
    trace: list[dict] = Field(default_factory=list)
    elapsed_seconds: float = 0
    question_id: str = ""
    synthetic: bool = False
    structural_grounding: bool = False


class CourseRow(StrictModel):
    course_code: str
    title: str
    department: str
    level: int
    course_type: Literal["core", "elective", "unknown"]
    slot: str
    days: str
    time: str
    semester: str
    section: str = ""
    instructor_id: str
    source_document_id: str
    source_locator: str
    slot_document_id: str = ""
    slot_locator: str = ""
    type_document_id: str = ""
    type_locator: str = ""


class FacultyRow(StrictModel):
    instructor_id: str
    name: str
    email: str
    source_document_id: str
    source_locator: str


class ExaminationRow(StrictModel):
    course_code: str
    examination: Literal["major", "minor"]
    semester: str
    date: str
    time: str
    status: Literal["tentative", "revised", "unconfirmed_change"]
    source_document_id: str
    source_locator: str
