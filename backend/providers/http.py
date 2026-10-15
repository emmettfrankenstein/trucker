from __future__ import annotations

import logging
import time

import httpx

from .base import ProviderError

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None


def client() -> httpx.Client:
    """One pooled client per process so connections are reused across requests."""
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            transport=httpx.HTTPTransport(retries=2),
            headers={"User-Agent": "trucker-weather-routing/1.0"},
        )
    return _client


def get_json(url: str, params: dict, *, service: str, retries: int = 2):
    """GET with retry on 429/5xx and errors mapped to ProviderError."""
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            resp = client().get(url, params=params)
        except httpx.HTTPError as exc:
            if attempt < retries:
                time.sleep(0.5 * 2**attempt)
                continue
            raise ProviderError(f"{service} is unreachable") from exc
        logger.info("%s %s %.0fms", service, resp.status_code, (time.monotonic() - started) * 1000)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(0.5 * 2**attempt)
            continue
        if resp.status_code >= 400:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("detailedError", {}).get("message") or body.get("reason") or ""
            except ValueError:
                pass
            status = 400 if resp.status_code == 400 else 502
            raise ProviderError(f"{service} error {resp.status_code}: {detail}".strip(": "), status=status)
        return resp.json()
    raise ProviderError(f"{service} failed")  # pragma: no cover
