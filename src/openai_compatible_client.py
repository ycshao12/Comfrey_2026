# Comfrey artifact source file.
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, urlunparse
from urllib import error, request

from .config import ComfreyConfig


class OpenAICompatibleClient:
    def __init__(self, config: ComfreyConfig):
        self.config = config

    def embeddings(self, texts: List[str]) -> List[List[float]]:
        input_value: Union[str, List[str]] = texts[0] if len(texts) == 1 else texts
        response = self._post_json(
            self.config.embedding_endpoint,
            {
                "model": self.config.embedding_model_name,
                "input": input_value,
                "encoding_format": "float",
            },
        )
        data = response.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Embedding API response is missing a data array")

        embeddings = []
        for item in data:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list):
                raise RuntimeError("Embedding API response contains an item without embedding")
            embeddings.append([float(value) for value in vector])

        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Embedding API returned {len(embeddings)} vectors for {len(texts)} inputs"
            )
        return embeddings

    def chat_completion(self, system_prompt: str, user_prompt: str) -> str:
        response = self._post_json(
            self.config.chat_completion_endpoint,
            {
                "model": self.config.chat_model_name,
                "temperature": self.config.chat_temperature,
                "max_tokens": self.config.chat_max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Chat completion API response is missing choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("Chat completion API response is missing message.content")
        return content.strip()

    def _post_json(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        body = json.dumps(payload).encode("utf-8")
        api_key = self._required_api_key()

        req = request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.config.api_timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAI-compatible API request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenAI-compatible API request failed: {exc}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI-compatible API returned non-JSON response") from exc

        if not isinstance(decoded, dict):
            raise RuntimeError("OpenAI-compatible API returned a non-object response")
        return decoded

    def _build_url(self, endpoint: str) -> str:
        base_url = self._required_base_url().rstrip("/")
        endpoint_path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        if base_url.endswith("/v1") and endpoint_path.startswith("/v1/"):
            endpoint_path = endpoint_path[len("/v1"):]
        return f"{base_url}{endpoint_path}"

    def _required_base_url(self) -> str:
        value = (
            self.config.api_base_url
            or os.getenv(self.config.api_base_url_env, "")
            or self._read_first_token_file(
                getattr(self.config, "api_base_url_file", None),
                "api_url.txt",
            )
        )
        if not value:
            raise RuntimeError(
                f"OpenAI-compatible API base URL is required. Set "
                f"config.api_base_url, ${self.config.api_base_url_env}, or api_url.txt."
            )
        return self._normalize_base_url(value)

    def _required_api_key(self) -> str:
        value = (
            self.config.api_key
            or os.getenv(self.config.api_key_env, "")
            or self._read_first_token_file(self.config.api_key_file, "key.txt")
        )
        if not value:
            raise RuntimeError(
                f"OpenAI-compatible API key is required. Set "
                f"config.api_key, ${self.config.api_key_env}, or key.txt."
            )
        return value.removeprefix("Bearer ").strip()

    def _normalize_base_url(self, value: str) -> str:
        stripped = value.strip().rstrip("/")
        parsed = urlparse(stripped)
        if not (parsed.scheme and parsed.netloc):
            stripped = f"https://{stripped}"
            parsed = urlparse(stripped)

        path = parsed.path.rstrip("/")
        for suffix in ("/v1/chat/completions", "/v1/embeddings"):
            if path.endswith(suffix):
                path = path[: -len(suffix)].rstrip("/")
                break

        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    def _read_first_token_file(self, configured_path: Optional[str], default_filename: str) -> str:
        if configured_path is None:
            return ""

        candidate_paths = []
        if configured_path:
            candidate_paths.append(Path(configured_path).expanduser())

        module_root = Path(__file__).resolve().parents[1]
        candidate_paths.extend([
            module_root / default_filename,
            module_root.parent / default_filename,
            Path.cwd() / default_filename,
            Path.cwd().parent / default_filename,
        ])

        seen = set()
        for path in candidate_paths:
            resolved = path if path.is_absolute() else (module_root / path).resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if not resolved.exists():
                continue
            content = resolved.read_text(encoding="utf-8").strip()
            if content:
                return content.split()[0]
        return ""
