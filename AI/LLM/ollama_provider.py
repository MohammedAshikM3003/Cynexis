"""
CYNEXIS — Ollama Local LLM Provider
Streams tokens from a locally running Ollama server.

Architecture:
    VoicePipeline → OllamaLLMProvider.stream() → async token iterator
    Tokens → _sentence_chunker() → Kokoro TTS → speaker

Safety: This provider ONLY generates conversational text.
        Hardware control is impossible from here — that path goes through
        IntentEngine → SafetyValidator → ActionRegistry.
"""

import asyncio
import time
import re
from typing import Optional, AsyncIterator

import ollama as ollama_sdk
from core.logger import get_logger
from core.config import settings
from AI.LLM.provider import LLMProvider

log = get_logger("ollama_llm")

# ── Qwen3 thinking-block stripper ─────────────────────────────────────────────
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_blocks(text: str) -> str:
    """Remove Qwen3 <think>...</think> reasoning blocks from output."""
    return _THINK_RE.sub("", text).strip()


class OllamaLLMProvider(LLMProvider):
    """
    Real local LLM provider backed by an Ollama server.

    Uses the official `ollama` Python SDK (0.6+) which wraps httpx under the
    hood.  All methods are async-safe and cancellation-aware.

    Telemetry is updated after each inference and exposed via `llm_telemetry`.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ):
        self._model: str = model or getattr(settings, "ollama_model", "llama3:8b")
        self._base_url: str = base_url or getattr(
            settings, "ollama_base_url", "http://localhost:11434"
        )
        self._temperature: float = temperature if temperature is not None else getattr(
            settings, "ollama_temperature", 0.7
        )
        self._max_tokens: int = max_tokens or getattr(
            settings, "ollama_max_tokens", 100
        )
        if self._max_tokens < 100:
            self._max_tokens = 100
        self._timeout_s: float = timeout_s or getattr(
            settings, "ollama_timeout_s", 30.0
        )

        self._loaded: bool = False
        self._client: ollama_sdk.AsyncClient = ollama_sdk.AsyncClient(
            host=self._base_url
        )

        # Live telemetry (updated after each inference)
        self._telemetry: dict = {
            "provider": "ollama",
            "model": self._model,
            "status": "OFFLINE",
            "ttft_s": None,
            "first_sentence_s": None,
            "generation_s": None,
            "tokens_generated": 0,
            "tokens_per_sec": None,
            "ttfa_s": None,
            "history_messages": 0,
            "prompt_chars": 0,
        }
        log.info(
            f"OllamaLLMProvider initialized: model={self._model} url={self._base_url}"
        )

    # ── LLMProvider interface ─────────────────────────────────────────────────

    async def load(self) -> bool:
        """Verify the Ollama server is reachable and the model exists."""
        try:
            models_response = await self._client.list()
            # ollama SDK returns an object with a 'models' attribute
            model_names = [m.model for m in models_response.models]
            if not any(self._model in name for name in model_names):
                log.warning(
                    f"Model '{self._model}' not found on Ollama server. "
                    f"Available: {model_names}"
                )
                # Still mark loaded — Ollama may auto-pull or it may be a partial name match
            self._loaded = True
            self._telemetry["status"] = "ONLINE"
            log.info(
                f"OllamaLLMProvider loaded. Server has {len(model_names)} models."
            )
            return True
        except Exception as e:
            log.error(f"OllamaLLMProvider failed to connect to Ollama server: {e}")
            self._telemetry["status"] = "OFFLINE"
            self._loaded = False
            return False

    async def unload(self) -> None:
        """Close the HTTP client gracefully."""
        try:
            await self._client._client.aclose()  # type: ignore[attr-defined]
        except Exception:
            pass
        self._loaded = False
        self._telemetry["status"] = "OFFLINE"
        log.info("OllamaLLMProvider unloaded")

    def is_loaded(self) -> bool:
        return self._loaded

    async def generate(self, prompt: str, context: str = "") -> str:
        """Accumulate the full streaming response and return as a single string."""
        full = ""
        try:
            async for token in self.stream(prompt, context):
                full += token
        except Exception as e:
            log.error(f"OllamaLLMProvider.generate failed: {e}")
            return "I'm sorry, I couldn't process that."
        return full.strip()

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        """
        Stream tokens from Ollama.

        Yields individual string tokens as they arrive.  Updates `_telemetry`
        with TTFT and generation stats after the stream completes.
        """
        messages = self._build_messages(prompt, context)
        t_start = time.monotonic()
        ttft: Optional[float] = None
        token_count = 0
        sentence_buf = ""
        first_sentence_time: Optional[float] = None

        try:
            stream = await self._client.chat(
                model=self._model,
                messages=messages,
                stream=True,
                keep_alive=-1,  # Keep model loaded indefinitely (no 5-min eviction)
                options={
                    "temperature": self._temperature,
                    "num_predict": self._max_tokens,
                    "num_thread": getattr(settings, "ollama_num_thread", 8) or 8,
                    "num_ctx": getattr(settings, "ollama_num_ctx", 512) or 512,
                },
            )
            async for chunk in stream:
                token: str = chunk.message.content or ""
                if not token:
                    continue

                # Strip Qwen3 think blocks token-by-token (block may span chunks)
                # We collect and strip at full-response level, but yield cleaned tokens
                token = _strip_think_blocks(token) if "<think>" in token else token

                if ttft is None and token.strip():
                    ttft = time.monotonic() - t_start

                token_count += 1
                sentence_buf += token

                # Track first sentence time
                if first_sentence_time is None and any(
                    c in sentence_buf for c in ".!?"
                ):
                    first_sentence_time = time.monotonic() - t_start

                yield token

        except asyncio.CancelledError:
            log.info("OllamaLLMProvider stream cancelled")
            raise
        except Exception as e:
            log.error(f"OllamaLLMProvider stream error: {e}")
            self._telemetry["status"] = "OFFLINE"
            yield "I'm sorry, I encountered a connection issue."
            return
        finally:
            elapsed = time.monotonic() - t_start
            self._telemetry.update(
                {
                    "status": "ONLINE",
                    "ttft_s": round(ttft, 3) if ttft is not None else None,
                    "first_sentence_s": (
                        round(first_sentence_time, 3) if first_sentence_time is not None else None
                    ),
                    "generation_s": round(elapsed, 3),
                    "tokens_generated": token_count,
                    "tokens_per_sec": (
                        round(token_count / elapsed, 1) if elapsed > 1e-6 else None
                    ),
                }
            )

            # Print Local Telemetry block
            hist_msgs = self._telemetry.get("history_messages", 0)
            prompt_ch = self._telemetry.get("prompt_chars", 0)
            ttft_s = round(ttft, 3) if ttft is not None else 0.0
            gen_s = round(elapsed, 3)
            print(f"\n============================================================\n"
                  f"[LOCAL TELEMETRY]\n"
                  f"ollama=true\n"
                  f"generation_calls=1\n"
                  f"history_messages={hist_msgs}\n"
                  f"prompt_chars={prompt_ch}\n"
                  f"ttft={ttft_s} s\n"
                  f"generation_time={gen_s} s\n"
                  f"============================================================\n")

            log.info(
                f"Ollama stream complete: {token_count} tokens in {elapsed:.2f}s "
                f"(TTFT={ttft:.3f}s)" if ttft else
                f"Ollama stream complete: {token_count} tokens in {elapsed:.2f}s"
            )

    # ── Extra methods (not in abstract base but used by API routes) ───────────

    async def health_check(self) -> dict:
        """Return server/model health status with latency measurement."""
        t0 = time.monotonic()
        try:
            models = await self._client.list()
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            names = [m.model for m in models.models]
            return {
                "ok": True,
                "model": self._model,
                "available_models": names,
                "latency_ms": latency_ms,
                "status": "ONLINE",
            }
        except Exception as e:
            return {
                "ok": False,
                "model": self._model,
                "error": str(e),
                "status": "OFFLINE",
            }

    async def close(self) -> None:
        """Alias for unload (for explicit resource cleanup)."""
        await self.unload()

    @property
    def llm_telemetry(self) -> dict:
        """Current telemetry snapshot (updated after each inference)."""
        return dict(self._telemetry)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_messages(self, prompt: str, context: str = "") -> list[dict]:
        """
        Build the Ollama chat message list.

        context is the pre-formatted string produced by pipeline.py:
            "System: <system_prompt>\n<augmented_context>\nuser: <msg>\nassistant: <msg>\n..."
        We parse it into proper role/content dicts, preserving system context and augmented references.
        """
        from AI.personality import get_system_prompt

        messages: list[dict] = []
        system_parts = [get_system_prompt()]
        conversation_history: list[dict] = []

        # Parse conversation history and any augmented context
        if context:
            lines = context.strip().splitlines()
            non_role_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("System:"):
                    continue
                if stripped.startswith("user:"):
                    conversation_history.append(
                        {"role": "user", "content": stripped[len("user:"):].strip()}
                    )
                elif stripped.startswith("assistant:"):
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": stripped[len("assistant:"):].strip(),
                        }
                    )
                else:
                    non_role_lines.append(line)

            if non_role_lines:
                extra_ctx = "\n".join(non_role_lines).strip()
                if extra_ctx:
                    system_parts.append(extra_ctx)

        # Prepend complete system prompt (including any augmented context)
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.extend(conversation_history)

        # Append the current user turn
        messages.append({"role": "user", "content": prompt})

        # Calculate and log telemetry stats
        history_messages = len(conversation_history)
        history_characters = sum(len(m["content"]) for m in conversation_history)
        system_prompt_characters = len(messages[0]["content"])
        user_prompt_characters = len(prompt)
        total_prompt_characters = sum(len(m["content"]) for m in messages)

        self._telemetry["history_messages"] = history_messages
        self._telemetry["prompt_chars"] = total_prompt_characters

        log.info(
            f"\n============================================================\n"
            f"[LOCAL TELEMETRY PROMPT SNAPSHOT]\n\n"
            f"History Messages: {history_messages}\n"
            f"History Characters: {history_characters}\n"
            f"System Prompt Characters: {system_prompt_characters}\n"
            f"User Prompt Characters: {user_prompt_characters}\n"
            f"Total Prompt Characters: {total_prompt_characters}\n"
            f"============================================================\n"
        )

        return messages
