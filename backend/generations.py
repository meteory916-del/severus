"""Маршруты генерации сценариев и переключение между mock и LLM-сервисом."""

from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel

from backend.catalog import list_events
from backend.llm_service_client import get_llm_service_client
from backend.schemas import GenerationRequest


router = APIRouter(
    prefix="/api/v1",
    tags=["Generations"],
)

# Временное хранилище mock-заданий. В режиме llm_service состояние хранит
# внутренний LLM-сервис, а Backend только проксирует запросы по тем же ID.
jobs = {}
projects = {}


class GenerationAccepted(BaseModel):
    job_id: str
    project_id: str
    status: str
    requested_variants: int
    completed_variants: int
    status_url: str
    project_url: str


def generator_mode() -> str:
    """Возвращает активный режим генератора основного Backend.

    Допустимые значения: ``mock`` и ``llm_service``. Неизвестное значение
    считается ошибкой конфигурации, а не поводом тихо переключаться на mock.

    Возвращает:
        str.
    """
    mode = os.getenv("GENERATOR_MODE", "mock").strip().lower()
    if mode not in {"mock", "llm_service"}:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Неизвестный GENERATOR_MODE={mode}",
                "field": None,
                "retryable": False,
            },
        )
    return mode


def _validate_catalog_constraints(request: GenerationRequest):
    """Проверяет событие, возраст и формат по общему каталогу команды.

    Параметры:
        `request`.

    Возвращает:
        EventSummary: Карточку найденного события.

    Исключения:
        HTTPException: Если событие или сочетание параметров не поддерживается.
    """
    events = {event.id: event for event in list_events()}
    event = events.get(request.event_id)

    if event is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "EVENT_NOT_FOUND",
                "message": "Неизвестное мероприятие",
                "field": "event_id",
            },
        )

    if request.grade_group not in event.supported_age_groups:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CONFLICTING_CONSTRAINTS",
                "message": "Возрастная группа не поддерживается",
                "field": "grade_group",
            },
        )

    if request.format not in event.supported_formats:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CONFLICTING_CONSTRAINTS",
                "message": "Формат мероприятия не поддерживается",
                "field": "format",
            },
        )

    return event


@router.post(
    "/generations",
    response_model=GenerationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_generation(
    request: GenerationRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
):
    """Создаёт задачу генерации через mock или внутренний LLM-сервис.

    В режиме ``llm_service`` JSON передаётся без изменения состава полей.
    Основной Backend сохраняет публичный контракт и не знает внутренних этапов LLM.
    """
    event = _validate_catalog_constraints(request)

    if generator_mode() == "llm_service":
        client = get_llm_service_client()
        data = client.create_generation(
            request.model_dump(mode="json"),
            request_id=http_request.headers.get("X-Request-Id"),
            idempotency_key=http_request.headers.get("Idempotency-Key"),
        )
        return GenerationAccepted.model_validate(data)

    job_id = f"job_{uuid4().hex}"
    project_id = f"evt_{uuid4().hex}"

    jobs[job_id] = {
        "job_id": job_id,
        "project_id": project_id,
        "status": "queued",
        "requested_variants": request.generation.variants_count,
        "completed_variants": 0,
        "input": request.model_dump(mode="json"),
    }

    background_tasks.add_task(
        finish_mock_generation, job_id, request, event.title
    )

    return GenerationAccepted(
        job_id=job_id,
        project_id=project_id,
        status="queued",
        requested_variants=request.generation.variants_count,
        completed_variants=0,
        status_url=f"/api/v1/generations/{job_id}",
        project_url=f"/api/v1/projects/{project_id}",
    )


def finish_mock_generation(
    job_id: str,
    request: GenerationRequest,
    event_title: str,
) -> None:
    """Завершает локальную mock-генерацию для режима разработки Frontend.

    Параметры:
        `job_id`, `request`, `event_title`.
    """
    from backend.mock_generator import build_mock_project

    job = jobs[job_id]
    job["status"] = "running"

    try:
        result = build_mock_project(
            request, job_id, job["project_id"], event_title
        )
        projects[job["project_id"]] = result
        job["completed_variants"] = len(result["variants"])
        job["status"] = "completed"
    except Exception:
        job["status"] = "failed"
        raise


@router.get("/generations/{job_id}")
def get_generation(job_id: str, request: Request):
    """Возвращает состояние mock-задачи или проксирует состояние LLM-задачи."""
    if generator_mode() == "llm_service":
        return get_llm_service_client().get_generation(
            job_id,
            request_id=request.headers.get("X-Request-Id"),
        )

    job = jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Задание не найдено",
        )

    completed = job["completed_variants"]

    return {
        "job_id": job_id,
        "project_id": job["project_id"],
        "status": job["status"],
        "phase": job["status"],
        "requested_variants": job["requested_variants"],
        "completed_variants": completed,
        "variants": [
            {
                "variant_id": f"v{i}",
                "status": "completed" if i <= completed else job["status"],
                "revision": 1,
            }
            for i in range(1, job["requested_variants"] + 1)
        ],
        "warnings": [],
        "errors": [],
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request):
    """Возвращает mock-проект или проксирует проект LLM-сервиса."""
    if generator_mode() == "llm_service":
        return get_llm_service_client().get_project(
            project_id,
            request_id=request.headers.get("X-Request-Id"),
        )

    project = projects.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Готовый проект не найден",
        )

    return project


@router.get("/health/llm")
def health_llm():
    """Возвращает состояние активного генератора с точки зрения Backend."""
    if generator_mode() == "mock":
        return {"status": "ok", "mode": "mock", "provider": "mock"}
    return get_llm_service_client().health()
