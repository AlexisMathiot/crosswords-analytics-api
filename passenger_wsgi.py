import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.main import app


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ["REQUEST_METHOD"]
    query_string = environ.get("QUERY_STRING", "").encode()

    headers = []
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            header_name = key[5:].lower().replace("_", "-").encode()
            headers.append((header_name, value.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": environ.get("wsgi.url_scheme", "http"),
        "path": path,
        "query_string": query_string,
        "headers": headers,
        "server": (
            environ.get("SERVER_NAME", "localhost"),
            int(environ.get("SERVER_PORT", 80)),
        ),
    }

    body_parts = []
    status_code = 500
    response_headers = []

    async def receive():
        body = (
            environ.get("wsgi.input", b"").read()
            if hasattr(environ.get("wsgi.input"), "read")
            else b""
        )
        return {"type": "http.request", "body": body}

    async def send(message):
        nonlocal status_code, response_headers
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = [
                (k.decode(), v.decode()) for k, v in message.get("headers", [])
            ]
        elif message["type"] == "http.response.body":
            body_parts.append(message.get("body", b""))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(app(scope, receive, send))
    finally:
        loop.close()

    status_text = {
        200: "OK",
        201: "Created",
        404: "Not Found",
        500: "Internal Server Error",
    }.get(status_code, "Unknown")
    start_response(f"{status_code} {status_text}", response_headers)
    return body_parts
