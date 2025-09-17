import os
import time
from typing import Optional
from openai import (
    OpenAI,
    APIError, RateLimitError, APITimeoutError, APIConnectionError,
    AuthenticationError, BadRequestError, OpenAIError,
)
from .llm_router import KeyRouter, Feature
from loguru import logger

router = KeyRouter()

TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

def _client_for(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, timeout=TIMEOUT)

def _mask(key: str | None) -> str:
    if not key:
        return "<empty>"
    return key[:7] + "…" + key[-4:]

def chat(feature: Feature, messages: list[dict], temperature: float = 0.3, **kwargs) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(RETRIES + 1):
        api_key, model = router.next_creds(feature)
        try:
            client = _client_for(api_key)
            logger.info("[llm] call feature={} model={} attempt={} key={}",
                        feature.value, model, attempt, _mask(api_key))

            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                **kwargs,
            )
            return resp.choices[0].message.content

        except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as e:
            last_err = e
            logger.warning("[llm] retryable {} feature={} model={} attempt={}",
                           type(e).__name__, feature.value, model, attempt)
            time.sleep(0.8)
            continue

        except (AuthenticationError, BadRequestError, OpenAIError) as e:
            last_err = e
            logger.error("[llm] non-retryable {} feature={} model={} attempt={}",
                         type(e).__name__, feature.value, model, attempt)
            break

    raise RuntimeError(f"LLM request failed after retries: {last_err}")

def _mask(key: str | None) -> str:
    if not key:
        return "<empty>"
    return key[:7] + "…" + key[-4:]