import logging
import re
from typing import Optional
import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Base exception for Ollama client interactions."""
    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when unable to connect to the local Ollama daemon."""
    pass


class OllamaTimeoutError(OllamaClientError):
    """Raised when the Ollama generation times out."""
    pass


class OllamaModelNotFoundError(OllamaClientError):
    """Raised when the requested model is not found in local Ollama."""
    pass


def clean_model_output(text: str) -> str:
    """
    Remove any internal model reasoning or thought tags (<think>...</think>)
    and normalize trailing whitespace.
    """
    if not text:
        return ""
    # Strip <think>...</think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip possible open/close XML tags for thoughts
    cleaned = re.sub(r"</?think>", "", cleaned)
    return cleaned.strip()


class OllamaClient:
    """Local Ollama client for querying local LLMs (Gemma 4)."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def check_health(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a prompt to the local Gemma model and return the final generated answer.
        Non-streaming execution.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for factual, grounded retrieval
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to local Ollama server at {self.base_url}: {e}")
            raise OllamaConnectionError(
                f"Failed to connect to local Ollama server at {self.base_url}. Ensure Ollama is running."
            )
        except httpx.TimeoutException as e:
            logger.error(f"Ollama generation timed out after {self.timeout}s: {e}")
            raise OllamaTimeoutError(
                f"Ollama model '{self.model}' generation timed out after {self.timeout} seconds."
            )
        except Exception as e:
            logger.error(f"Unexpected error communicating with Ollama: {e}")
            raise OllamaConnectionError(f"Error communicating with local Ollama: {str(e)}")

        if response.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' was not found on local Ollama server. Pull it using: ollama pull {self.model}"
            )
        elif response.status_code != 200:
            raise OllamaClientError(
                f"Ollama server returned error status {response.status_code}: {response.text}"
            )

        data = response.json()
        raw_text = data.get("response", "")
        return clean_model_output(raw_text)


# Default singleton instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get or initialize singleton OllamaClient."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
