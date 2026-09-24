"""Function and method caching decorators with TTL, dynamic keys, and semantic tags."""

import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.caching.manager import cache_manager, hash_key


def _to_json_compatible(obj: Any) -> Any:
    """Convert Pydantic models or domain objects to JSON-serializable primitives."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_to_json_compatible(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_json_compatible(v) for k, v in obj.items()}
    return obj


def cached(
    ttl_seconds: int = 300,
    namespace: str = "travelops",
    key_builder: Callable[..., str] | None = None,
    tags: list[str] | Callable[..., list[str]] | None = None,
) -> Callable:
    """Decorator to cache sync and async function return values in Redis / in-memory store."""

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func) or inspect.iscoroutinefunction(func)
        sig = inspect.signature(func)
        ret_annotation = sig.return_annotation

        def _reconstitute(data: Any) -> Any:
            if data is None:
                return None
            try:
                if inspect.isclass(ret_annotation) and issubclass(ret_annotation, BaseModel):
                    if isinstance(data, dict):
                        return ret_annotation(**data)
            except Exception:
                pass
            return data

        def _resolve_key_and_tags(*args: Any, **kwargs: Any) -> tuple[str, list[str]]:
            filtered_args = args
            if args and hasattr(args[0], "__class__") and func.__name__ in dir(args[0].__class__):
                filtered_args = args[1:]

            if key_builder:
                k = key_builder(*args, **kwargs)
            else:
                arg_hash = hash_key(*filtered_args, **kwargs)
                k = f"{func.__name__}:{arg_hash}"

            resolved_tags: list[str] = []
            if callable(tags):
                resolved_tags = tags(*args, **kwargs)
            elif isinstance(tags, list):
                resolved_tags = list(tags)

            return k, resolved_tags

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                k, resolved_tags = _resolve_key_and_tags(*args, **kwargs)
                cached_val = cache_manager.get(k, namespace=namespace)
                if cached_val is not None:
                    return _reconstitute(cached_val)

                result = await func(*args, **kwargs)
                serializable = _to_json_compatible(result)
                cache_manager.set(
                    key=k,
                    value=serializable,
                    ttl_seconds=ttl_seconds,
                    namespace=namespace,
                    tags=resolved_tags,
                )
                return result

            return async_wrapper

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                k, resolved_tags = _resolve_key_and_tags(*args, **kwargs)
                cached_val = cache_manager.get(k, namespace=namespace)
                if cached_val is not None:
                    return _reconstitute(cached_val)

                result = func(*args, **kwargs)
                serializable = _to_json_compatible(result)
                cache_manager.set(
                    key=k,
                    value=serializable,
                    ttl_seconds=ttl_seconds,
                    namespace=namespace,
                    tags=resolved_tags,
                )
                return result

            return sync_wrapper

    return decorator
