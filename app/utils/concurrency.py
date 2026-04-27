
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)


def is_gemini_429_error(exception: Exception) -> bool:
    error_text = str(exception)
    return (
        "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
        or "Resource exhausted" in error_text
    )


@retry(
    retry=retry_if_exception(is_gemini_429_error),
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def generate_with_retry(fn):
    return await fn()