"""FastAPI app for the local web panel.

Endpoints (all under `/api`, JSON in/out unless noted):

* ``POST /api/translate``        — body ``{text, target_lang?}`` → translation
* ``POST /api/brief``            — body ``{idea, target_lang?}`` → brief draft + post_id
* ``POST /api/draft/{post_id}``  → generated draft text
* ``POST /api/detect/{post_id}`` → detector flags
* ``POST /api/publish/{post_id}``— body ``{url}`` → publishes
* ``GET  /api/posts``            → list of post records
* ``GET  /api/posts/{post_id}``  → single post + brief + draft if present

The app reuses every module in ``pipeline.*``. Provider creation is delegated
to a small accessor so tests can override it with a stub.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from pipeline import auth as _auth
from pipeline import paths as _paths
from pipeline.brief_builder import BriefBuildError, BriefDraft, IdeaToBrief
from pipeline.config import Settings, get_settings
from pipeline.detectors import DetectionResult, LocalKillListDetector
from pipeline.detectors.llm_judge import DetectorParseError, LLMJudgeDetector
from pipeline.llm import LLMProvider, MissingAPIKeyError, build_provider
from pipeline.llm.base import RateLimitError
from pipeline.logging_config import get_logger
from pipeline.models import PostRecord, PostStatus, RetentionAnswer, now_iso
from pipeline.repository import PostNotFoundError, PostRepository
from pipeline.templating import render_master_prompt
from pipeline.transcript import parse as parse_transcript
from pipeline.translation import TranslationParseError, Translator

LOG = get_logger(__name__)

ProviderFactory = Callable[[Settings], LLMProvider]

_SLUG_RE = re.compile(r"[^a-zA-Z0-9\s-]+")
_SPACE_RE = re.compile(r"[\s_-]+")


def _slugify(text: str) -> str:
    cleaned = _SLUG_RE.sub("", text).strip().lower()
    return _SPACE_RE.sub("-", cleaned).strip("-")


def _make_post_id(title: str) -> str:
    today = datetime.now(timezone.utc)
    slug = _slugify(title)
    if not slug:
        raise ValueError(f"Title produces empty slug: {title!r}")
    return f"{today:%Y%m%d}-{slug}"


# --- Request / response models ---------------------------------------------


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "en"


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    needed_translation: bool


class BriefRequest(BaseModel):
    idea: str
    target_lang: str = "en"


class BriefResponse(BaseModel):
    post_id: str
    brief_path: str
    working_title: str
    one_big_idea: str
    why_now: str
    target_hook: str
    target_framework: str
    reader_transformation: str
    forbidden_moves: list[str]
    source_language: str
    original_text: str
    translated_text: str
    needed_translation: bool
    rendered_markdown: str


class DraftResponse(BaseModel):
    post_id: str
    draft_path: str
    text: str
    word_count: int


class DetectFlag(BaseModel):
    pattern: str
    snippet: str
    line_approx: int


class DetectResponse(BaseModel):
    post_id: str
    passed: bool
    flags: list[DetectFlag]
    detector: str


class PublishRequest(BaseModel):
    url: str


class PublishResponse(BaseModel):
    post_id: str
    substack_url: str
    published_at: str


class PostsListResponse(BaseModel):
    posts: list[PostRecord]


class PostDetail(BaseModel):
    post: PostRecord
    brief_text: str | None = None
    draft_text: str | None = None
    published_text: str | None = None


class StatusResponse(BaseModel):
    provider: str
    model: str
    has_active_provider_key: bool
    brand_name: str
    cadence_days: int


class ErrorResponse(BaseModel):
    detail: str


# --- Auth + Admin models --------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str


class AdminFileListItem(BaseModel):
    path: str
    category: str
    label: str
    size: int
    modified_at: str
    deletable: bool = False


class AdminFileBody(BaseModel):
    path: str
    content: str


class TranscriptParseRequest(BaseModel):
    content: str
    filename: str | None = None


class TranscriptParseResponse(BaseModel):
    text: str
    detected_format: str
    line_count: int
    word_count: int
    speakers: list[str]


# Whitelist of fixed editable paths. Anything else must match a dynamic rule
# (currently: corpus/{writer}/{post}.md).
_FIXED_EDITABLE_FILES: dict[str, tuple[str, str]] = {
    "voice/voice_map.md": ("voice", "Voice fingerprint map"),
    "voice/brand_promise.md": ("voice", "Brand promise"),
    "voice/ai_tells_killlist.md": ("voice", "AI tells kill list"),
    "prompts/master_system_prompt.md": ("prompts", "Master system prompt"),
    "prompts/ai_tells_detector_prompt.md": ("prompts", "AI tells detector prompt"),
    "libraries/hook_library.md": ("libraries", "Hook library"),
    "libraries/structure_library.md": ("libraries", "Structure library"),
    "briefs/_TEMPLATE.md": ("briefs", "Brief template"),
    "data/config.json": ("config", "Brand + cadence config"),
}


def _resolve_editable_path(rel_path: str) -> tuple[Path, str, bool]:
    """Validate that `rel_path` is editable. Returns (abs_path, category, deletable).

    Rejects path traversal and any path outside the editable set.
    """
    rel = rel_path.strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise HTTPException(status_code=400, detail=f"invalid path: {rel_path!r}")

    root = _paths.PROJECT_ROOT
    abs_path = (root / rel).resolve()
    try:
        abs_path.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes project root") from exc

    if rel in _FIXED_EDITABLE_FILES:
        category = _FIXED_EDITABLE_FILES[rel][0]
        return abs_path, category, False

    # Corpus rule: corpus/{writer}/{post}.md, single nesting level.
    parts = rel.split("/")
    if (
        len(parts) == 3
        and parts[0] == "corpus"
        and parts[2].endswith(".md")
        and parts[1]
        and not parts[1].startswith(".")
        and not parts[2].startswith(".")
    ):
        return abs_path, "corpus", True

    raise HTTPException(status_code=403, detail=f"path not editable: {rel}")


# --- Helpers ---------------------------------------------------------------


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _latest_draft_path(post_id: str) -> Path | None:
    matches = sorted(_paths.DRAFTS_DIR.glob(f"{post_id}_v*.md"))
    return matches[-1] if matches else None


def _latest_published_path(post_id: str) -> Path | None:
    matches = sorted(_paths.PUBLISHED_DIR.glob(f"{post_id}_v*.md"))
    return matches[-1] if matches else None


def _ensure_provider(provider_factory: ProviderFactory) -> LLMProvider:
    settings = get_settings()
    if not settings.has_active_provider_key():
        raise HTTPException(
            status_code=400,
            detail=(
                f"No API key for provider={settings.llm_provider}. "
                "Set the corresponding key in .env."
            ),
        )
    try:
        return provider_factory(settings)
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _rate_limit_http(exc: RateLimitError) -> HTTPException:
    """Convert a provider RateLimitError into a 429 response."""
    seconds = exc.retry_after_seconds
    if seconds is None or seconds <= 0:
        seconds = 30.0
    headers = {"Retry-After": str(int(seconds))}
    detail = (
        f"Rate-limited by provider. Retry in ~{int(seconds)}s. "
        "Free-tier Gemini: ~10–20 req/min on 2.5-flash. "
        "Upgrade billing or switch model in .env."
    )
    return HTTPException(status_code=429, detail=detail, headers=headers)


# --- App factory -----------------------------------------------------------


def create_app(provider_factory: ProviderFactory | None = None) -> FastAPI:
    factory = provider_factory or build_provider

    web_dir = Path(__file__).resolve().parent
    templates_dir = web_dir / "templates"
    static_dir = web_dir / "static"

    # React SPA build output. If `webapp/dist/` exists we serve it as the root
    # UI; otherwise we fall back to the legacy template-based panel.
    project_root = Path(__file__).resolve().parents[3]
    spa_dir = project_root / "webapp" / "dist"
    spa_index = spa_dir / "index.html"

    app = FastAPI(title="Stack Hub Pipeline", docs_url="/api/docs", redoc_url=None)
    templates = Jinja2Templates(directory=str(templates_dir))
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    if spa_dir.exists() and (spa_dir / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(spa_dir / "assets")),
            name="spa-assets",
        )

    # ---- Auth helpers (closures over the app for dependency injection) ---

    def _current_user_optional(
        session_cookie: str | None = Cookie(default=None, alias=_auth.COOKIE_NAME),
    ) -> _auth.User | None:
        if _auth.auth_disabled():
            return _auth.User(username="anonymous", role="admin")
        if not session_cookie:
            return None
        try:
            return _auth.decode_session(session_cookie)
        except _auth.AuthError:
            return None

    def require_user(user: _auth.User | None = Depends(_current_user_optional)) -> _auth.User:
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        return user

    def require_admin(user: _auth.User = Depends(require_user)) -> _auth.User:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin role required")
        return user

    # ---- Page -------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        if spa_index.exists():
            return HTMLResponse(content=spa_index.read_text(encoding="utf-8"))
        settings = get_settings()
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "brand": settings.brand_name,
                "provider": settings.llm_provider,
                "model": settings.model_for(),
                "key_present": settings.has_active_provider_key(),
            },
        )


    # ---- Auth -------------------------------------------------------------

    @app.post("/api/auth/login", response_model=LoginResponse)
    def auth_login(payload: LoginRequest, response: Response) -> LoginResponse:
        try:
            user = _auth.authenticate(payload.username, payload.password)
        except _auth.AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        token = _auth.encode_session(user)
        response.set_cookie(
            key=_auth.COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=_auth._max_age_seconds(),  # noqa: SLF001
            path="/",
        )
        return LoginResponse(username=user.username, role=user.role)

    @app.post("/api/auth/logout")
    def auth_logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(_auth.COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/auth/me", response_model=LoginResponse)
    def auth_me(
        user: _auth.User | None = Depends(_current_user_optional),
    ) -> LoginResponse:
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        return LoginResponse(username=user.username, role=user.role)

    # ---- Meeting transcript ingestion ------------------------------------

    @app.post(
        "/api/meeting/parse",
        response_model=TranscriptParseResponse,
        responses={400: {"model": ErrorResponse}},
    )
    def meeting_parse(
        payload: TranscriptParseRequest,
        _user: _auth.User = Depends(require_user),
    ) -> TranscriptParseResponse:
        if not payload.content.strip():
            raise HTTPException(status_code=400, detail="content must not be empty")
        result = parse_transcript(payload.content)
        return TranscriptParseResponse(
            text=result.text,
            detected_format=result.detected_format,
            line_count=result.line_count,
            word_count=result.word_count,
            speakers=result.speakers,
        )

    # ---- Status -----------------------------------------------------------

    @app.get("/api/status", response_model=StatusResponse)
    def status(_user: _auth.User = Depends(require_user)) -> StatusResponse:
        settings = get_settings()
        return StatusResponse(
            provider=settings.llm_provider,
            model=settings.model_for(),
            has_active_provider_key=settings.has_active_provider_key(),
            brand_name=settings.brand_name,
            cadence_days=settings.cadence_days,
        )

    # ---- Admin: file editor ----------------------------------------------

    @app.get("/api/admin/files", response_model=list[AdminFileListItem])
    def admin_list_files(
        _user: _auth.User = Depends(require_admin),
    ) -> list[AdminFileListItem]:
        items: list[AdminFileListItem] = []
        for rel, (category, label) in _FIXED_EDITABLE_FILES.items():
            abs_path = _paths.PROJECT_ROOT / rel
            stat = abs_path.stat() if abs_path.exists() else None
            items.append(
                AdminFileListItem(
                    path=rel,
                    category=category,
                    label=label,
                    size=stat.st_size if stat else 0,
                    modified_at=(
                        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        if stat
                        else ""
                    ),
                    deletable=False,
                )
            )
        # Corpus files (dynamic)
        corpus_dir = _paths.CORPUS_DIR
        if corpus_dir.exists():
            for writer_dir in sorted(corpus_dir.iterdir()):
                if not writer_dir.is_dir() or writer_dir.name.startswith("."):
                    continue
                for post in sorted(writer_dir.glob("*.md")):
                    rel = f"corpus/{writer_dir.name}/{post.name}"
                    stat = post.stat()
                    items.append(
                        AdminFileListItem(
                            path=rel,
                            category="corpus",
                            label=f"{writer_dir.name} · {post.stem}",
                            size=stat.st_size,
                            modified_at=datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            deletable=True,
                        )
                    )
        return items

    @app.get("/api/admin/files/{file_path:path}")
    def admin_read_file(
        file_path: str,
        _user: _auth.User = Depends(require_admin),
    ) -> dict[str, Any]:
        abs_path, category, deletable = _resolve_editable_path(file_path)
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail=f"file not found: {file_path}")
        stat = abs_path.stat()
        return {
            "path": file_path,
            "category": category,
            "deletable": deletable,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "content": abs_path.read_text(encoding="utf-8"),
        }

    @app.put("/api/admin/files/{file_path:path}")
    def admin_write_file(
        file_path: str,
        payload: AdminFileBody,
        _user: _auth.User = Depends(require_admin),
    ) -> dict[str, Any]:
        if payload.path.strip() and payload.path.strip().lstrip("/") != file_path:
            raise HTTPException(
                status_code=400,
                detail="payload.path must match URL path",
            )
        abs_path, category, deletable = _resolve_editable_path(file_path)

        # config.json must remain valid JSON
        if file_path == "data/config.json":
            try:
                import json as _json

                parsed = _json.loads(payload.content)
                if not isinstance(parsed, dict):
                    raise ValueError("config.json must be a JSON object")
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temp file rename.
        import os as _os

        tmp = abs_path.with_suffix(abs_path.suffix + ".tmp")
        tmp.write_text(payload.content, encoding="utf-8")
        _os.replace(tmp, abs_path)
        stat = abs_path.stat()
        return {
            "path": file_path,
            "category": category,
            "deletable": deletable,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    @app.delete("/api/admin/files/{file_path:path}")
    def admin_delete_file(
        file_path: str,
        _user: _auth.User = Depends(require_admin),
    ) -> dict[str, Any]:
        abs_path, _category, deletable = _resolve_editable_path(file_path)
        if not deletable:
            raise HTTPException(status_code=400, detail="this file is not deletable")
        if abs_path.exists():
            abs_path.unlink()
        return {"path": file_path, "deleted": True}

    # ---- Translate --------------------------------------------------------

    @app.post(
        "/api/translate",
        response_model=TranslateResponse,
        responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    )
    def translate(
        payload: TranslateRequest,
        _user: _auth.User = Depends(require_user),
    ) -> TranslateResponse:
        if not payload.text.strip():
            raise HTTPException(status_code=400, detail="text must not be empty")
        provider = _ensure_provider(factory)
        translator = Translator(provider, max_tokens=get_settings().llm_max_tokens_voice)
        try:
            result = translator.translate(payload.text, target_language=payload.target_lang)
        except RateLimitError as exc:
            raise _rate_limit_http(exc) from exc
        except TranslationParseError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return TranslateResponse(
            original_text=result.original_text,
            translated_text=result.translated_text,
            source_language=result.source_language,
            target_language=result.target_language,
            needed_translation=result.needed_translation,
        )

    # ---- Brief ------------------------------------------------------------

    @app.post(
        "/api/brief",
        response_model=BriefResponse,
        responses={
            400: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    def compose_brief(
        payload: BriefRequest,
        _user: _auth.User = Depends(require_user),
    ) -> BriefResponse:
        if not payload.idea.strip():
            raise HTTPException(status_code=400, detail="idea must not be empty")
        provider = _ensure_provider(factory)
        composer = IdeaToBrief(
            provider=provider,
            max_tokens=get_settings().llm_max_tokens_voice,
        )
        try:
            draft = composer.build(payload.idea, target_language=payload.target_lang)
        except RateLimitError as exc:
            raise _rate_limit_http(exc) from exc
        except BriefBuildError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if not draft.working_title.strip():
            raise HTTPException(status_code=502, detail="LLM returned empty working title")

        post_id = _make_post_id(draft.working_title)
        repo = PostRepository()
        if repo.exists(post_id):
            raise HTTPException(
                status_code=409,
                detail=f"post_id already exists: {post_id}",
            )

        brief_md = _render_brief(post_id, draft, repo)
        brief_path = _paths.BRIEFS_DIR / f"{post_id}.md"
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(brief_md, encoding="utf-8")

        repo.append(
            PostRecord(
                post_id=post_id,
                working_title=draft.working_title,
                status=PostStatus.BRIEF,
                hook_pattern_used=draft.target_hook,
                structural_framework_used=draft.target_framework,
            )
        )

        translation = draft.translation
        return BriefResponse(
            post_id=post_id,
            brief_path=str(brief_path),
            working_title=draft.working_title,
            one_big_idea=draft.one_big_idea,
            why_now=draft.why_now,
            target_hook=draft.target_hook,
            target_framework=draft.target_framework,
            reader_transformation=draft.reader_transformation,
            forbidden_moves=draft.forbidden_moves,
            source_language=translation.source_language if translation else "unknown",
            original_text=translation.original_text if translation else payload.idea,
            translated_text=translation.translated_text if translation else payload.idea,
            needed_translation=translation.needed_translation if translation else False,
            rendered_markdown=brief_md,
        )

    # ---- Draft ------------------------------------------------------------

    @app.post(
        "/api/draft/{post_id}",
        response_model=DraftResponse,
        responses={
            404: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    def generate_draft(
        post_id: str,
        _user: _auth.User = Depends(require_user),
    ) -> DraftResponse:
        repo = PostRepository()
        try:
            post = repo.get(post_id)
        except PostNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"post_id not found: {post_id}") from exc

        provider = _ensure_provider(factory)
        settings = get_settings()
        rotation = repo.recent_published(3)
        system_prompt = render_master_prompt(
            brand_name=settings.brand_name, rotation=rotation
        )
        user_prompt = _build_draft_user_prompt(post_id)
        try:
            text = provider.generate(
                system_prompt,
                user_prompt,
                max_tokens=settings.llm_max_tokens_draft,
                temperature=settings.llm_temperature,
            )
        except RateLimitError as exc:
            raise _rate_limit_http(exc) from exc
        draft_path = _paths.DRAFTS_DIR / f"{post_id}_v1.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        repo.update(post.post_id, status=PostStatus.DRAFTING)
        return DraftResponse(
            post_id=post_id,
            draft_path=str(draft_path),
            text=text,
            word_count=len(text.split()),
        )

    # ---- Detect -----------------------------------------------------------

    @app.post(
        "/api/detect/{post_id}",
        response_model=DetectResponse,
        responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    )
    def run_detector(
        post_id: str,
        _user: _auth.User = Depends(require_user),
    ) -> DetectResponse:
        repo = PostRepository()
        try:
            post = repo.get(post_id)
        except PostNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"post_id not found: {post_id}") from exc

        draft_path = _latest_draft_path(post_id) or _latest_published_path(post_id)
        if draft_path is None:
            raise HTTPException(
                status_code=404,
                detail=f"no draft or published file found for {post_id}",
            )
        draft_text = draft_path.read_text(encoding="utf-8")

        settings = get_settings()
        if settings.has_active_provider_key():
            try:
                provider = factory(settings)
                detector = LLMJudgeDetector(
                    provider=provider, max_tokens=settings.llm_max_tokens_detector
                )
                detector_name = "LLMJudgeDetector"
                result = detector.detect(draft_text)
            except RateLimitError as exc:
                raise _rate_limit_http(exc) from exc
            except (MissingAPIKeyError, DetectorParseError):
                LOG.warning("LLM detector failed; falling back to local kill list.")
                result = LocalKillListDetector().detect(draft_text)
                detector_name = "LocalKillListDetector"
        else:
            result = LocalKillListDetector().detect(draft_text)
            detector_name = "LocalKillListDetector"

        if result.passed:
            new_status = PostStatus.AI_TELLS_PASS
        elif post.status == PostStatus.AI_TELLS_PASS:
            new_status = PostStatus.DRAFTING
        else:
            new_status = post.status
        repo.update(
            post.post_id,
            ai_tells_check_passed=result.passed,
            status=new_status,
        )
        return DetectResponse(
            post_id=post_id,
            passed=result.passed,
            flags=[
                DetectFlag(pattern=f.pattern, snippet=f.snippet, line_approx=f.line_approx)
                for f in result.flags
            ],
            detector=detector_name,
        )

    # ---- Retention check (server-side, all-yes flag) ---------------------

    @app.post("/api/retention/{post_id}")
    def retention_pass(
        post_id: str,
        _user: _auth.User = Depends(require_user),
    ) -> dict[str, Any]:
        repo = PostRepository()
        try:
            post = repo.get(post_id)
        except PostNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"post_id not found: {post_id}") from exc
        questions = (
            "Open loop set in para 2, resolved in para 6+?",
            "Pattern interrupts every 200-300 words?",
            "Buried 'wait, what?' sentence two-thirds in?",
            "Closing line screenshot-able after deliberate revision?",
        )
        answers = [RetentionAnswer(question=q, passed=True) for q in questions]
        repo.update(
            post.post_id,
            human_edit_completed=True,
            retention_check_answers=answers,
            status=PostStatus.RETENTION_CHECK,
        )
        return {"post_id": post.post_id, "human_edit_completed": True}

    # ---- Publish ----------------------------------------------------------

    @app.post(
        "/api/publish/{post_id}",
        response_model=PublishResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    def publish(
        post_id: str,
        payload: PublishRequest,
        _user: _auth.User = Depends(require_user),
    ) -> PublishResponse:
        repo = PostRepository()
        try:
            post = repo.get(post_id)
        except PostNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"post_id not found: {post_id}") from exc
        if not post.ai_tells_check_passed:
            raise HTTPException(
                status_code=400, detail="ai_tells_check_passed=false — cannot publish"
            )
        if not post.human_edit_completed:
            raise HTTPException(
                status_code=400, detail="human_edit_completed=false — cannot publish"
            )

        url = payload.url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="url must start with http(s)://")
        if "example.com" in url or "example.substack.com" in url:
            raise HTTPException(
                status_code=400, detail="refusing placeholder URL containing example.com"
            )

        draft = _latest_draft_path(post_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="no draft to publish")
        dest = _paths.PUBLISHED_DIR / draft.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        draft.replace(dest)

        published_at = now_iso()
        repo.update(
            post.post_id,
            status=PostStatus.PUBLISHED,
            substack_url=url,
            published_at=published_at,
        )
        return PublishResponse(
            post_id=post_id, substack_url=url, published_at=published_at
        )

    # ---- Posts list -------------------------------------------------------

    @app.get("/api/posts", response_model=PostsListResponse)
    def list_posts(
        _user: _auth.User = Depends(require_user),
    ) -> PostsListResponse:
        return PostsListResponse(posts=PostRepository().list())

    @app.get(
        "/api/posts/{post_id}",
        response_model=PostDetail,
        responses={404: {"model": ErrorResponse}},
    )
    def get_post(
        post_id: str,
        _user: _auth.User = Depends(require_user),
    ) -> PostDetail:
        repo = PostRepository()
        try:
            post = repo.get(post_id)
        except PostNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"post_id not found: {post_id}") from exc
        return PostDetail(
            post=post,
            brief_text=_read_optional(_paths.BRIEFS_DIR / f"{post_id}.md"),
            draft_text=_read_optional(_latest_draft_path(post_id) or Path("/dev/null")),
            published_text=_read_optional(_latest_published_path(post_id) or Path("/dev/null")),
        )

    # ---- SPA fallback (REGISTERED LAST) ------------------------------------
    # Any non-/api, non-/static, non-/assets path falls through to index.html
    # so React Router can handle deep-links like /library/{post_id}.

    if spa_index.exists():
        @app.get("/{full_path:path}", response_class=HTMLResponse)
        def spa_fallback(full_path: str) -> HTMLResponse:
            if (
                full_path.startswith("api")
                or full_path.startswith("static")
                or full_path.startswith("assets")
            ):
                raise HTTPException(status_code=404)
            return HTMLResponse(content=spa_index.read_text(encoding="utf-8"))

    return app


# --- Internal helpers -----------------------------------------------------


def _build_draft_user_prompt(post_id: str) -> str:
    brief = (_paths.BRIEFS_DIR / f"{post_id}.md").read_text(encoding="utf-8")
    hooks = _paths.HOOK_LIBRARY_PATH.read_text(encoding="utf-8")
    structures = _paths.STRUCTURE_LIBRARY_PATH.read_text(encoding="utf-8")
    return (
        "Draft a post following the brief and inheriting the master prompt's "
        "constraints. Use the hook + structure libraries as a menu, not a script.\n\n"
        f"## BRIEF\n{brief}\n\n"
        f"## HOOK LIBRARY (reference)\n{hooks}\n\n"
        f"## STRUCTURE LIBRARY (reference)\n{structures}\n"
    )


def _render_brief(post_id: str, draft: BriefDraft, repo: PostRepository) -> str:
    last_three = repo.recent_published(3)
    hooks = [p.hook_pattern_used for p in last_three if p.hook_pattern_used] or ["none"]
    frameworks = [
        p.structural_framework_used for p in last_three if p.structural_framework_used
    ] or ["none"]
    rotation_block = (
        "\n\n### Rotation Snapshot (auto-filled)\n"
        f"- Last 3 hook patterns: {hooks}\n"
        f"- Last 3 frameworks: {frameworks}\n"
    )
    return f"# {post_id}\n\n{draft.render()}{rotation_block}"
