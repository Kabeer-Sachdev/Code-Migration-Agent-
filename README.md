# .NET → Java Spring Boot Migration Agent

An AI-powered code migration platform that converts .NET/C# projects into production-ready **Java Spring Boot 3** code using OpenRouter LLM + a RAG engine with 35+ curated migration patterns.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🤖 LLM-powered | OpenRouter (Claude, GPT-4o, Gemini) |
| 📚 RAG Engine | 35+ .NET→Java migration patterns |
| 🔌 MCP Tools | `read_file`, `write_file`, `search_code` |
| 🪝 Hook Engine | Live lifecycle events via WebSocket |
| 🧪 JUnit 5 Tests | Auto-generated + augmented test stubs |
| 📦 Maven ZIP | Downloadable complete Spring Boot project |
| 🎨 Premium UI | Dark glassmorphism with live streaming terminal |

---

## 🚀 Quick Start

### Prerequisites
- Python **3.11+**
- An [OpenRouter](https://openrouter.ai) API key

### Run
```bash
# From the project root
python run.py
```

Open **http://localhost:8000** in your browser.

---

## 🗂️ Project Structure

```
code migration/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── agent/
│   │   ├── migration_agent.py   # Pipeline orchestrator
│   │   ├── analyzer.py          # .NET code analyzer (MCP-based)
│   │   ├── converter.py         # LLM prompt + response parser
│   │   ├── test_generator.py    # JUnit 5 test augmentation
│   │   └── packager.py          # Maven ZIP builder
│   ├── tools/
│   │   ├── mcp_tools.py         # MCP: read_file, write_file, search_code
│   │   └── file_store.py        # In-memory job-scoped file store
│   ├── rag/
│   │   ├── rag_engine.py        # Keyword-weighted pattern retrieval
│   │   └── patterns.py          # 35+ migration pattern library
│   ├── llm/
│   │   └── openrouter_client.py # Async streaming OpenRouter client
│   ├── hooks/
│   │   └── hook_engine.py       # Async event bus + WS broadcaster
│   └── api/
│       ├── routes.py            # REST + WebSocket endpoints
│       └── models.py            # Pydantic request/response models
├── frontend/
│   ├── index.html               # Premium dark SPA
│   ├── styles.css               # Glassmorphism design system
│   └── app.js                   # WS client + UI logic
├── run.py                       # One-command launcher
└── README.md
```

---

## 🔄 Migration Pipeline

```
Upload .NET files
      │
      ▼
[Hook: MIGRATION_START]
      │
      ▼
Analyzer — detect frameworks via MCP search_code
      │
      ▼
[Hook: ANALYSIS_DONE]
      │
      ▼
RAG Engine — retrieve top-8 migration patterns
      │
      ▼
[Hook: RAG_RETRIEVED]
      │
      ▼
OpenRouter LLM — stream Java Spring Boot code
      │
      ▼
[Hook: LLM_STREAM (per token)] → [Hook: CONVERSION_DONE]
      │
      ▼
Test Generator — augment missing JUnit 5 tests
      │
      ▼
[Hook: TESTS_GENERATED]
      │
      ▼
Packager — build Maven project ZIP
      │
      ▼
[Hook: MIGRATION_COMPLETE]
      │
      ▼
Download ZIP 📦
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/migrate` | Upload files + start migration |
| `GET` | `/api/migrate/{job_id}` | Get full migration result |
| `GET` | `/api/migrate/{job_id}/status` | Poll job status |
| `GET` | `/api/migrate/{job_id}/download` | Download Maven ZIP |
| `WS` | `/api/ws/{job_id}` | Live hook event stream |

---

## 🤖 Supported OpenRouter Models (Free Tier)

All models below use OpenRouter's **free** tier — no credits required. Append `:free` to any supported model ID.

- `qwen/qwen3-coder:free` *(default — best for code migration)*
- `openrouter/free` *(auto-selects an available free model)*
- `meta-llama/llama-3.3-70b-instruct:free`
- `openai/gpt-oss-120b:free`

---

## 📋 Migration Patterns (RAG)

The RAG engine contains 35+ curated pattern pairs covering:

- **Controllers** — `[ApiController]` → `@RestController`
- **HTTP Verbs** — `[HttpGet]` → `@GetMapping`
- **Data** — `DbContext` / `DbSet` → Spring Data JPA
- **LINQ** — `.Where()` `.Select()` → Java Streams
- **Async** — `async Task` → synchronous + CompletableFuture
- **DI** — `AddScoped` → `@Service` beans
- **Config** — `appsettings.json` → `application.yml`
- **Auth** — JWT Bearer → Spring Security
- **Middleware** — `IMiddleware` → `OncePerRequestFilter`
- **Logging** — `ILogger<T>` → SLF4J + `@Slf4j`
- **Mapping** — AutoMapper → MapStruct
- **Events** — MediatR → Spring `ApplicationEventPublisher`
- **Validation** — FluentValidation → Bean Validation `@Valid`
- **Caching** — `IMemoryCache` → `@Cacheable`
- **Testing** — xUnit + Moq → JUnit 5 + Mockito

---

## ⚙️ Generated Project Structure (ZIP)

```
app/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/com/example/app/
│   │   │   ├── Application.java
│   │   │   ├── controller/
│   │   │   ├── service/
│   │   │   ├── repository/
│   │   │   ├── entity/
│   │   │   └── dto/
│   │   └── resources/
│   │       └── application.yml
│   └── test/
│       └── java/com/example/app/
│           ├── service/   (unit tests)
│           └── controller/ (integration tests)
└── .gitignore
```

---

## 📝 License

MIT — built for educational and productivity use.
