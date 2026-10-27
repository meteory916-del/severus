"""HTTP-клиент основного Backend для внутреннего LLM-сервиса Severus."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import HTTPException


class LLMServiceClient:
    """Передаёт замороженные контракты 01/02 между Backend и LLM-сервисом без преобразования."""

    def __init__(self, base_url: str, service_token: str | None = None, timeout_seconds: float = 10.0):
        """Настраивает адрес, межсервисный токен и HTTP-таймаут.

        Параметры:
            `base_url`, `service_token`, `timeout_seconds`.
        """
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    def _headers(self, request_id: str | None = None, idempotency_key: str | None = None) -> dict[str, str]:
        """Формирует служебные заголовки запроса к LLM-сервису.

        Параметры:
            `request_id`, `idempotency_key`.

        Возвращает:
            dict[str, str].
        """
        headers: dict[str, str] = {}
        if self.service_token:
            headers["X-Service-Token"] = self.service_token
        if request_id:
            headers["X-Request-Id"] = request_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _raise_service_error(response: httpx.Response) -> None:
        """Преобразует ошибку LLM-сервиса в HTTPException основного Backend.

        Параметры:
            `response`.
        """
        if response.status_code < 400:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            error = {
                "code": "LLM_SERVICE_ERROR",
                "message": f"LLM-сервис вернул HTTP {response.status_code}",
                "field": None,
                "retryable": response.status_code >= 500,
            }
        raise HTTPException(status_code=response.status_code, detail=error)

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None,
                 request_id: str | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        """Выполняет один запрос к внутреннему сервису и возвращает JSON-объект.

        Параметры:
            `method`, `path`, `json_body`, `request_id`, `idempotency_key`.

        Возвращает:
            dict[str, Any].

        Исключения:
            HTTPException: При недоступности сервиса или ошибочном HTTP-ответе.
        """
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                json=json_body,
                headers=self._headers(request_id, idempotency_key),
                timeout=self.timeout_seconds,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MODEL_UNAVAILABLE",
                    "message": "LLM-сервис недоступен",
                    "field": None,
                    "retryable": True,
                },
            ) from exc
        self._raise_service_error(response)
        return response.json()

    def create_generation(self, payload: dict[str, Any], *, request_id: str | None = None,
                          idempotency_key: str | None = None) -> dict[str, Any]:
        """Создаёт задачу генерации в LLM-сервисе по контракту 01."""
        return self._request(
            "POST",
            "/api/v1/generations",
            json_body=payload,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def get_generation(self, job_id: str, *, request_id: str | None = None) -> dict[str, Any]:
        """Получает состояние удалённой задачи генерации."""
        return self._request("GET", f"/api/v1/generations/{job_id}", request_id=request_id)

    def get_project(self, project_id: str, *, request_id: str | None = None) -> dict[str, Any]:
        """Получает готовый проект по контракту 02."""
        return self._request("GET", f"/api/v1/projects/{project_id}", request_id=request_id)

    def health(self) -> dict[str, Any]:
        """Проверяет доступность LLM-провайдера через внутренний сервис."""
        return self._request("GET", "/api/v1/health/llm")


def get_llm_service_client() -> LLMServiceClient:
    """Создаёт клиент из переменных окружения основного Backend.

    Возвращает:
        LLMServiceClient.
    """
    return LLMServiceClient(
        base_url=os.getenv("LLM_SERVICE_URL", "http://127.0.0.1:8090"),
        service_token=os.getenv("LLM_SERVICE_TOKEN") or None,
        timeout_seconds=float(os.getenv("LLM_SERVICE_HTTP_TIMEOUT", "10")),
    )
