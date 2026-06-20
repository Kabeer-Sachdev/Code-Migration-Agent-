"""
Migration Agent - orchestrates the full pipeline:
  MIGRATION_START → Analyze → RAG → LLM Convert → Test Augment → Package → MIGRATION_COMPLETE
Fires hooks at every stage and streams LLM tokens via WebSocket.
"""
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional

from ..hooks.hook_engine import hook_engine, HookEvent
from ..tools.file_store import file_store
from ..tools.mcp_tools import MCPTools
from ..rag.rag_engine import rag_engine
from ..llm.groq_client import GroqClient
from ..llm.ollama_client import OllamaClient
from ..llm.openrouter_client import OpenRouterClient, DEFAULT_FREE_MODEL
from .analyzer import Analyzer
from .converter import Converter, MigrationOutput
from .test_generator import augment_tests
from .packager import build_zip

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED      = "queued"
    RUNNING     = "running"
    COMPLETE    = "complete"
    ERROR       = "error"


@dataclass
class MigrationJob:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    current_step: str = "Waiting..."
    output: Optional[MigrationOutput] = None
    zip_bytes: Optional[bytes] = None
    error: Optional[str] = None
    token_buffer: str = field(default="", repr=False)


# In-memory job registry
_jobs: Dict[str, MigrationJob] = {}


def create_job() -> str:
    """Create a new migration job and return its ID."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = MigrationJob(job_id=job_id)
    file_store.create_job(job_id)
    return job_id


def get_job(job_id: str) -> Optional[MigrationJob]:
    return _jobs.get(job_id)


async def run_migration(
    job_id: str,
    api_key: str,
    model: str = DEFAULT_FREE_MODEL,
    directory_path: Optional[str] = None,
) -> None:
    """
    Main async migration pipeline. Designed to run in a background task.
    Updates the MigrationJob in-place at every step.
    """
    job = _jobs.get(job_id)
    if not job:
        logger.error("run_migration: job %s not found", job_id)
        return

    job.status = JobStatus.RUNNING

    async def _step(event: HookEvent, msg: str, progress: int, data: Any = None):
        job.current_step = msg
        job.progress = progress
        await hook_engine.fire(event, data=data, job_id=job_id, message=msg)

    try:
        # ── Step 1: Start ────────────────────────────────────────────
        await _step(HookEvent.MIGRATION_START, "🚀 Migration started", 5)

        # ── Scan local directory if provided ─────────────────────────
        if directory_path:
            from pathlib import Path
            scanned_files = []
            allowed_exts = {".cs", ".csproj", ".json", ".xml", ".config", ".txt"}
            ignored_dirs = {"bin", "obj", ".git", ".vs", "migrated-java", "__pycache__", "node_modules"}

            dp = Path(directory_path).resolve()
            logger.info("Scanning local directory: %s", dp)
            has_dotnet = False
            for root, dirs, filenames in os.walk(dp):
                # Prune ignored directories in-place
                dirs[:] = [d for d in dirs if d.lower() not in ignored_dirs]
                
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in allowed_exts:
                        full_path = Path(root) / filename
                        try:
                            rel_path = full_path.relative_to(dp)
                            rel_path_str = str(rel_path).replace("\\", "/") # cross-platform normalize
                            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                                content = f.read()
                            file_store.store_input(job_id, rel_path_str, content)
                            scanned_files.append(rel_path_str)
                            if ext in {".cs", ".csproj"}:
                                has_dotnet = True
                        except Exception as e:
                            logger.error("Failed to read file %s: %s", full_path, e)
            
            logger.info("Scanned local directory: found %d files", len(scanned_files))
            if not has_dotnet:
                raise ValueError("Validation failed: The specified local directory does not contain any .NET source code (.cs or .csproj files).")

        # ── Step 2: MCP Tool setup ───────────────────────────────────
        mcp = MCPTools(job_id)
        files = mcp.list_files()
        
        # Display up to 15 files in log message to avoid bloating terminal
        display_list = files[:15]
        suffix = f" and {len(files) - 15} more..." if len(files) > 15 else ""
        files_str = ", ".join(display_list) + suffix
        
        await _step(
            HookEvent.FILES_UPLOADED,
            f"📁 Loaded {len(files)} file(s): {files_str}",
            10,
            data={"files": files},
        )

        # ── Step 3: Analysis ─────────────────────────────────────────
        await _step(HookEvent.ANALYSIS_DONE, "🔍 Analyzing .NET codebase...", 20)
        analyzer = Analyzer(mcp)
        analysis = analyzer.analyze()
        await _step(
            HookEvent.ANALYSIS_DONE,
            f"✅ Analysis done - .NET {analysis.dotnet_version} | "
            f"Frameworks: {', '.join(analysis.frameworks_detected[:3]) or 'None'}",
            30,
            data=analysis.to_dict(),
        )

        # ── Step 4: RAG Retrieval ────────────────────────────────────
        await _step(HookEvent.RAG_RETRIEVED, "🧠 Querying RAG for migration patterns...", 40)
        combined_code = "\n".join(mcp.get_all_content().values())
        patterns = rag_engine.retrieve_for_code(combined_code, top_k=8)
        await _step(
            HookEvent.RAG_RETRIEVED,
            f"📚 Retrieved {len(patterns)} migration patterns from RAG store",
            50,
            data={"pattern_ids": [p["id"] for p in patterns]},
        )

        # ── Step 5: LLM Conversion (streaming) ──────────────────────
        await _step(HookEvent.LLM_GENERATING, "⚡ Calling LLM - streaming response...", 55)

        # Determine which LLM client to use based on model parameter
        ollama_models = ["llama3.2", "llama3", "llama2", "codellama", "qwen2.5-coder"]
        groq_models = ["llama-3.3-70b-versatile", "llama-3.2-1b-preview", "llama-3.1-8b-instant"]

        if model in ollama_models:
            llm_client = OllamaClient(api_key="", model=model)
            step_msg = f"⚡ Calling Ollama LLM ({model}) - streaming response..."
        elif model in groq_models:
            resolved_key = api_key.strip() or os.environ.get("GROQ_API_KEY", "")
            llm_client = GroqClient(api_key=resolved_key, model=model)
            step_msg = "⚡ Calling Groq LLM - streaming response..."
        else:
            # OpenRouter — use free-tier models (model id ends with :free or is openrouter/free)
            resolved_key = api_key.strip() or os.environ.get("OPENROUTER_API_KEY", "")
            if not resolved_key:
                raise ValueError(
                    "OpenRouter API key required. Set OPENROUTER_API_KEY in backend/.env "
                    "or enter your key in the UI."
                )
            llm_client = OpenRouterClient(api_key=resolved_key, model=model)
            step_msg = f"⚡ Calling OpenRouter LLM ({model}) - streaming response..."

        await _step(HookEvent.LLM_GENERATING, step_msg, 55)

        async def on_token(chunk: str):
            job.token_buffer += chunk
            await hook_engine.fire(
                HookEvent.LLM_STREAM,
                data={"chunk": chunk},
                job_id=job_id,
                message=chunk,
            )

        converter = Converter(mcp=mcp, rag=rag_engine, llm=llm_client)
        migration_output = await converter.convert(analysis=analysis, on_token=on_token)
        await _step(
            HookEvent.CONVERSION_DONE,
            f"✅ Conversion done - {len(migration_output.java_files)} Java file(s) generated",
            75,
            data={"java_files": [f.filename for f in migration_output.java_files]},
        )

        # ── Step 6: Test Augmentation ────────────────────────────────
        await _step(HookEvent.TESTS_GENERATED, "🧪 Augmenting JUnit 5 tests...", 85)
        migration_output.test_files = augment_tests(
            migration_output.java_files,
            migration_output.test_files,
        )
        await _step(
            HookEvent.TESTS_GENERATED,
            f"✅ Tests ready - {len(migration_output.test_files)} test file(s)",
            88,
        )

        # ── Step 7: Package ZIP ──────────────────────────────────────
        await _step(HookEvent.PACKAGING, "📦 Packaging Maven project ZIP...", 92)
        zip_bytes = build_zip(migration_output)

        # ── Step 8: MCP write outputs ────────────────────────────────
        for jf in migration_output.java_files:
            mcp.write_file(jf.filename, jf.content)
        for tf in migration_output.test_files:
            mcp.write_file(tf.filename, tf.content)

        # ── Write local disk outputs if directory_path is provided ───
        if directory_path:
            from pathlib import Path
            from .packager import _DEFAULT_POM, _DEFAULT_APP_YML, _MAIN_CLASS_TEMPLATE
            
            output_dir = Path(directory_path) / "migrated-java"
            logger.info("Writing output files to local disk: %s", output_dir)
            
            def write_local_file(rel_path: str, content: str):
                full_path = output_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            
            # pom.xml
            pom = migration_output.pom_xml.strip() or _DEFAULT_POM.strip()
            write_local_file("pom.xml", pom)
            
            # application.yml
            app_yml = migration_output.application_yml.strip() or _DEFAULT_APP_YML.strip()
            write_local_file("src/main/resources/application.yml", app_yml)
            
            # Application.main
            has_main = any("Application.java" in f.filename for f in migration_output.java_files)
            if not has_main:
                write_local_file("src/main/java/com/example/app/Application.java", _MAIN_CLASS_TEMPLATE)
            
            # Java files
            for jf in migration_output.java_files:
                fn = jf.filename
                if fn.startswith("app/"):
                    fn = fn[4:]
                write_local_file(fn, jf.content)
                
            # Test files
            for tf in migration_output.test_files:
                fn = tf.filename
                if fn.startswith("app/"):
                    fn = fn[4:]
                write_local_file(fn, tf.content)
                
            # .gitignore
            write_local_file(".gitignore", "target/\n*.class\n.idea/\n*.iml\n")
            
            # README.md
            readme = (
                "# Migrated Spring Boot Application\n\n"
                "Auto-migrated from .NET by the Migration Agent.\n\n"
                "## Run\n```bash\nmvn spring-boot:run\n```\n\n"
                "## Swagger UI\nhttp://localhost:8080/swagger-ui.html\n"
            )
            write_local_file("README.md", readme)
            
            await _step(
                HookEvent.PACKAGING,
                f"💾 Migrated code written to local directory: {output_dir.resolve()}",
                95,
            )

        # ── Complete ─────────────────────────────────────────────────
        job.output   = migration_output
        job.zip_bytes = zip_bytes
        job.status   = JobStatus.COMPLETE
        job.progress  = 100

        await _step(
            HookEvent.MIGRATION_COMPLETE,
            f"🎉 Migration complete - {len(migration_output.java_files)} files, "
            f"{len(migration_output.test_files)} tests, ZIP ready",
            100,
            data=migration_output.to_dict(),
        )

    except Exception as exc:
        logger.exception("Migration failed for job %s", job_id)
        job.status = JobStatus.ERROR
        job.error  = str(exc)
        await hook_engine.fire(
            HookEvent.MIGRATION_ERROR,
            data={"error": str(exc)},
            job_id=job_id,
            message=f"❌ Migration failed: {exc}",
        )
