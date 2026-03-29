"""
llm_router.py — LLM abstraction layer with Claude → Gemini → Groq fallback.
All agent LLM calls MUST go through this class — never call providers directly.
"""

import asyncio
import time
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)


class LLMRouter:
    """
    Routes LLM requests through providers in priority order:
    Claude (best quality) → Gemini (free 1500/day) → Groq (fastest, free).
    Implements exponential backoff on rate limits.
    """

    def __init__(self):
        """Initialize the router — lazy loads clients on first use."""
        self._anthropic_client = None
        self._gemini_configured = False
        self._groq_client = None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1000,
    ) -> str:
        """
        Complete a prompt using the best available LLM.
        Router: Gemini (free 1500/day) → Groq (fastest, free).

        Args:
            prompt: The user prompt / query.
            system: Optional system prompt for context framing.
            max_tokens: Maximum tokens in the response.

        Returns:
            The LLM response text.

        Raises:
            RuntimeError: If all providers fail.
        """
        # --- Try Gemini first ---
        try:
            return await self._call_gemini(prompt, system, max_tokens)
        except Exception as e:
            logger.warning("Gemini failed, trying Groq", error=str(e))

        # --- Final fallback to Groq ---
        try:
            return await self._call_groq(prompt, system, max_tokens)
        except Exception as e:
            logger.error("All LLMs failed", error=str(e))
            if "not configured" in str(e):
                return "Mock Mode (API Keys Missing): This is a placeholder AI response. Please configure your GEMINI_API_KEY or GROQ_API_KEY in the .env file to enable live ML inferences."
            raise RuntimeError(f"All LLM providers failed. Last error: {e}")

    async def stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2000,
    ):
        """
        Stream a response as an async generator of text chunks.
        Falls back to non-streaming complete() if streaming fails.
        """
        try:
            async for chunk in self._stream_claude(prompt, system, max_tokens):
                yield chunk
        except Exception as e:
            logger.warning("Claude streaming failed, falling back to complete", error=str(e))
            try:
                full_text = await self.complete(prompt, system, max_tokens)
                # Yield in chunks to simulate streaming
                words = full_text.split()
                for i in range(0, len(words), 5):
                    yield " ".join(words[i:i+5]) + " "
                    await asyncio.sleep(0.05)
            except Exception as e2:
                logger.error("Streaming fallback also failed", error=str(e2))
                yield "Unable to generate response at this time. Please try again."

    # ------------------------------------------------------------------ #
    #  Provider Implementations                                            #
    # ------------------------------------------------------------------ #

    async def _call_claude(self, prompt: str, system: str, max_tokens: int) -> str:
        """Call Anthropic Claude API with retry logic."""
        from backend.config import settings, CLAUDE_MODEL

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        import anthropic

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )

        return await self._with_retry(self._claude_request, prompt, system, max_tokens)

    async def _claude_request(self, prompt: str, system: str, max_tokens: int) -> str:
        """Execute a single Claude API request."""
        from backend.config import CLAUDE_MODEL

        messages = [{"role": "user", "content": prompt}]
        kwargs = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system

        response = await self._anthropic_client.messages.create(**kwargs)
        return response.content[0].text

    async def _stream_claude(self, prompt: str, system: str, max_tokens: int):
        """Stream response from Claude."""
        from backend.config import settings, CLAUDE_MODEL

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        import anthropic

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )

        messages = [{"role": "user", "content": prompt}]
        kwargs = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system

        async with self._anthropic_client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def _call_gemini(self, prompt: str, system: str, max_tokens: int) -> str:
        """Call Google Gemini API."""
        from backend.config import settings, GEMINI_MODEL

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        import google.generativeai as genai

        if not self._gemini_configured:
            genai.configure(api_key=settings.gemini_api_key)
            self._gemini_configured = True

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system if system else None,
        )

        full_prompt = prompt
        response = await asyncio.to_thread(
            model.generate_content,
            full_prompt,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text

    async def _call_groq(self, prompt: str, system: str, max_tokens: int) -> str:
        """Call Groq API (llama-3.1-8b-instant)."""
        from backend.config import settings, GROQ_MODEL

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")

        from groq import AsyncGroq

        if self._groq_client is None:
            self._groq_client = AsyncGroq(api_key=settings.groq_api_key)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------ #
    #  Retry Logic                                                         #
    # ------------------------------------------------------------------ #

    async def _with_retry(self, func, *args, max_retries: int = 3) -> str:
        """
        Execute an async function with exponential backoff retry.
        Retries on rate limit errors (429) and transient failures.
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return await func(*args)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Rate limit — back off and retry
                if "rate" in error_str or "429" in error_str or "overloaded" in error_str:
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    logger.warning(
                        "Rate limited, backing off",
                        attempt=attempt + 1,
                        wait_seconds=wait_time,
                        error=str(e),
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Non-retryable error — break immediately
                    raise

        raise last_error


# Singleton instance — import this in agents
llm_router = LLMRouter()
