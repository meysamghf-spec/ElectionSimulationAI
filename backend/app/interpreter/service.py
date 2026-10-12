"""Choose the deterministic parser or an optional language model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import ProviderError, SpecError
from app.interpreter.deterministic import interpret_prompt
from app.interpreter.llm import (
    SYSTEM_PROMPT,
    LanguageModelClient,
    OpenAICompatibleClient,
    specification_from_model_text,
)
from app.schemas.spec import ElectionSpecification


class InterpretationResult(BaseModel):
    specification: ElectionSpecification
    interpreter_mode: Literal["deterministic", "deterministic_fallback", "llm", "json"]
    llm_configured: bool
    notices: list[str]


def interpret(
    prompt: str,
    settings: Settings,
    *,
    client: LanguageModelClient | None = None,
    allow_llm: bool = True,
) -> InterpretationResult:
    if len(prompt) > settings.max_prompt_chars:
        raise SpecError(
            f"Prompts are limited to {settings.max_prompt_chars} characters.",
            details=[{"field": "prompt", "message": "Prompt is too long."}],
        )
    if prompt.strip().startswith("{"):
        specification, notices = interpret_prompt(prompt)
        return InterpretationResult(
            specification=specification,
            interpreter_mode="json",
            llm_configured=settings.llm_configured,
            notices=notices,
        )
    if allow_llm and settings.llm_configured:
        model_client: LanguageModelClient | None = client
        owns_client = client is None
        if model_client is None:
            model_client = OpenAICompatibleClient(settings)
        try:
            raw = model_client.complete_json(SYSTEM_PROMPT, prompt)
            specification = specification_from_model_text(raw)
            return InterpretationResult(
                specification=specification,
                interpreter_mode="llm",
                llm_configured=True,
                notices=[
                    "A language model proposed this specification. Every value is model-proposed "
                    "until you edit it. The simulation engine will not treat the narrative as a result.",
                ],
            )
        except (ProviderError, SpecError, ValidationError, ValueError) as exc:
            specification, notices = interpret_prompt(prompt)
            safe = (
                exc.safe_message if isinstance(exc, ProviderError) else "the model response failed validation"
            )
            notices.insert(
                0,
                "The language-model provider was not used "
                f"({safe}). The deterministic parser produced this specification instead.",
            )
            return InterpretationResult(
                specification=specification,
                interpreter_mode="deterministic_fallback",
                llm_configured=True,
                notices=notices,
            )
        finally:
            if owns_client and isinstance(model_client, OpenAICompatibleClient):
                model_client.close()
    specification, notices = interpret_prompt(prompt)
    notices.insert(
        0,
        "No language-model provider is configured. Natural-language interpretation is in "
        "deterministic fallback mode. Review every inferred assumption in the structured editor "
        "before running.",
    )
    return InterpretationResult(
        specification=specification,
        interpreter_mode="deterministic",
        llm_configured=False,
        notices=notices,
    )
