import time, uuid, structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger()

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())
        start = time.perf_counter()

        # attach request id
        request.state.req_id = req_id
        response: Response = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # Skip logging for monitoring endpoints to reduce noise
            skip_paths = [
                "/v1/monitoring/metrics",
                "/v1/monitoring/logs",
                "/v1/monitoring/token-usage",
                "/healthz"
            ]
            
            if request.url.path not in skip_paths:
                log.info("http.access",
                         req_id=req_id,
                         method=request.method,
                         path=request.url.path,
                         status=getattr(response, "status_code", None),
                         elapsed_ms=round(elapsed_ms, 2))