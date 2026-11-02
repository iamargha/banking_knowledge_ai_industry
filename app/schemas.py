from datetime import date
from typing import Any
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    department: str = Field(min_length=2, max_length=64)
    document_type: str = Field(default='POLICY', max_length=64)
    document_id: str = Field(min_length=2, max_length=128)
    version: str = Field(default='1', max_length=32)
    effective_date: date | None = None
    classification: str = Field(default='INTERNAL', max_length=32)

class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)

class Source(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_id: str
    score: float | None = None
    version: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    request_id: str
    abstained: bool = False

class IngestResponse(BaseModel):
    status: str
    document_id: str
    content_sha256: str
    pages_processed: int
    chunks_indexed: int
    warnings: list[str] = []
