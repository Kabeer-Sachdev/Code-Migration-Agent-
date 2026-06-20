"""
Converter - builds the LLM prompt from analysis + RAG patterns,
calls Groq, and parses the JSON response into a MigrationOutput.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable, Union

from ..llm.groq_client import GroqClient
from ..llm.ollama_client import OllamaClient
from ..llm.openrouter_client import OpenRouterClient
from ..rag.rag_engine import RAGEngine
from ..tools.mcp_tools import MCPTools
from .analyzer import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class JavaFile:
    filename: str
    content: str


@dataclass
class MigrationOutput:
    analysis: Dict[str, Any] = field(default_factory=dict)
    java_files: List[JavaFile] = field(default_factory=list)
    test_files: List[JavaFile] = field(default_factory=list)
    pom_xml: str = ""
    application_yml: str = ""
    notes: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "analysis": self.analysis,
            "java_files": [{"filename": f.filename, "content": f.content} for f in self.java_files],
            "test_files": [{"filename": f.filename, "content": f.content} for f in self.test_files],
            "pom_xml": self.pom_xml,
            "application_yml": self.application_yml,
            "notes": self.notes,
        }


def _build_prompt(
    files: Dict[str, str],
    analysis: AnalysisResult,
    rag_context: str,
) -> str:
    """
    Constructs the full user-turn prompt injected into the LLM.
    Structured sections: instructions → analysis → RAG context → source files.
    """
    file_sections = []
    for filename, content in files.items():
        file_sections.append(f"### File: {filename}\n```csharp\n{content}\n```")

    files_block = "\n\n".join(file_sections)

    prompt = f"""Migrate the following .NET source files to production-ready Java Spring Boot 3.

## Analysis of the .NET Codebase
- .NET Version: {analysis.dotnet_version}
- Frameworks detected: {', '.join(analysis.frameworks_detected) or 'None'}
- NuGet dependencies: {', '.join(analysis.dependencies) or 'None'}
- Migration considerations:
{chr(10).join(f'  • {c}' for c in analysis.migration_considerations)}

## Retrieved Migration Patterns (RAG)
{rag_context}

## Source Files to Migrate
{files_block}

## Your Task
1. Analyze the above .NET code thoroughly.
2. Apply the retrieved migration patterns where applicable.
3. Generate idiomatic Java Spring Boot 3 / Java 21 equivalents.
4. Preserve ALL business logic exactly.
5. **Validation Migration**: Translate any .NET validation (like DataAnnotations e.g. `[Required]`, `[StringLength]`, `[EmailAddress]`, or custom FluentValidation rules) into Spring Boot validation using standard Java Bean Validation annotations (e.g., `@NotNull`, `@NotBlank`, `@Size`, `@Email`, `@Pattern` from package `jakarta.validation.constraints`) in the generated Java model/DTO classes, and use `@Valid` or `@Validated` in the REST controller parameters to trigger request payload validation.
6. Return ONLY valid JSON matching the schema in your system prompt. No markdown, no extra text.

Use package name: com.example.app
"""
    return prompt


def _extract_java_from_markdown(raw: str) -> List[JavaFile]:
    """Fallback: pull Java source from markdown fences when JSON has no java_files."""
    files: List[JavaFile] = []
    for i, match in enumerate(re.finditer(r"```(?:java)?\s*\n(.*?)```", raw, re.DOTALL)):
        content = match.group(1).strip()
        if len(content) < 20 or "class " not in content:
            continue
        class_match = re.search(r"(?:public\s+)?class\s+(\w+)", content)
        class_name = class_match.group(1) if class_match else f"GeneratedClass{i + 1}"
        files.append(JavaFile(
            filename=f"src/main/java/com/example/app/{class_name}.java",
            content=content,
        ))
    return files


def _try_repair_json(json_str: str) -> Optional[dict]:
    """Attempt to parse truncated JSON from free models that cut off mid-response."""
    suffixes = [
        '"}]}',
        '"]}',
        '"}',
        ']}',
        '}',
    ]
    for suffix in suffixes:
        try:
            return json.loads(json_str + suffix)
        except json.JSONDecodeError:
            continue
    return None


def _parse_json_data(json_str: str) -> Optional[dict]:
    """Parse JSON from LLM output, tolerating trailing garbage or truncation."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        if "Extra data" in str(exc):
            try:
                obj, _ = json.JSONDecoder().raw_decode(json_str)
                return obj
            except json.JSONDecodeError:
                pass
        repaired = _try_repair_json(json_str)
        if repaired:
            return repaired
        try:
            start = json_str.find("{")
            if start >= 0:
                obj, _ = json.JSONDecoder().raw_decode(json_str, start)
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _extract_json(raw: str) -> Optional[str]:
    """
    Robustly extract JSON from LLM response.
    Handles cases where the model wraps output in markdown fences.
    """
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]

    return raw if raw.startswith("{") else None


def _parse_response(raw: str, analysis: AnalysisResult) -> MigrationOutput:
    """
    Parse the raw LLM response JSON into a MigrationOutput.
    Falls back gracefully if the JSON is malformed.
    """
    output = MigrationOutput(raw_response=raw)

    json_str = _extract_json(raw)
    if not json_str:
        logger.error("Could not extract JSON from LLM response. Raw output (first 500 chars):\n%s", raw[:500])
        output.notes = {
            "key_decisions": [],
            "potential_risks": ["LLM did not return valid JSON - raw output stored in raw_response"],
        }
        # Store raw as a Java comment file so user sees something
        output.java_files.append(JavaFile(
            filename="src/main/java/com/example/app/MigrationOutput.txt",
            content=raw,
        ))
        return output

    data = _parse_json_data(json_str)
    if not data:
        logger.error("Could not parse JSON from LLM response. JSON string (first 500 chars):\n%s", json_str[:500])
        data = {}
        output.notes = {
            "key_decisions": [],
            "potential_risks": ["LLM returned malformed JSON - partial response stored."],
        }

    # Populate output from parsed data — prefer backend analysis over LLM guesses
    llm_analysis = data.get("analysis") or {}
    backend_analysis = analysis.to_dict()
    output.analysis = {
        **llm_analysis,
        "dotnet_version": backend_analysis.get("dotnet_version") or llm_analysis.get("dotnet_version", "Unknown"),
        "frameworks_detected": backend_analysis.get("frameworks_detected") or llm_analysis.get("frameworks_detected", []),
        "dependencies": backend_analysis.get("dependencies") or llm_analysis.get("dependencies", []),
        "migration_considerations": backend_analysis.get("migration_considerations") or llm_analysis.get("migration_considerations", []),
    }
    output.pom_xml = data.get("pom_xml", "")
    output.application_yml = data.get("application_yml", "")
    output.notes = data.get("notes", {"key_decisions": [], "potential_risks": []})

    # Parse java_files with better error handling
    java_files_data = data.get("java_files", [])
    logger.info("Parsing java_files array: %d items", len(java_files_data))
    
    for jf in java_files_data:
        if isinstance(jf, dict) and "filename" in jf and "content" in jf:
            output.java_files.append(JavaFile(filename=jf["filename"], content=jf["content"]))
            logger.info("Added Java file: %s", jf["filename"])
        else:
            logger.warning("Invalid java_file entry (missing filename or content): %s", jf)

    test_files_data = data.get("test_files", [])
    logger.info("Parsing test_files array: %d items", len(test_files_data))
    
    for tf in test_files_data:
        if isinstance(tf, dict) and "filename" in tf and "content" in tf:
            output.test_files.append(JavaFile(filename=tf["filename"], content=tf["content"]))
            logger.info("Added test file: %s", tf["filename"])
        else:
            logger.warning("Invalid test_file entry (missing filename or content): %s", tf)

    if not output.java_files:
        output.java_files = _extract_java_from_markdown(raw)
        if output.java_files:
            logger.info("Recovered %d Java file(s) from markdown in LLM response", len(output.java_files))

    if not output.java_files:
        logger.warning("No java_files were parsed from LLM response!")

    # Run code validation checks on each java and test file
    validation_warnings = []
    for jf in output.java_files:
        validation_warnings.extend(validate_java_file(jf))
    for tf in output.test_files:
        validation_warnings.extend(validate_java_file(tf))
        
    if validation_warnings:
        # Initialize notes structure if missing
        if not isinstance(output.notes, dict):
            output.notes = {"key_decisions": [], "potential_risks": []}
        risks = output.notes.setdefault("potential_risks", [])
        if not isinstance(risks, list):
            risks = [risks] if risks else []
            output.notes["potential_risks"] = risks
        
        # Append warnings to risks so they appear on the notes panel
        risks.extend(validation_warnings)
        logger.warning("Java validation generated %d warning(s)", len(validation_warnings))

    return output


def validate_java_file(jf: JavaFile) -> List[str]:
    """
    Perform structural and syntax validation on a generated Java/test file.
    Returns a list of warning/error messages.
    """
    warnings = []
    content = jf.content
    filename = jf.filename
    short_name = filename.split("/")[-1]
    
    # 1. Curly brace balance check
    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        warnings.append(
            f"Validation warning: Unbalanced curly braces in {short_name} "
            f"(found {open_braces} open '{{', {close_braces} close '}}')."
        )
        
    # 2. Parentheses balance check
    open_parens = content.count("(")
    close_parens = content.count(")")
    if open_parens != close_parens:
        warnings.append(
            f"Validation warning: Unbalanced parentheses in {short_name} "
            f"(found {open_parens} open '(', {close_parens} close ')')."
        )
        
    # 3. Package statement check
    if short_name.endswith(".java") and "package " not in content:
        warnings.append(f"Validation warning: Missing package declaration in {short_name}.")
        
    # 4. Class/interface/enum name matching filename check
    if short_name.endswith(".java") and "GeneratedClass" not in short_name:
        expected_class = short_name.replace(".java", "")
        # Find class/interface/enum/record declarations
        pattern = r"\b(?:public\s+)?(?:class|interface|enum|record)\s+(\w+)\b"
        matches = re.findall(pattern, content)
        if matches:
            if expected_class not in matches:
                warnings.append(
                    f"Validation warning: Filename '{short_name}' does not match "
                    f"any declared class/interface/enum name in the file: {', '.join(matches)}."
                )
        else:
            warnings.append(f"Validation warning: No class, interface, enum, or record declaration found in {short_name}.")
            
    return warnings


_RETRY_SUFFIX = """

CRITICAL RETRY INSTRUCTION:
Your previous response was REJECTED because java_files was empty or missing.
You MUST include at least one complete Java source file in the java_files array.
Convert every C# class you see into a Java Spring Boot class.
Do NOT return an empty java_files array under any circumstances.
Return ONLY valid JSON — no markdown fences.
"""


async def _retry_empty_response(
    llm: OpenRouterClient,
    prompt: str,
    analysis: AnalysisResult,
    on_token: Optional[Callable[[str], Awaitable[None]]] = None,
) -> MigrationOutput:
    """Retry with non-streaming calls across free models when the first pass yields no files."""
    retry_prompt = prompt + _RETRY_SUFFIX

    for model in llm.retry_models():
        if model == llm.model:
            continue  # already tried during streaming
        logger.warning("Retrying LLM conversion with model=%s (empty java_files)", model)
        try:
            raw = await llm.complete(retry_prompt, model=model, json_mode=True)
            if on_token and raw:
                await on_token(raw)
            output = _parse_response(raw, analysis)
            if output.java_files:
                logger.info("Retry succeeded with model=%s (%d files)", model, len(output.java_files))
                return output
        except Exception as exc:
            logger.error("Retry failed for model=%s: %s", model, exc)

    raise ValueError(
        "LLM returned no Java files after multiple retries. "
        "Free models may be rate-limited — wait a minute and try again, "
        "or switch to 'Auto Free Router' in the model dropdown."
    )


class Converter:
    """
    Orchestrates the LLM conversion step:
      1. Retrieve RAG patterns relevant to the code.
      2. Build the prompt.
      3. Stream the LLM response.
      4. Parse and return MigrationOutput.
    """

    def __init__(
        self,
        mcp: MCPTools,
        rag: RAGEngine,
        llm: Union[GroqClient, OllamaClient, OpenRouterClient],
    ) -> None:
        self.mcp = mcp
        self.rag = rag
        self.llm = llm

    async def convert(
        self,
        analysis: AnalysisResult,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> MigrationOutput:
        """
        Run the full conversion pipeline for this job.
        `on_token` receives each streamed token from the LLM.
        """
        files = self.mcp.get_all_content()
        if not files:
            raise ValueError("No files to convert")

        # RAG retrieval - combine all code for the query
        combined_code = "\n".join(files.values())
        patterns = self.rag.retrieve_for_code(combined_code, top_k=8)
        rag_context = self.rag.format_for_prompt(patterns)
        logger.info("RAG retrieved %d patterns", len(patterns))

        # Build LLM prompt
        prompt = _build_prompt(files, analysis, rag_context)
        logger.info("Prompt built (%d chars), starting LLM stream...", len(prompt))

        # Stream LLM response
        raw_response = await self.llm.stream(prompt, on_token=on_token)
        logger.info("LLM responded (%d chars)", len(raw_response))

        # Parse and return
        output = _parse_response(raw_response, analysis)

        # Free OpenRouter models often return empty java_files — retry non-streaming
        if not output.java_files and isinstance(self.llm, OpenRouterClient):
            output = await _retry_empty_response(self.llm, prompt, analysis, on_token)

        return output
