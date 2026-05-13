"""AI Coach Q&A endpoints.

GET /v1/ai_coach/search?q=...        keyword search over the 280 Q&A library
GET /v1/ai_coach/by_id/{id}          single Q&A
GET /v1/ai_coach/by_category/{cat}   all Q&A in a category
GET /v1/ai_coach/categories          available categories
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.ai_coach import (
    CoachCategoryResponse,
    CoachQA,
    CoachSearchResponse,
)
from app.services.ai_coach_service import AICoachService, get_ai_coach_service


router = APIRouter(prefix="/v1/ai_coach", tags=["ai_coach"])


@router.get("/search", response_model=CoachSearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(5, ge=1, le=20),
    svc: AICoachService = Depends(get_ai_coach_service),
) -> CoachSearchResponse:
    hits = svc.search(q, limit=limit)
    return CoachSearchResponse(query=q, hits=hits, total=len(hits))


@router.get("/by_id/{qa_id}", response_model=CoachQA)
async def by_id(
    qa_id: str,
    svc: AICoachService = Depends(get_ai_coach_service),
) -> CoachQA:
    qa = svc.get_by_id(qa_id)
    if qa is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"coach Q&A {qa_id} not found",
        )
    return qa


@router.get("/by_category/{category}", response_model=CoachCategoryResponse)
async def by_category(
    category: str,
    svc: AICoachService = Depends(get_ai_coach_service),
) -> CoachCategoryResponse:
    items = svc.by_category(category)
    return CoachCategoryResponse(
        category=category, items=items, total=len(items),
    )


@router.get("/categories", response_model=list[str])
async def categories(
    svc: AICoachService = Depends(get_ai_coach_service),
) -> list[str]:
    return svc.categories()
