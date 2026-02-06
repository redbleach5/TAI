"""Assistant API - modes, templates, commands."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_config, get_library, limiter
from src.domain.ports.config import AppConfig
from src.infrastructure.services.assistant_modes import get_mode, list_modes
from src.infrastructure.services.command_parser import get_help_text
from src.infrastructure.services.prompt_templates import PromptLibrary, PromptTemplate
from src.infrastructure.services.web_search import (
    format_search_results,
    multi_search,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# === Modes ===


@router.get("/modes")
@limiter.limit("60/minute")
async def get_modes(request: Request) -> dict:
    """Get available assistant modes."""
    return {"modes": list_modes()}


@router.get("/modes/{mode_id}")
@limiter.limit("60/minute")
async def get_mode_config(request: Request, mode_id: str) -> dict:
    """Get specific mode configuration. Falls back to default mode if not found."""
    config = get_mode(mode_id)
    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "icon": config.icon,
        "temperature": config.temperature,
        "system_prompt": config.system_prompt,
    }


# === Templates ===


class TemplateCreate(BaseModel):
    """Create template request."""

    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=50_000)
    category: str = Field("custom", max_length=100)
    description: str = Field("", max_length=1000)


class TemplateFill(BaseModel):
    """Fill template request."""

    template_id: str = Field(..., min_length=1, max_length=100)
    variables: dict[str, str]


@router.get("/templates")
@limiter.limit("60/minute")
async def list_templates(
    request: Request,
    category: str | None = None,
    library: PromptLibrary = Depends(get_library),
) -> dict:
    """List prompt templates."""
    if category:
        templates = library.list_by_category(category)
    else:
        templates = library.list_all()

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "description": t.description,
            }
            for t in templates
        ],
        "categories": library.get_categories(),
    }


@router.get("/templates/{template_id}")
@limiter.limit("60/minute")
async def get_template(
    request: Request,
    template_id: str,
    library: PromptLibrary = Depends(get_library),
) -> dict:
    """Get template by ID."""
    template = library.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": template.id,
        "name": template.name,
        "content": template.content,
        "category": template.category,
        "description": template.description,
    }


@router.post("/templates")
@limiter.limit("30/minute")
async def create_template(
    request: Request,
    body: TemplateCreate,
    library: PromptLibrary = Depends(get_library),
) -> dict:
    """Create custom template."""
    template = PromptTemplate(
        id=body.id,
        name=body.name,
        content=body.content,
        category=body.category,
        description=body.description,
    )
    if library.add(template):
        return {"status": "ok", "id": template.id}
    raise HTTPException(status_code=409, detail="Template ID already exists")


@router.delete("/templates/{template_id}")
@limiter.limit("30/minute")
async def delete_template(
    request: Request,
    template_id: str,
    library: PromptLibrary = Depends(get_library),
) -> dict:
    """Delete custom template."""
    if library.remove(template_id):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Cannot delete (not found or builtin)")


@router.post("/templates/fill")
@limiter.limit("60/minute")
async def fill_template(
    request: Request,
    body: TemplateFill,
    library: PromptLibrary = Depends(get_library),
) -> dict:
    """Fill template with variables."""
    result = library.fill_template(body.template_id, **body.variables)
    if result is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"content": result}


# === Commands ===


@router.get("/commands/help")
@limiter.limit("60/minute")
async def commands_help(request: Request) -> dict:
    """Get quick commands help."""
    return {"help": get_help_text()}


# === Web Search ===


class WebSearchRequest(BaseModel):
    """Web search request."""

    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(5, ge=1, le=50)


@router.post("/search/web")
@limiter.limit("30/minute")
async def web_search(
    request: Request,
    body: WebSearchRequest,
    config: AppConfig = Depends(get_config),
) -> dict:
    """Search using multiple engines (DuckDuckGo, SearXNG, Brave, Tavily) in parallel."""
    ws = config.web_search
    try:
        results = await multi_search(
            body.query,
            max_results=body.max_results,
            use_cache=True,
            searxng_url=ws.searxng_url,
            brave_api_key=ws.brave_api_key,
            tavily_api_key=ws.tavily_api_key,
            google_api_key=ws.google_api_key,
            google_cx=ws.google_cx,
        )
    except Exception:
        logger.exception("Web search failed for query: %s", body.query)
        raise HTTPException(status_code=502, detail="Web search failed")

    return {
        "query": body.query,
        "results": [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
            }
            for r in results
        ],
        "formatted": format_search_results(results),
    }
