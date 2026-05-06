from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MOCKS_DIR = Path(__file__).resolve().parent.parent / "mocks"

HAIKU_MODEL = "claude-haiku-4-5-20251001"


async def call_haiku(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    mock_fixture: str = "haiku_summary_response",
) -> tuple[str, int, int]:
    """Call Claude Haiku. Returns (text, tokens_in, tokens_out).

    In mock mode reads from app/mocks/{mock_fixture}.json instead of the live API.
    """
    from app.config import get_settings
    settings = get_settings()

    if settings.anthropic_mock_mode:
        fixture_path = _MOCKS_DIR / f"{mock_fixture}.json"
        payload = json.loads(fixture_path.read_text())
        logger.debug("anthropic_client: mock fixture=%s", mock_fixture)
        return payload["text"], payload["tokens_in"], payload["tokens_out"]

    import anthropic  # lazy import — not available in test envs without the package

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    text = message.content[0].text
    tokens_in = message.usage.input_tokens
    tokens_out = message.usage.output_tokens
    logger.info(
        "anthropic_client: tokens_in=%d tokens_out=%d",
        tokens_in,
        tokens_out,
    )
    return text, tokens_in, tokens_out
