"""Ask a model for text, never for target writes.

Read provider keys only from the environment.
Keep LiteLLM lookups and telemetry off for local and offline use.
"""

from dataclasses import dataclass, field
import os

from migration_agent.settings import Settings, load_settings

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_TELEMETRY"] = "False"


class ModelError(RuntimeError):
    """Explain why a model request failed."""


class ModelTimeout(ModelError):
    """Report that the model took too long."""


@dataclass(frozen=True)
class Reply:
    """Keep reply text and token counts for the caller."""

    text: str
    usage: dict = field(default_factory=dict)


def chat(messages, response_format=None, *, settings: Settings | None = None, timeout: float = 60) -> Reply:
    """Send one chat request with the chosen settings and time limit."""
    settings = settings or load_settings()
    provider = settings.model.split("/", 1)[0]
    key_name = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "nvidia_nim": "NVIDIA_NIM_API_KEY"}.get(provider)
    if provider != "openai" and key_name is None:
        raise ModelError("model: use openai/local, gemini, groq or nvidia_nim")
    api_key = os.environ.get(key_name) if key_name else "local"
    if not api_key:
        raise ModelError(f"missing environment variable {key_name}")
    # Load the large client only when a real request needs it.
    import litellm

    litellm.telemetry = False
    litellm.suppress_debug_info = True
    kwargs = dict(model=settings.model, api_base=settings.api_base if provider == "openai" else None,
                  api_key=api_key, timeout=timeout, max_retries=0, messages=messages)
    if response_format is not None:
        kwargs["response_format"] = response_format
    try:
        response = litellm.completion(**kwargs)
    except (litellm.Timeout, TimeoutError):
        raise ModelTimeout(f"model did not answer within {timeout} seconds") from None
    except Exception:
        # Provider error text can contain credentials or request contents.
        raise ModelError("model request failed; check provider settings and availability") from None
    if not response.choices:
        raise ModelError("model returned no choices")
    usage = response.usage
    return Reply(response.choices[0].message.content or "", {
        key: getattr(usage, key, 0) or 0 for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    })
