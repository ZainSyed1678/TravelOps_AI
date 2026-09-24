"""Async HTTP client for Amadeus Travel APIs with token caching, retries, and error normalization."""

import asyncio
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.providers.exceptions import (
    ProviderAuthenticationException,
    ProviderException,
    ProviderRateLimitException,
    ProviderTimeoutException,
    ProviderValidationException,
)


class AmadeusClient:
    """Production async HTTP client for Amadeus Self-Service APIs."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        environment: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.client_id = client_id if client_id is not None else settings.AMADEUS_CLIENT_ID
        self.client_secret = client_secret if client_secret is not None else settings.AMADEUS_CLIENT_SECRET
        self.environment = environment if environment is not None else settings.AMADEUS_ENVIRONMENT
        self.timeout = timeout
        self.max_retries = max_retries

        self.base_url = (
            "https://api.amadeus.com"
            if self.environment == "production"
            else "https://test.api.amadeus.com"
        )

        # In-memory OAuth2 token cache
        self._access_token: str | None = None
        self._token_expires_at: float | None = None
        self._token_lock = asyncio.Lock()

    async def get_access_token(self) -> str:
        """Obtain or refresh OAuth2 access token with thread-safe async locking."""
        now = time.time()
        if self._access_token and self._token_expires_at and now < (self._token_expires_at - 60):
            return self._access_token

        async with self._token_lock:
            # Double-check inside lock
            now = time.time()
            if (
                self._access_token
                and self._token_expires_at
                and now < (self._token_expires_at - 60)
            ):
                return self._access_token

            if not self.client_id or not self.client_secret:
                raise ProviderAuthenticationException(
                    provider_name="AMADEUS",
                    message="AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET must be configured",
                )

            token_url = f"{self.base_url}/v1/security/oauth2/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    start_t = time.perf_counter()
                    resp = await client.post(token_url, data=data)
                    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    logger.info(
                        f"[AMADEUS] OAuth2 token request -> {resp.status_code} ({elapsed_ms}ms)"
                    )

                    if resp.status_code == 401 or resp.status_code == 400:
                        raise ProviderAuthenticationException(
                            provider_name="AMADEUS",
                            message=f"Invalid credentials: {resp.text}",
                        )
                    resp.raise_for_status()
                    payload = resp.json()

                    self._access_token = payload["access_token"]
                    expires_in = payload.get("expires_in", 1799)
                    self._token_expires_at = time.time() + expires_in
                    return self._access_token

            except httpx.TimeoutException as exc:
                raise ProviderTimeoutException(
                    provider_name="AMADEUS",
                    message=f"Amadeus OAuth2 token endpoint timed out: {exc}",
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderAuthenticationException(
                    provider_name="AMADEUS",
                    message=f"Amadeus token error: {exc.response.text}",
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderException(
                    message=f"Amadeus network connection failure: {exc}",
                    provider_name="AMADEUS",
                    status_code=503,
                ) from exc

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute authenticated request with exponential retries and error normalization."""
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "TravelOpsAI/0.1.0",
        }
        url = f"{self.base_url}{path}"

        for attempt in range(1, self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                    )
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    logger.info(
                        f"[AMADEUS] {method} {path} -> {response.status_code} ({latency_ms}ms, attempt {attempt})"
                    )

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "2"))
                        if attempt < self.max_retries:
                            logger.warning(
                                f"[AMADEUS] Rate limit hit. Backing off for {retry_after}s..."
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        raise ProviderRateLimitException(
                            provider_name="AMADEUS", retry_after_seconds=retry_after
                        )

                    if response.status_code == 401 and attempt < self.max_retries:
                        # Invalidate token and retry once
                        self._access_token = None
                        token = await self.get_access_token()
                        headers["Authorization"] = f"Bearer {token}"
                        continue

                    if response.status_code >= 500 and attempt < self.max_retries:
                        backoff = 0.5 * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)
                        continue

                    if response.status_code == 400:
                        raise ProviderValidationException(
                            provider_name="AMADEUS",
                            message=f"Bad request: {response.text}",
                        )

                    response.raise_for_status()
                    return response.json()

            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise ProviderTimeoutException(
                    provider_name="AMADEUS",
                    message=f"Request to {path} timed out after {self.timeout}s: {exc}",
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderException(
                    message=f"Amadeus API returned error: {exc.response.text}",
                    provider_name="AMADEUS",
                    status_code=exc.response.status_code,
                    raw_error=exc.response.text,
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise ProviderException(
                    message=f"Amadeus network connection error for {path}: {exc}",
                    provider_name="AMADEUS",
                    status_code=503,
                ) from exc

        raise ProviderException(
            message=f"Max retries ({self.max_retries}) exceeded for {path}",
            provider_name="AMADEUS",
        )
