"""
Analyzer - examines uploaded .NET source files and produces a structured
AnalysisResult describing frameworks, dependencies, and migration considerations.
Works via MCP Tools (read_file, search_code) on the uploaded file set.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from ..tools.mcp_tools import MCPTools

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    dotnet_version: str = "Unknown"
    frameworks_detected: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    migration_considerations: List[str] = field(default_factory=list)
    has_controllers: bool = False
    has_ef_core: bool = False
    has_async: bool = False
    has_di: bool = False
    has_linq: bool = False
    has_auth: bool = False
    has_middleware: bool = False
    has_hosted_service: bool = False
    has_automapper: bool = False
    has_mediatr: bool = False
    has_fluent_validation: bool = False
    summary_query: str = ""  # Used to drive RAG retrieval

    def to_dict(self) -> dict:
        return {
            "dotnet_version": self.dotnet_version,
            "frameworks_detected": self.frameworks_detected,
            "dependencies": self.dependencies,
            "migration_considerations": self.migration_considerations,
        }


# ------------------------------------------------------------------
# Detection rules: (label, regex_pattern, attribute_name, note)
# ------------------------------------------------------------------
_DETECTION_RULES = [
    # Framework detections
    ("ASP.NET Core (Controllers)", r"\[ApiController\]|ControllerBase|IActionResult",
     "has_controllers", "ASP.NET Controllers → @RestController"),
    ("Entity Framework Core", r"DbContext|DbSet<|\.SaveChangesAsync|EntityTypeBuilder",
     "has_ef_core", "EF Core → Spring Data JPA (JpaRepository)"),
    ("Async/Await", r"async\s+Task|await\s+",
     "has_async", "async/await → synchronous Spring (thread pool) or CompletableFuture"),
    ("Dependency Injection", r"IServiceCollection|services\.Add|IServiceProvider",
     "has_di", "DI registration → Spring @Service/@Component beans"),
    ("LINQ", r"\.Where\(|\.Select\(|\.FirstOrDefault\(|\.Any\(|from\s+\w+\s+in\s+",
     "has_linq", "LINQ → Java Streams API"),
    ("JWT / Authentication", r"\[Authorize\]|AddAuthentication|AddJwtBearer|JwtSecurityToken",
     "has_auth", "JWT Auth → Spring Security with JwtFilter"),
    ("Middleware", r"IMiddleware|RequestDelegate|app\.Use",
     "has_middleware", "Middleware → Spring OncePerRequestFilter / HandlerInterceptor"),
    ("IHostedService / BackgroundService", r"IHostedService|BackgroundService|ExecuteAsync",
     "has_hosted_service", "BackgroundService → @Scheduled component"),
    ("AutoMapper", r"IMapper|CreateMap|\.Map<",
     "has_automapper", "AutoMapper → MapStruct @Mapper"),
    ("MediatR", r"IMediator|IRequest|IRequestHandler|INotification",
     "has_mediatr", "MediatR → Spring ApplicationEventPublisher"),
    ("FluentValidation", r"AbstractValidator|RuleFor\(",
     "has_fluent_validation", "FluentValidation → Spring @Valid + Bean Validation"),
]

_VERSION_PATTERNS = [
    (r"net9\.|<TargetFramework>net9", "9.0"),
    (r"net8\.|<TargetFramework>net8", "8.0"),
    (r"net7\.|<TargetFramework>net7", "7.0"),
    (r"net6\.|<TargetFramework>net6", "6.0"),
    (r"netcoreapp3", "3.1"),
    (r"net5\.", "5.0"),
    (r"netstandard2", "Standard 2.x"),
]

_DEPENDENCY_PATTERNS = [
    (r"Microsoft\.EntityFrameworkCore", "Microsoft.EntityFrameworkCore"),
    (r"AutoMapper", "AutoMapper"),
    (r"MediatR", "MediatR"),
    (r"FluentValidation", "FluentValidation"),
    (r"Serilog", "Serilog"),
    (r"NLog", "NLog"),
    (r"Swashbuckle|Swagger", "Swashbuckle (Swagger)"),
    (r"Newtonsoft\.Json", "Newtonsoft.Json"),
    (r"StackExchange\.Redis", "StackExchange.Redis"),
    (r"Npgsql", "Npgsql (PostgreSQL)"),
    (r"Microsoft\.Data\.SqlClient|SqlServer", "SQL Server"),
    (r"Dapper", "Dapper"),
    (r"xunit|NUnit|MSTest", "Unit Testing Framework"),
    (r"Moq|NSubstitute", "Mocking Framework"),
]


class Analyzer:
    """
    Analyses uploaded .NET source files via MCP Tools.
    Produces an AnalysisResult used to guide RAG retrieval and LLM prompting.
    """

    def __init__(self, mcp: MCPTools) -> None:
        self.mcp = mcp

    def analyze(self) -> AnalysisResult:
        result = AnalysisResult()
        all_files = self.mcp.get_all_content()

        if not all_files:
            logger.warning("Analyzer: no files to analyze")
            result.migration_considerations.append("No files were uploaded for analysis.")
            return result

        # Combine all content for global pattern search
        combined = "\n".join(all_files.values())
        logger.info("Analyzer: analyzing %d files (%d chars total)", len(all_files), len(combined))

        # Detect .NET version
        for pat, version in _VERSION_PATTERNS:
            if re.search(pat, combined, re.IGNORECASE):
                result.dotnet_version = version
                break

        # Detect dependencies from .csproj files
        csproj_content = ""
        for name, content in all_files.items():
            if name.endswith(".csproj"):
                csproj_content += content

        all_scan = combined + csproj_content
        for dep_pat, dep_name in _DEPENDENCY_PATTERNS:
            if re.search(dep_pat, all_scan, re.IGNORECASE):
                result.dependencies.append(dep_name)

        # Run framework detection rules
        query_terms = []
        for label, pattern, attr, note in _DETECTION_RULES:
            hits = self.mcp.search_code(pattern)
            if hits:
                result.frameworks_detected.append(label)
                setattr(result, attr, True)
                result.migration_considerations.append(note)
                query_terms.append(attr.replace("has_", ""))
                logger.debug("Detected: %s (%d file(s))", label, len(hits))

        # Additional specific checks
        if result.has_ef_core:
            # Check for migrations folder
            if any("migration" in n.lower() for n in all_files):
                result.migration_considerations.append(
                    "EF Core migration files detected → use Flyway SQL scripts instead"
                )

        if result.has_controllers:
            # Count controller files
            ctrl_count = sum(1 for n in all_files if "controller" in n.lower())
            if ctrl_count > 0:
                result.migration_considerations.append(
                    f"{ctrl_count} controller file(s) detected → generate @RestController classes"
                )

        if result.has_async:
            result.migration_considerations.append(
                "async/await methods → convert to synchronous; Spring Boot's Tomcat thread pool handles concurrency"
            )

        if not result.frameworks_detected:
            result.frameworks_detected.append("Plain C# / .NET")
            result.migration_considerations.append("No special frameworks detected - standard POJO migration")

        # Build summary query for RAG
        result.summary_query = " ".join(query_terms + result.frameworks_detected)

        logger.info(
            "Analysis complete: .NET %s | frameworks=%s | deps=%s",
            result.dotnet_version,
            result.frameworks_detected,
            result.dependencies,
        )
        return result
