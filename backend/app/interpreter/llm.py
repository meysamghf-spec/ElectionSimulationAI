"""Optional OpenAI-compatible interpreter.

The model may propose a specification. It cannot execute code, write to the
database, or skip schema validation. Model output is never labeled as an
extracted fact.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.errors import ProviderError, SpecError
from app.schemas.spec import Assumption, ElectionSpecification

SYSTEM_PROMPT = """You convert an election description into one JSON object matching this shape:
title, description, candidates[{id,name}], regions[{id,name,eligible_voters,turnout_probability,
preferences,blank_rate,invalid_rate,ranking_blocs,segments}],
voting_method (plurality|two_round|ranked_choice|dhondt), seats, runoff_threshold, runoff_transfers,
iterations, seed, scenarios, assumptions[{field,source,note}], empirical_data, turnout_shock_sd, reporting.
Rules:
- Return JSON only. Do not return code, SQL, shell commands, or Markdown.
- ids are lowercase letters, digits, underscores, or hyphens, and start with a letter.
- Preference probabilities are nonnegative and sum to 1. Do not include candidates that were not requested.
- Do not invent official results or claim a value was measured. Set empirical_data to false.
- Set every assumption source to model_proposed.
- If a number is absent, use a clearly labeled placeholder instead of a realistic-looking fake measurement.
- Use plurality unless the user asks for another method. D'Hondt needs seats.
"""


class LanguageModelClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw model text."""


class OpenAICompatibleClient:
    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client(timeout=settings.llm_timeout_seconds)
        self._owns_client = http_client is None

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self._settings.llm_api_key:
            raise ProviderError("No LLM API key is configured.")
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        try:
            response = self._http.post(
                url,
                headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
                json={
                    "model": self._settings.llm_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("The language-model provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("The language-model provider could not be reached.") from exc
        if response.status_code == 429:
            raise ProviderError("The language-model provider rate-limited the request.")
        if response.status_code >= 400:
            raise ProviderError(
                f"The language-model provider returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("The language-model provider returned an unreadable response.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("The language-model provider returned an empty response.")
        return content

    def close(self) -> None:
        if self._owns_client:
            self._http.close()


def specification_from_model_text(text: str) -> ElectionSpecification:
    """Validate model text. The text is parsed as JSON and never executed."""

    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SpecError("The language model did not return valid JSON.") from exc
    if not isinstance(payload, dict):
        raise SpecError("The language model did not return a JSON object.")
    payload["empirical_data"] = False
    assumptions = payload.get("assumptions")
    normalized: list[dict[str, str]] = []
    if isinstance(assumptions, list):
        for item in assumptions:
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            note = str(item.get("note") or "Language-model proposal.")
            if source in {"extracted", "user"}:
                note = (
                    f"{note} The server relabeled this as model-proposed rather than an extracted fact."
                )
            normalized.append(
                {
                    "field": str(item.get("field") or "specification")[:120],
                    "source": "model_proposed",
                    "note": note[:2000],
                }
            )
    normalized.append(
        {
            "field": "specification",
            "source": "model_proposed",
            "note": (
                "A language model proposed this specification. Review every value before execution. "
                "It is not an official measurement."
            ),
        }
    )
    payload["assumptions"] = normalized
    try:
        specification = ElectionSpecification.model_validate(payload)
    except ValidationError as exc:
        raise SpecError("The language-model specification failed validation.") from exc
    for assumption in specification.assumptions:
        if not isinstance(assumption, Assumption):
            raise SpecError("Model assumptions were not structured records.")
    return specification
