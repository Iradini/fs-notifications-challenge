from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from fs_notifications_challenge.application.check_health import CheckHealth
from fs_notifications_challenge.interface.dependencies import get_check_health
from fs_notifications_challenge.interface.schemas import HealthResponse


router = APIRouter()


# Public on purpose (monitors and load balancers don't log in). It answers with the
# 503 itself instead of raising: outside /api an exception would be rendered as an
# HTML error page by error_handlers.py.
@router.head("/health", include_in_schema=False)
@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "A dependency is down."}},
)
async def health_check(
    response: Response,
    use_case: Annotated[CheckHealth, Depends(get_check_health)],
) -> HealthResponse:
    report = await use_case.execute()
    response.headers["Cache-Control"] = "no-store"
    if not report.healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse.from_report(report)