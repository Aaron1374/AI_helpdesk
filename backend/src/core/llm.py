import os
from typing import Any

def _setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def normalize_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "\n".join(parts)
    return str(content)


def _client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_key = _setting("OPENAI_API_KEY")
    base_url = _setting("OPENAI_BASE_URL")
    organization = _setting("OPENAI_ORG_ID")

    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if organization:
        kwargs["organization"] = organization
    return kwargs


def get_chat_model(temperature: float = None, seed: int = None):
    provider = _setting("LLM_PROVIDER", "openai").lower()
    model = _setting("LLM_MODEL", "gpt-4o-mini")
    if temperature is None:
        temperature = float(_setting("LLM_TEMPERATURE", "0"))
    if seed is None:
        seed_env = _setting("LLM_SEED", "42")
        seed = int(seed_env) if seed_env.isdigit() else None

    if provider in {"google", "gemini"}:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            return None
        if not _setting("GOOGLE_API_KEY"):
            return None
        kwargs = {
            "model": model,
            "temperature": temperature,
            "google_api_key": _setting("GOOGLE_API_KEY"),
        }
        return ChatGoogleGenerativeAI(**kwargs)

    if provider in {"xai", "grok"}:
        # xAI exposes an OpenAI-compatible API.
        if not _setting("XAI_API_KEY"):
            return None
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            return None
        kwargs = {
            "model": model,
            "temperature": temperature,
            "api_key": _setting("XAI_API_KEY"),
            "base_url": _setting("XAI_BASE_URL", "https://api.x.ai/v1"),
        }
        if seed is not None:
            kwargs["seed"] = seed
        return ChatOpenAI(**kwargs)

    if provider in {"openai", "openai_compatible", "ollama", "custom"}:
        if not _setting("OPENAI_API_KEY"):
            return None
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            return None
        kwargs = {
            "model": model,
            "temperature": temperature,
            **_client_kwargs(),
        }
        if seed is not None:
            kwargs["seed"] = seed
        return ChatOpenAI(**kwargs)


    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")



def get_embedding_model():
    provider = _setting("EMBEDDING_PROVIDER", _setting("LLM_PROVIDER", "openai")).lower()
    default_model = "gemini-embedding-2" if provider in {"google", "gemini"} else "text-embedding-3-small"
    model = _setting("EMBEDDING_MODEL", default_model)

    if provider in {"google", "gemini"}:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except ImportError:
            return None
        if not _setting("GOOGLE_API_KEY"):
            return None
        return GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=_setting("GOOGLE_API_KEY"),
        )

    if provider in {"openai", "openai_compatible", "ollama", "custom", "xai", "grok"}:
        api_key = _setting("XAI_API_KEY") if provider in {"xai", "grok"} else _setting("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            return None
        kwargs = {"api_key": api_key, "model": model}
        base_url = _setting("XAI_BASE_URL") if provider in {"xai", "grok"} else _setting("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)

    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")