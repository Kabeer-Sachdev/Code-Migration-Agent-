"""
Ollama LLM Client - async streaming HTTP client for local/hosted Ollama instances.
Supports streaming and non-streaming modes.
"""
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/chat"

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


class OllamaClient:
    """
    Async client for Ollama Chat API.
    Supports streaming (SSE) with a token callback and final aggregation.
    Can connect to local Ollama (localhost:11434) or remote instance.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/chat"
        self.timeout = timeout
        self.max_retries = max_retries
        logger.info("OllamaClient initialized with model=%s, url=%s", model, self.api_url)

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, user_message: str, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": MIGRATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "stream": stream,
            "options": {
                "temperature": 0.2,
                "num_predict": 32000,
            }
        }

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
        payload = self._build_payload(user_message, stream=True)
        full_response = []

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info("Sending request to %s (attempt %d/%d)", self.api_url, attempt + 1, self.max_retries + 1)
                    
                    async with client.stream(
                        "POST",
                        self.api_url,
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        logger.info("Got response status %d", response.status_code)
                        
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                data = json.loads(line)
                                
                                # Ollama returns message chunks
                                message = data.get("message", {})
                                content = message.get("content", "")
                                
                                if content:
                                    full_response.append(content)
                                    if on_token:
                                        await on_token(content)
                                
                                # Check if this is the last message
                                if data.get("done", False):
                                    break
                                    
                            except json.JSONDecodeError as exc:
                                logger.warning("JSON decode error on line: %s", line[:100])
                                continue

                response_str = "".join(full_response)
                logger.info("Stream completed (%d chars)", len(response_str))
                return response_str

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.error("Request error (attempt %d): %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    # ------------------------------------------------------------------
    # Non-streaming (fallback)
    # ------------------------------------------------------------------

    async def call(self, user_message: str) -> str:
        """
        Non-streaming call to Ollama.
        Useful as fallback or when streaming is not needed.
        """
        payload = self._build_payload(user_message, stream=False)

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.api_url,
                        headers=self._headers(),
                        json=payload,
                    )
                    response.raise_for_status()

                    data = response.json()
                    message = data.get("message", {})
                    content = message.get("content", "")

                    logger.info("Non-streaming call returned %d chars", len(content))
                    return content

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                logger.error("Request error (attempt %d): %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    # Alias for compatibility with GroqClient interface
    async def generate(self, user_message: str) -> str:
        return await self.call(user_message)
