"""Glossary endpoints.

GET  /v1/glossary/{locale}              full categorised catalogue
GET  /v1/glossary/{locale}/{term_id}    single term; 404 if unknown

The Flutter client bundles the EN glossary as an asset for offline /
first-launch use, so these routes exist primarily so a future beta
can hot-swap entries without an app release, and so the parent
catalogue screen can read a single source of truth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.glossary import GlossaryCatalogue, GlossaryEntry
from app.services.glossary_service import GlossaryService, get_glossary_service


router = APIRouter(prefix="/v1/glossary", tags=["glossary"])


@router.get("/{locale}", response_model=GlossaryCatalogue)
async def catalogue(
    locale: str,
    svc: GlossaryService = Depends(get_glossary_service),
) -> GlossaryCatalogue:
    return svc.catalogue(locale=locale)


@router.get("/{locale}/{term_id}", response_model=GlossaryEntry)
async def get_term(
    locale: str,
    term_id: str,
    svc: GlossaryService = Depends(get_glossary_service),
) -> GlossaryEntry:
    entry = svc.get(locale, term_id)
    if entry is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"glossary term {term_id} not found",
        )
    return entry
