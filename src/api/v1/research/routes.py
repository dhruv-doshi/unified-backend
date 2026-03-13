from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_db, get_verified_user_id
from src.core.exceptions import success_response
from src.domain.research import service as research_service
from src.api.v1.research.schemas import PaperResponse, AIQueryRequest, AIQueryResponse, FetchPapersRequest

router = APIRouter(prefix="/research", tags=["research"])


def _to_paper_response(paper) -> PaperResponse:
    return PaperResponse(
        id=str(paper.id),
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors,
        url=paper.url,
        categories=paper.categories,
        published_at=paper.published_at,
    )


@router.get("/papers")
async def list_papers(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    papers = await research_service.list_papers(db, offset=offset, limit=limit, category=category)
    return success_response([_to_paper_response(p).model_dump() for p in papers])


@router.get("/papers/{paper_id}")
async def get_paper(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
):
    paper = await research_service.get_paper(db, paper_id)
    return success_response(_to_paper_response(paper).model_dump())


@router.get("/search")
async def search_papers(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    papers = await research_service.search_papers(db, q, limit)
    return success_response([_to_paper_response(p).model_dump() for p in papers])


@router.post("/ai-query")
async def ai_query(
    body: AIQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    answer, papers = await research_service.ai_query(db, body.query, body.limit)
    resp = AIQueryResponse(
        answer=answer,
        sources=[_to_paper_response(p) for p in papers],
    )
    return success_response(resp.model_dump())


@router.post("/fetch")
async def fetch_papers(
    body: FetchPapersRequest,
    db: AsyncSession = Depends(get_db),
    _user_id=Depends(get_verified_user_id),
):
    """Admin-triggered fetch from arXiv. Requires auth."""
    papers = await research_service.fetch_papers(
        db,
        query=body.query,
        max_results=body.max_results,
        categories=body.categories,
    )
    return success_response(
        {"fetched": len(papers)},
        f"Fetched and stored {len(papers)} new papers",
    )
