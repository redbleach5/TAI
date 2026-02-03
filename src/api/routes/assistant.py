"""Assistant API - modes, templates, commands."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.dependencies import get_config, get_library, limiter
from src.domain.ports.config import AppConfig
from src.infrastructure.services.assistant_modes import get_mode, list_modes
from src.infrastructure.services.command_parser import get_help_text
from src.infrastructure.services.prompt_templates import PromptLibrary, PromptTemplate
from src.infrastructure.services.web_search import (
    format_search_results,
    multi_search,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# === Modes ===


@router.get("/modes")
@limiter.limit("60/minute")
async def get_modes(request: Request):
    """Get available assistant modes."""
    return {"modes": list_modes()}


@router.get("/modes/{mode_id}")
@limiter.limit("60/minute")
async def get_mode_config(request: Request, mode_id: str):
    """Get specific mode configuration."""
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

    id: str
    name: str
    content: str
    category: str = "custom"
    description: str = ""


class TemplateFill(BaseModel):
    """Fill template request."""

    template_id: str
    variables: dict[str, str]


@router.get("/templates")
@limiter.limit("60/minute")
async def list_templates(
    request: Request,
    category: str | None = None,
    library: PromptLibrary = Depends(get_library),
):
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
):
    """Get template by ID."""
    template = library.get(template_id)
    if not template:
        return {"error": "Template not found"}

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
):
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
    return {"status": "error", "error": "Template ID already exists"}


@router.delete("/templates/{template_id}")
@limiter.limit("30/minute")
async def delete_template(
    request: Request,
    template_id: str,
    library: PromptLibrary = Depends(get_library),
):
    """Delete custom template."""
    if library.remove(template_id):
        return {"status": "ok"}
    return {"status": "error", "error": "Cannot delete (not found or builtin)"}


@router.post("/templates/fill")
@limiter.limit("60/minute")
async def fill_template(
    request: Request,
    body: TemplateFill,
    library: PromptLibrary = Depends(get_library),
):
    """Fill template with variables."""
    result = library.fill_template(body.template_id, **body.variables)
    if result is None:
        return {"error": "Template not found"}
    return {"content": result}


# === Commands ===


@router.get("/commands/help")
@limiter.limit("60/minute")
async def commands_help(request: Request):
    """Get quick commands help."""
    return {"help": get_help_text()}


# === Web Search ===


class SearchRequest(BaseModel):
    """Web search request."""

    query: str
    max_results: int = 5


@router.post("/search/web")
@limiter.limit("30/minute")
async def web_search(
    request: Request,
    body: SearchRequest,
    config: AppConfig = Depends(get_config),
):
    """Search using multiple engines (DuckDuckGo, SearXNG, Brave, Tavily) in parallel."""
    ws = config.web_search
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
