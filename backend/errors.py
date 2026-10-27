from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def error_response(code, message, field=None, retryable=False):
    """Формирует единый JSON-ответ об ошибке для публичного Backend API."""
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "retryable": retryable,
        }
    }


def register_error_handlers(app: FastAPI):
    """Регистрирует обработчики ошибок в приложении FastAPI."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        """Преобразует ошибки валидации Pydantic в стабильный контракт Backend API."""
        errors = exc.errors()
        first = errors[0] if errors else {}

        location = [
            str(part)
            for part in first.get("loc", [])
            if part not in ("body", "query", "path")
        ]
        field = ".".join(location) or None

        if field == "generation.variants_count":
            code = "INVALID_VARIANTS_COUNT"
            message = "Количество вариантов должно быть от 1 до 3"
        elif field == "region_id":
            code = "UNSUPPORTED_REGION"
            message = "Указанный регион не поддерживается"
        else:
            code = "VALIDATION_ERROR"
            message = (
                f"Проверьте значение поля: {field}"
                if field else "Некорректные параметры запроса"
            )

        return JSONResponse(
            status_code=422,
            content=error_response(code, message, field),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request, exc):
        """Преобразует HTTPException в единый ответ, сохраняя признак retryable."""
        detail = exc.detail

        retryable = False
        if isinstance(detail, dict) and "code" in detail:
            code = detail["code"]
            message = detail.get("message", "Ошибка запроса")
            field = detail.get("field")
            retryable = bool(detail.get("retryable", False))
        else:
            code = (
                "RESOURCE_NOT_FOUND"
                if exc.status_code == 404
                else "VALIDATION_ERROR"
                if exc.status_code == 422
                else "HTTP_ERROR"
            )
            message = str(detail)
            field = None

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code, message, field, retryable),
            headers=exc.headers,
        )
