from pydantic import BaseModel
import uuid
from datetime import datetime


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    image: str | None = None


class GalleryItem(BaseModel):
    id: uuid.UUID
    url: str | None
    thumbnailUrl: str | None
    uploadedAt: datetime
    filename: str
    overallScore: int | None = None
    summaryHeadline: str | None = None
    status: str


class GalleryResponse(BaseModel):
    data: list[GalleryItem]
    total: int
    page: int
    limit: int
    hasNext: bool
