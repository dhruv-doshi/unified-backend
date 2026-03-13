import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Any


class PaperResponse(BaseModel):
    id: str
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str] | None
    url: str
    categories: list[str] | None
    published_at: datetime | None

    model_config = {"from_attributes": True}


class AIQueryRequest(BaseModel):
    query: str
    limit: int = 5


class AIQueryResponse(BaseModel):
    answer: str
    sources: list[PaperResponse]


class FetchPapersRequest(BaseModel):
    query: str
    max_results: int = 20
    categories: list[str] | None = None
