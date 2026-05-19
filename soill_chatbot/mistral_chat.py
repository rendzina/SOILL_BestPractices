"""Mistral chat completion with rate-limit handling and optional fallback model."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from mistralai.client.errors import SDKError

import config as cfg
from soill_chatbot.mistral_client import Mistral

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    if '429' in message or 'rate limit' in message or 'capacity exceeded' in message:
        return True
    if isinstance(exc, SDKError):
        status = getattr(exc, 'status_code', None)
        if status == 429:
            return True
    return False


def _friendly_error(exc: BaseException, models_tried: list[str]) -> str:
    if _is_rate_limit_error(exc):
        models = '`, `'.join(models_tried)
        return (
            'The Mistral chat API is temporarily at capacity for the configured model(s) '
            f'(`{models}`). Retrieval succeeded, but the answer could not be generated.\n\n'
            'Try again in a few minutes, or set `MISTRAL_CHAT_MODEL` in `.env` to another '
            'model (e.g. `open-mistral-nemo`). You can also set `MISTRAL_CHAT_MODEL_FALLBACK` '
            'for an automatic retry.'
        )
    return f'Mistral API error: {exc}'


def _models_to_try() -> list[str]:
    models: list[str] = [cfg.MISTRAL_CHAT_MODEL]
    fallback = (cfg.MISTRAL_CHAT_MODEL_FALLBACK or '').strip()
    if fallback and fallback not in models:
        models.append(fallback)
    return models


def complete_chat(
    client: Mistral,
    messages: List[Any],
    *,
    temperature: float = 0.2,
) -> Any:
    """
    Call Mistral chat completion, retrying on rate limits with optional fallback model.
    """
    models = _models_to_try()
    last_error: Optional[BaseException] = None
    retries = max(0, cfg.MISTRAL_CHAT_RETRY_COUNT)

    for model in models:
        for attempt in range(retries + 1):
            try:
                return client.chat.complete(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )
            except SDKError as exc:
                last_error = exc
                if _is_rate_limit_error(exc) and attempt < retries:
                    delay = cfg.MISTRAL_CHAT_RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        'Rate limit for %s (attempt %d/%d), retrying in %.1fs',
                        model,
                        attempt + 1,
                        retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                if _is_rate_limit_error(exc):
                    logger.warning('Rate limit for model %s, trying next option', model)
                    break
                raise RuntimeError(_friendly_error(exc, models)) from exc
            except Exception as exc:
                raise RuntimeError(_friendly_error(exc, models)) from exc

    raise RuntimeError(_friendly_error(last_error or RuntimeError('Unknown error'), models))
