"""
Edge shim for the Yash Dental Clinic Next.js application.

The platform ingress routes /api/* to this service (port 8001) and everything
else to the Next.js dev server (port 3000). The application itself is a single
Next.js App Router project whose API routes live under /api, so this process
does nothing but transparently forward those requests to Next.js and stream the
response back — headers, cookies, status and body unchanged.

No application logic lives here. All of it is in /app/frontend/src.
"""

import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

NEXT_ORIGIN = os.environ.get("NEXT_ORIGIN", "http://127.0.0.1:3000")

app = FastAPI(title="Yash Dental Clinic API proxy", docs_url=None, redoc_url=None)

_client: httpx.AsyncClient | None = None

# Hop-by-hop headers must not be forwarded in either direction.
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
    "host",
}


@app.on_event("startup")
async def _startup() -> None:
    global _client
    # Long timeout: Next.js dev compiles a route on first request, and the
    # reminder cron endpoint can legitimately run for tens of seconds.
    _client = httpx.AsyncClient(
        base_url=NEXT_ORIGIN,
        timeout=httpx.Timeout(120.0, connect=10.0),
        follow_redirects=False,
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _client is not None:
        await _client.aclose()


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request) -> Response:
    assert _client is not None

    url = "/api/" + path
    body = await request.body()

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    # Preserve the public origin so Next.js builds correct absolute URLs and
    # rate limiting still sees the real client IP.
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        headers["x-forwarded-host"] = forwarded_host
    headers["x-forwarded-proto"] = request.headers.get("x-forwarded-proto", "https")

    try:
        upstream = await _client.request(
            request.method,
            url,
            params=dict(request.query_params),
            content=body if body else None,
            headers=headers,
        )
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "The application server is starting up. Please retry in a moment."},
            status_code=503,
        )
    except httpx.ReadTimeout:
        return JSONResponse({"error": "The request timed out."}, status_code=504)

    out = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )

    for key, value in upstream.headers.multi_items():
        lower = key.lower()
        if lower in HOP_BY_HOP or lower == "content-type":
            continue
        if lower == "set-cookie":
            out.headers.append("set-cookie", value)
        else:
            out.headers[key] = value

    return out
