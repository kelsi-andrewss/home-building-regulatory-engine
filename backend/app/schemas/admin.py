from pydantic import BaseModel


class IngestRequest(BaseModel):
    name: str
    url: str
    specific_plan: str


class IngestionResponse(BaseModel):
    status: str  # "completed" | "failed"
    document_name: str
    fragments_extracted: int
    fragments_flagged: int
    errors: list[str]
