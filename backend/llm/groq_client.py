# -*- coding: utf-8 -*-
"""
Groq LLM Client - async streaming HTTP client for Groq API.
Supports both streaming and non-streaming modes.
"""
import json
import logging
import asyncio
from typing import Optional, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

MIGRATION_SYSTEM_PROMPT = """You are a .NET to Java Spring Boot 3 migration expert.

RULES:
- Generate idiomatic Java 21 Spring Boot 3 code
- Use Spring Data JPA, Lombok, constructor injection
- Create JUnit 5 tests with Mockito
- Preserve all business logic 100%

OUTPUT: Valid JSON only. No markdown.

Schema:
{
  "analysis": {"dotnet_version": "string", "frameworks_detected": ["string"], "dependencies": []},
  "java_files": [{"filename": "src/main/java/com/example/app/ClassName.java", "content": "Java code"}],
  "test_files": [{"filename": "src/test/java/com/example/app/ClassNameTest.java", "content": "JUnit 5"}],
  "pom_xml": "Maven config",
  "application_yml": "Spring config",
  "notes": {"key_decisions": [], "potential_risks": []}
}

Start with { immediately."""


class GroqClient:
    """
    Async client for Groq Chat API.
    Supports streaming with token callback and final aggregation.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_url = GROQ_API_URL
        self.timeout = timeout
        self.max_retries = max_retries
        logger.info("GroqClient initialized with model=%s", model)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _build_payload(self, user_message: str, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": MIGRATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "stream": stream,
            "temperature": 0.2,
            "max_tokens": 32000,
        }

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
                    logger.info("Sending streaming request to Groq (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                    
                    async with client.stream(
                        "POST",
                        self.api_url,
                        json=payload,
                        headers=self._headers(),
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            logger.error("Groq API error (status %d): %s", response.status_code, error_text.decode('utf-8', errors='replace'))
                            raise Exception(f"Groq API returned status {response.status_code}: {error_text.decode('utf-8', errors='replace')}")

                        async for line in response.aiter_lines():
                            if not line.strip() or line.startswith(":"):
                                continue
                            
                            if line.startswith("data: "):
                                data = line[6:].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(data)
                                    if "choices" in chunk_json and len(chunk_json["choices"]) > 0:
                                        delta = chunk_json["choices"][0].get("delta", {})
                                        if "content" in delta:
                                            chunk = delta["content"]
                                            full_response.append(chunk)
                                            if on_token:
                                                await on_token(chunk)
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse chunk: %s", data)
                                    continue

                        result = "".join(full_response)
                        logger.info("Streaming complete. Total response length: %d characters", len(result))
                        return result

            except asyncio.TimeoutError:
                logger.warning("Request timed out on attempt %d/%d", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except Exception as e:
                logger.error("Request failed on attempt %d/%d: %s", attempt + 1, self.max_retries + 1, e)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise Exception(f"Failed after {self.max_retries + 1} attempts")

    async def generate(self, user_message: str) -> str:
        """
        Generate a non-streaming response from the LLM.
        Waits for the full response before returning.
        """
        payload = self._build_payload(user_message, stream=False)

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info("Sending non-streaming request to Groq (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=self._headers(),
                    )

                    if response.status_code != 200:
                        error_text = response.text
                        logger.error("Groq API error (status %d): %s", response.status_code, error_text)
                        raise Exception(f"Groq API returned status {response.status_code}: {error_text}")

                    result_json = response.json()
                    if "choices" in result_json and len(result_json["choices"]) > 0:
                        return result_json["choices"][0]["message"]["content"]
                    else:
                        raise Exception(f"Unexpected response format: {result_json}")

            except asyncio.TimeoutError:
                logger.warning("Request timed out on attempt %d/%d", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except Exception as e:
                logger.error("Request failed on attempt %d/%d: %s", attempt + 1, self.max_retries + 1, e)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        raise Exception(f"Failed after {self.max_retries + 1} attempts")
