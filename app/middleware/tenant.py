from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Example: extract tenant info from header or domain
        tenant = request.headers.get("X-Tenant-ID", "default")
        request.state.tenant = tenant  # Store tenant info
        response = await call_next(request)
        return response
