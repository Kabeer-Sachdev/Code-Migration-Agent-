"""
OpenRouter LLM Client - async streaming HTTP client for the OpenRouter Chat API.
Supports both streaming (SSE) and non-streaming modes.
"""
import json
import logging
import asyncio
from typing import Optional, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free-tier models — append :free or use openrouter/free (no credits required)
DEFAULT_FREE_MODEL = "qwen/qwen3-coder:free"
FALLBACK_FREE_MODEL = "openrouter/free"
OPENROUTER_FREE_MODELS = frozenset({
    DEFAULT_FREE_MODEL,
    FALLBACK_FREE_MODEL,
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "google/gemma-4-31b-it:free",
})

# Ordered fallback chain when a free model returns empty or fails
FREE_MODEL_CHAIN = [
    DEFAULT_FREE_MODEL,
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-120b:free",
    FALLBACK_FREE_MODEL,
]

MIGRATION_SYSTEM_PROMPT = """You are an expert .NET to Java Spring Boot migration engineer with 10+ years of experience.

## Your Role
Convert .NET / C# source code into production-ready Java Spring Boot 3 code.

## Strict Rules
- Java version: 21
- Spring Boot version: 3.x
- Use Spring Data JPA for all database access
- Use Lombok (@Data, @Builder, @RequiredArgsConstructor, @Slf4j, etc.) where appropriate
- Use constructor injection ONLY - never field injection with @Autowired
- Generate JUnit 5 tests with Mockito for all service methods
- NEVER do literal line-by-line translation - understand intent and rewrite idiomatically
- Preserve all business logic 100% accurately
- Follow Java naming conventions (camelCase fields, PascalCase classes)
- Use BigDecimal for monetary values, not double/float
- Use Optional<T> for nullable return types
- Use Java records for immutable DTOs where appropriate
- Add proper package declarations (com.example.app)
- Add all necessary import statements
- Generate AT LEAST ONE Java file from the provided .NET code
- CRITICAL: Do NOT return empty java_files array!

## Output Format - STRICT JSON ONLY
You MUST respond with ONLY valid JSON. NO markdown fences, NO explanations, NO extra text.
Start with { and end with }

The JSON schema is:
{
  "analysis": {
    "dotnet_version": "string (e.g. '.NET 8.0')",
    "frameworks_detected": ["string array of framework names"],
    "dependencies": ["string array of dependencies"],
    "migration_considerations": ["string array of considerations"]
  },
  "java_files": [
    {
      "filename": "src/main/java/com/example/app/ClassName.java",
      "content": "Complete Java source code with package and imports"
    },
    {
      "filename": "src/main/java/com/example/app/AnotherClass.java",
      "content": "Complete Java source code"
    }
  ],
  "test_files": [
    {
      "filename": "src/test/java/com/example/app/ClassNameTest.java",
      "content": "Complete JUnit 5 test code"
    }
  ],
  "pom_xml": "Complete pom.xml file content",
  "application_yml": "Complete application.yml content",
  "notes": {
    "key_decisions": ["string"],
    "potential_risks": ["string"]
  }
}

CRITICAL REMINDERS:
- java_files MUST NOT be empty
- Every converted class must go into java_files
- Response MUST be valid JSON that can be parsed
- Start the response with { immediately"""


class OpenRouterClient:
    """
    Async client for the OpenRouter Chat Completions API.
    Supports streaming (SSE) with a token callback and a final aggregation.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_FREE_MODEL,
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://dotnet-java-migrator.local",
            "X-Title": ".NET to Java Migration Agent",
        }

    def _build_payload(
        self,
        user_message: str,
        stream: bool,
        model: Optional[str] = None,
        json_mode: bool = False,
    ) -> dict:
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": MIGRATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "stream": stream,
            "temperature": 0.2,
            "max_tokens": 16000,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _models_to_try(self, model: Optional[str] = None) -> list[str]:
        """Primary model first, then auto free router if the primary is unavailable."""
        primary = model or self.model
        if primary in (FALLBACK_FREE_MODEL,):
            return [primary]
        return [primary, FALLBACK_FREE_MODEL]

    def retry_models(self) -> list[str]:
        """Models to try when the response parses but contains no Java files."""
        chain = []
        for m in FREE_MODEL_CHAIN:
            if m not in chain:
                chain.append(m)
        if self.model not in chain:
            chain.insert(0, self.model)
        return chain

    @staticmethod
    def _should_try_fallback(exc: httpx.HTTPStatusError) -> bool:
        code = exc.response.status_code
        return code in (402, 404, 429)

    async def _raise_for_response(self, response: httpx.Response) -> None:
        """Raise a clear error that includes OpenRouter's response body."""
        if response.is_success:
            return
        try:
            body_bytes = await response.aread()
            body = json.loads(body_bytes)
            detail = body.get("error", {}).get("message") or body.get("message") or str(body)
        except Exception:
            try:
                detail = body_bytes.decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = f"HTTP {response.status_code}"
        raise httpx.HTTPStatusError(
            f"OpenRouter API error {response.status_code}: {detail}",
            request=response.request,
            response=response,
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        user_message: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        Stream the LLM response token by token.
        Calls `on_token(chunk)` for each token received.
        Returns the full aggregated response string.
        """
        last_exc: Optional[Exception] = None

        for model in self._models_to_try():
            payload = self._build_payload(user_message, stream=True, model=model)
            full_response = []

            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        async with client.stream(
                            "POST",
                            OPENROUTER_API_URL,
                            headers=self._headers(),
                            json=payload,
                        ) as response:
                            await self._raise_for_response(response)
                            async for line in response.aiter_lines():
                                if not line.startswith("data: "):
                                    continue
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = (
                                        data.get("choices", [{}])[0]
                                        .get("delta", {})
                                        .get("content", "")
                                    )
                                    if delta:
                                        full_response.append(delta)
                                        if on_token:
                                            await on_token(delta)
                                except (json.JSONDecodeError, IndexError, KeyError):
                                    continue
                    if model != self.model:
                        logger.info("OpenRouter fell back to %s", model)
                    return "".join(full_response)

                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    logger.error("OpenRouter HTTP error (model=%s, attempt %d): %s", model, attempt + 1, exc)
                    if self._should_try_fallback(exc) and model != FALLBACK_FREE_MODEL:
                        break
                    if attempt == self.max_retries:
                        raise
                    await asyncio.sleep(2 ** attempt)

                except httpx.RequestError as exc:
                    last_exc = exc
                    partial = "".join(full_response)
                    if len(partial) > 200:
                        logger.warning(
                            "OpenRouter stream interrupted (model=%s), using partial response (%d chars)",
                            model, len(partial),
                        )
                        return partial
                    logger.error("OpenRouter request error (model=%s, attempt %d): %s", model, attempt + 1, exc)
                    if attempt == self.max_retries:
                        if model != FALLBACK_FREE_MODEL:
                            break
                        raise
                    await asyncio.sleep(2 ** attempt)

        if last_exc:
            raise last_exc
        return ""

    # ------------------------------------------------------------------
    # Non-streaming (fallback)
    # ------------------------------------------------------------------

    async def complete(
        self,
        user_message: str,
        model: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Non-streaming completion. Returns the full response content.
        """
        last_exc: Optional[Exception] = None
        target = model or self.model

        for try_model in self._models_to_try(target):
            payload = self._build_payload(user_message, stream=False, model=try_model, json_mode=json_mode)

            for attempt in range(self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            OPENROUTER_API_URL,
                            headers=self._headers(),
                            json=payload,
                        )
                        await self._raise_for_response(response)
                        body_bytes = await response.aread()
                        data = json.loads(body_bytes)
                        content = data["choices"][0]["message"].get("content")
                        return content if content is not None else ""

                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    logger.error("OpenRouter error (model=%s, attempt %d): %s", try_model, attempt + 1, exc)
                    if self._should_try_fallback(exc) and try_model != FALLBACK_FREE_MODEL:
                        break
                    if attempt == self.max_retries:
                        raise
                    await asyncio.sleep(2 ** attempt)

                except (httpx.RequestError, KeyError) as exc:
                    last_exc = exc
                    logger.error("OpenRouter error (model=%s, attempt %d): %s", try_model, attempt + 1, exc)
                    if attempt == self.max_retries:
                        if try_model != FALLBACK_FREE_MODEL:
                            break
                        raise
                    await asyncio.sleep(2 ** attempt)

        if last_exc:
            raise last_exc
        return ""
