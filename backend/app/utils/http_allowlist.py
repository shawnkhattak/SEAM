from __future__ import annotations

import httpx

# Outbound HTTP allowlist — enforced at transport layer.
# Only agents and clients in app/clients/ and app/agents/ should use this transport.
ALLOWED_HOSTS = frozenset(
    [
        "oceans-x.mpa.gov.sg",
        "data.opensanctions.org",
        "marine-api.open-meteo.com",
        "api.anthropic.com",
        # RSS.app domains
        "rss.app",
        "api.rss.app",
    ]
)


class AllowlistTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host not in ALLOWED_HOSTS and not any(host.endswith("." + h) for h in ALLOWED_HOSTS):
            raise PermissionError(f"Outbound HTTP to {host!r} is not in the allowlist")
        return await super().handle_async_request(request)


def make_allowlisted_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=AllowlistTransport(), **kwargs)
