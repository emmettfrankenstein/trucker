from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

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
            follow_redirects=True,  # NWS redirects /points to its canonical coordinates
            # MET Norway's terms ask for an identifying User-Agent with a contact.
            headers={"User-Agent": "trucker-weather-routing/1.0 github.com/emmettfrankenstein/trucker"},
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
        if resp.status_code == 429:
            # Quotas reset per minute or longer; an immediate retry only wastes a call.
            reason = _reason(resp)
            logger.warning("%s rate-limited: %s", service, reason or "no reason given")
            raise ProviderError(
                f"{service} is rate-limiting requests right now. Please try again in about a minute.",
                status=503,
                retry_after=_retry_after(resp, reason),
                upstream_status=429,
            )
        if resp.status_code in (500, 502, 503, 504) and attempt < retries:
            time.sleep(0.5 * 2**attempt)
            continue
        if resp.status_code >= 400:
            detail = _reason(resp)
            status = 400 if resp.status_code == 400 else 502
            raise ProviderError(
                f"{service} error {resp.status_code}: {detail}".strip(": "),
                status=status,
                upstream_status=resp.status_code,
            )
        return resp.json()
    raise ProviderError(f"{service} failed")  # pragma: no cover


def _reason(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    return body.get("detailedError", {}).get("message") or body.get("reason") or ""


def _retry_after(resp: httpx.Response, reason: str) -> int:
    """Seconds until the quota resets: the Retry-After header, else Open-Meteo's wording."""
    header = resp.headers.get("Retry-After", "")
    if header.isdigit():
        return int(header)
    now = datetime.now(UTC)
    if "Daily" in reason:
        return int((now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - now).total_seconds())
    if "Hourly" in reason:
        return int((now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1) - now).total_seconds())
    return 60
