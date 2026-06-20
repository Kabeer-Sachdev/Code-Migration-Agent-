"""
RAG Patterns - 35+ curated .NET → Java Spring Boot migration pattern pairs.
Each pattern has:
  - id          : unique string
  - category    : grouping (controller, data, config, async, etc.)
  - dotnet       : description / code snippet of the .NET concept
  - java         : equivalent Spring Boot concept / snippet
  - keywords     : list of terms used for retrieval scoring
"""

MIGRATION_PATTERNS = [
    # =========================================================
    # CONTROLLERS / REST
    # =========================================================
    {
        "id": "ctrl-001",
        "category": "controller",
        "dotnet": "[ApiController] [Route(\"api/[controller]\")] ControllerBase class",
        "java": "@RestController @RequestMapping(\"/api/resource\") class",
        "keywords": ["apicontroller", "controllerbase", "route", "controller", "restcontroller"],
        "example_dotnet": "[ApiController]\n[Route(\"api/[controller]\")]\npublic class ProductsController : ControllerBase { }",
        "example_java": "@RestController\n@RequestMapping(\"/api/products\")\npublic class ProductController { }",
    },
    {
        "id": "ctrl-002",
        "category": "controller",
        "dotnet": "[HttpGet] [HttpPost] [HttpPut] [HttpDelete] HTTP verb attributes",
        "java": "@GetMapping @PostMapping @PutMapping @DeleteMapping",
        "keywords": ["httpget", "httppost", "httpput", "httpdelete", "getmapping", "postmapping"],
        "example_dotnet": "[HttpGet(\"{id}\")]\npublic IActionResult GetById(int id) { }",
        "example_java": "@GetMapping(\"/{id}\")\npublic ResponseEntity<ProductDto> getById(@PathVariable Long id) { }",
    },
    {
        "id": "ctrl-003",
        "category": "controller",
        "dotnet": "IActionResult / ActionResult<T> return types",
        "java": "ResponseEntity<T> return type",
        "keywords": ["iactionresult", "actionresult", "responseentity", "ok", "notfound", "badrequest"],
        "example_dotnet": "return Ok(product);\nreturn NotFound();\nreturn BadRequest(errors);",
        "example_java": "return ResponseEntity.ok(productDto);\nreturn ResponseEntity.notFound().build();\nreturn ResponseEntity.badRequest().body(errors);",
    },
    {
        "id": "ctrl-004",
        "category": "controller",
        "dotnet": "[FromBody] [FromRoute] [FromQuery] parameter binding",
        "java": "@RequestBody @PathVariable @RequestParam parameter binding",
        "keywords": ["frombody", "fromroute", "fromquery", "requestbody", "pathvariable", "requestparam"],
        "example_dotnet": "public IActionResult Create([FromBody] CreateProductDto dto) { }",
        "example_java": "public ResponseEntity<ProductDto> create(@Valid @RequestBody CreateProductDto dto) { }",
    },
    {
        "id": "ctrl-005",
        "category": "controller",
        "dotnet": "ModelState validation with [Required] annotations",
        "java": "Bean Validation with @Valid + @NotNull @NotBlank @Size",
        "keywords": ["modelstate", "required", "valid", "notblank", "notNull", "validation"],
        "example_dotnet": "if (!ModelState.IsValid) return BadRequest(ModelState);",
        "example_java": "// @Valid on method param triggers automatic validation\n// Spring returns 400 automatically on constraint violations",
    },
    # =========================================================
    # DEPENDENCY INJECTION
    # =========================================================
    {
        "id": "di-001",
        "category": "di",
        "dotnet": "services.AddScoped / AddTransient / AddSingleton DI registration",
        "java": "@Service @Component @Repository @Singleton Spring beans",
        "keywords": ["addscoped", "addtransient", "addsingleton", "service", "component", "bean"],
        "example_dotnet": "services.AddScoped<IProductService, ProductService>();",
        "example_java": "@Service\npublic class ProductService implements IProductService { }",
    },
    {
        "id": "di-002",
        "category": "di",
        "dotnet": "Constructor injection via IServiceProvider",
        "java": "Constructor injection (Spring default, no @Autowired needed with single constructor)",
        "keywords": ["constructor", "inject", "autowired", "iserviceprovider"],
        "example_dotnet": "public ProductService(IProductRepository repo, ILogger<ProductService> logger) { }",
        "example_java": "@RequiredArgsConstructor // Lombok\npublic class ProductService {\n    private final ProductRepository productRepository;\n    private final Logger log = LoggerFactory.getLogger(getClass());\n}",
    },
    # =========================================================
    # ENTITY FRAMEWORK → SPRING DATA JPA
    # =========================================================
    {
        "id": "ef-001",
        "category": "data",
        "dotnet": "DbContext class with DbSet<T> properties",
        "java": "Spring Data JPA with JpaRepository<T, ID>",
        "keywords": ["dbcontext", "dbset", "entityframework", "jparepository", "springdata"],
        "example_dotnet": "public class AppDbContext : DbContext {\n    public DbSet<Product> Products { get; set; }\n}",
        "example_java": "@Repository\npublic interface ProductRepository extends JpaRepository<Product, Long> { }",
    },
    {
        "id": "ef-002",
        "category": "data",
        "dotnet": "Entity annotations: [Key] [Required] [MaxLength] [Column]",
        "java": "JPA annotations: @Id @GeneratedValue @NotNull @Column @Size",
        "keywords": ["key", "column", "maxlength", "id", "generatedvalue", "entity", "table"],
        "example_dotnet": "[Key]\npublic int Id { get; set; }\n[Required][MaxLength(255)]\npublic string Name { get; set; }",
        "example_java": "@Id @GeneratedValue(strategy = GenerationType.IDENTITY)\nprivate Long id;\n@NotBlank @Size(max = 255)\nprivate String name;",
    },
    {
        "id": "ef-003",
        "category": "data",
        "dotnet": "LINQ queries: .Where() .Select() .Include() .FirstOrDefault()",
        "java": "JPQL @Query / Spring Data derived query methods / Java Streams",
        "keywords": ["linq", "where", "select", "include", "firstordefault", "query", "stream"],
        "example_dotnet": "_context.Products.Where(p => p.IsActive).Include(p => p.Category).ToList()",
        "example_java": "// Derived method:\nList<Product> findByIsActiveTrue();\n// Custom JPQL:\n@Query(\"SELECT p FROM Product p JOIN FETCH p.category WHERE p.isActive = true\")\nList<Product> findActiveWithCategory();",
    },
    {
        "id": "ef-004",
        "category": "data",
        "dotnet": "EF Core migrations",
        "java": "Flyway or Liquibase for schema migrations",
        "keywords": ["migration", "flyway", "liquibase", "schema", "efcore"],
        "example_dotnet": "dotnet ef migrations add InitialCreate",
        "example_java": "# src/main/resources/db/migration/V1__Initial_Create.sql\nCREATE TABLE products (id BIGINT AUTO_INCREMENT PRIMARY KEY, ...);",
    },
    {
        "id": "ef-005",
        "category": "data",
        "dotnet": "Entity relationships: [ForeignKey] virtual navigation properties",
        "java": "@ManyToOne @OneToMany @JoinColumn @MappedBy JPA relationships",
        "keywords": ["foreignkey", "navigation", "manytone", "onetomany", "joincolumn", "mappedby"],
        "example_dotnet": "[ForeignKey(\"CategoryId\")]\npublic virtual Category Category { get; set; }",
        "example_java": "@ManyToOne(fetch = FetchType.LAZY)\n@JoinColumn(name = \"category_id\")\nprivate Category category;",
    },
    # =========================================================
    # ASYNC / AWAIT
    # =========================================================
    {
        "id": "async-001",
        "category": "async",
        "dotnet": "async Task<T> / await pattern",
        "java": "Standard synchronous Java (Spring handles thread pooling) or CompletableFuture",
        "keywords": ["async", "await", "task", "completablefuture", "asynchronous"],
        "example_dotnet": "public async Task<Product> GetByIdAsync(int id) {\n    return await _context.Products.FindAsync(id);\n}",
        "example_java": "public Optional<Product> findById(Long id) {\n    return productRepository.findById(id);\n}",
    },
    {
        "id": "async-002",
        "category": "async",
        "dotnet": "IHostedService / BackgroundService for background tasks",
        "java": "@Scheduled methods or CommandLineRunner for background tasks",
        "keywords": ["ihostedservice", "backgroundservice", "scheduled", "background", "timer"],
        "example_dotnet": "public class TimedService : BackgroundService {\n    protected override async Task ExecuteAsync(CancellationToken ct) { }\n}",
        "example_java": "@Component\npublic class TimedTask {\n    @Scheduled(fixedDelay = 5000)\n    public void execute() { }\n}",
    },
    # =========================================================
    # CONFIGURATION
    # =========================================================
    {
        "id": "cfg-001",
        "category": "config",
        "dotnet": "appsettings.json configuration",
        "java": "application.yml (Spring Boot default config file)",
        "keywords": ["appsettings", "json", "configuration", "application.yml", "yaml"],
        "example_dotnet": "{\n  \"ConnectionStrings\": { \"Default\": \"...\" },\n  \"Logging\": { \"LogLevel\": { \"Default\": \"Info\" } }\n}",
        "example_java": "spring:\n  datasource:\n    url: jdbc:postgresql://localhost:5432/mydb\nlogging:\n  level:\n    root: INFO",
    },
    {
        "id": "cfg-002",
        "category": "config",
        "dotnet": "IOptions<T> / IConfiguration strongly-typed config binding",
        "java": "@ConfigurationProperties(prefix = \"app\") bound to a POJO",
        "keywords": ["ioptions", "iconfiguration", "configurationproperties", "binding"],
        "example_dotnet": "public class JwtSettings { public string Secret { get; set; } }",
        "example_java": "@ConfigurationProperties(prefix = \"app.jwt\")\n@Component\npublic class JwtSettings {\n    private String secret;\n}",
    },
    {
        "id": "cfg-003",
        "category": "config",
        "dotnet": "Program.cs / Startup.cs - service registration and middleware pipeline",
        "java": "@SpringBootApplication main class + @Configuration @Bean definitions",
        "keywords": ["program", "startup", "configureservices", "configure", "springbootapplication", "configuration", "bean"],
        "example_dotnet": "builder.Services.AddControllers();\napp.UseAuthentication();\napp.MapControllers();",
        "example_java": "@SpringBootApplication\npublic class Application {\n    public static void main(String[] args) {\n        SpringApplication.run(Application.class, args);\n    }\n}",
    },
    # =========================================================
    # MIDDLEWARE → FILTERS / INTERCEPTORS
    # =========================================================
    {
        "id": "mw-001",
        "category": "middleware",
        "dotnet": "ASP.NET Core Middleware (IMiddleware / RequestDelegate pipeline)",
        "java": "Spring OncePerRequestFilter or HandlerInterceptor",
        "keywords": ["middleware", "imiddleware", "requestdelegate", "filter", "interceptor", "onceperrequestfilter"],
        "example_dotnet": "public class LoggingMiddleware : IMiddleware {\n    public async Task InvokeAsync(HttpContext ctx, RequestDelegate next) { }\n}",
        "example_java": "@Component\npublic class LoggingFilter extends OncePerRequestFilter {\n    @Override\n    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ... { }\n}",
    },
    {
        "id": "mw-002",
        "category": "middleware",
        "dotnet": "Global exception handling with UseExceptionHandler",
        "java": "@ControllerAdvice + @ExceptionHandler global exception handling",
        "keywords": ["exceptionhandler", "useexceptionhandler", "controlleradvice", "globalexception"],
        "example_dotnet": "app.UseExceptionHandler(\"/error\");",
        "example_java": "@RestControllerAdvice\npublic class GlobalExceptionHandler {\n    @ExceptionHandler(ResourceNotFoundException.class)\n    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {\n        return ResponseEntity.status(404).body(new ErrorResponse(ex.getMessage()));\n    }\n}",
    },
    # =========================================================
    # MODELS / DTOs
    # =========================================================
    {
        "id": "dto-001",
        "category": "model",
        "dotnet": "Plain C# class / record used as DTO",
        "java": "Java record (Java 16+) or Lombok @Data @Builder class as DTO",
        "keywords": ["dto", "record", "pojo", "data", "builder", "lombok"],
        "example_dotnet": "public record CreateProductDto(string Name, decimal Price, int CategoryId);",
        "example_java": "// Java record:\npublic record CreateProductDto(String name, BigDecimal price, Long categoryId) {}\n// OR Lombok:\n@Data @Builder\npublic class CreateProductDto {\n    private String name;\n    private BigDecimal price;\n    private Long categoryId;\n}",
    },
    {
        "id": "dto-002",
        "category": "model",
        "dotnet": "AutoMapper for DTO ↔ Entity mapping",
        "java": "MapStruct @Mapper interface for compile-time mapping",
        "keywords": ["automapper", "mapster", "mapstruct", "mapper", "mapping", "dto"],
        "example_dotnet": "_mapper.Map<ProductDto>(product);",
        "example_java": "@Mapper(componentModel = \"spring\")\npublic interface ProductMapper {\n    ProductDto toDto(Product product);\n    Product toEntity(CreateProductDto dto);\n}",
    },
    # =========================================================
    # SECURITY / AUTH
    # =========================================================
    {
        "id": "sec-001",
        "category": "security",
        "dotnet": "JWT Bearer authentication middleware",
        "java": "Spring Security with JWT filter",
        "keywords": ["jwt", "bearer", "authentication", "springsecurity", "jwtfilter"],
        "example_dotnet": "builder.Services.AddAuthentication().AddJwtBearer(opt => { opt.TokenValidationParameters = ...; });",
        "example_java": "@Configuration\npublic class SecurityConfig {\n    @Bean\n    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {\n        return http.csrf(c -> c.disable())\n            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))\n            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)\n            .build();\n    }\n}",
    },
    {
        "id": "sec-002",
        "category": "security",
        "dotnet": "[Authorize] [AllowAnonymous] attributes",
        "java": "@PreAuthorize(\"isAuthenticated()\") @PreAuthorize(\"hasRole('ADMIN')\") / permitAll()",
        "keywords": ["authorize", "allowanonymous", "preauthorize", "hasrole", "security"],
        "example_dotnet": "[Authorize(Roles = \"Admin\")]\n[HttpDelete(\"{id}\")]",
        "example_java": "@PreAuthorize(\"hasRole('ADMIN')\")\n@DeleteMapping(\"/{id}\")",
    },
    # =========================================================
    # LOGGING
    # =========================================================
    {
        "id": "log-001",
        "category": "logging",
        "dotnet": "ILogger<T> injected via DI, Serilog / NLog sinks",
        "java": "SLF4J + Logback (Spring Boot default), @Slf4j Lombok annotation",
        "keywords": ["ilogger", "logger", "serilog", "nlog", "slf4j", "logback", "log4j"],
        "example_dotnet": "private readonly ILogger<ProductService> _logger;\n_logger.LogInformation(\"Fetching product {Id}\", id);",
        "example_java": "@Slf4j // Lombok\npublic class ProductService {\n    log.info(\"Fetching product {}\", id);\n}",
    },
    # =========================================================
    # CACHING
    # =========================================================
    {
        "id": "cache-001",
        "category": "caching",
        "dotnet": "IMemoryCache / IDistributedCache (Redis)",
        "java": "@Cacheable @CacheEvict Spring Cache abstraction (Caffeine / Redis backend)",
        "keywords": ["memorycache", "distributedcache", "redis", "cacheable", "cacheevict", "caching"],
        "example_dotnet": "_cache.GetOrCreate(\"products\", entry => {\n    entry.SlidingExpiration = TimeSpan.FromMinutes(5);\n    return _repo.GetAll();\n});",
        "example_java": "@Cacheable(value = \"products\", key = \"#id\")\npublic ProductDto getProduct(Long id) { ... }",
    },
    # =========================================================
    # EVENTS / MEDIATOR PATTERN
    # =========================================================
    {
        "id": "event-001",
        "category": "events",
        "dotnet": "MediatR IRequest / IRequestHandler / INotification",
        "java": "Spring ApplicationEventPublisher + @EventListener",
        "keywords": ["mediatr", "irequest", "inotification", "handler", "eventpublisher", "eventlistener"],
        "example_dotnet": "await _mediator.Publish(new ProductCreatedEvent(product));",
        "example_java": "applicationEventPublisher.publishEvent(new ProductCreatedEvent(this, product));\n\n@EventListener\npublic void onProductCreated(ProductCreatedEvent event) { }",
    },
    # =========================================================
    # VALIDATION
    # =========================================================
    {
        "id": "val-001",
        "category": "validation",
        "dotnet": "FluentValidation RuleFor().NotEmpty().MaximumLength()",
        "java": "Spring @Valid + Bean Validation annotations (@NotBlank @Max @Pattern)",
        "keywords": ["fluentvalidation", "rulefor", "notempty", "valid", "notblank", "constraint"],
        "example_dotnet": "RuleFor(x => x.Name).NotEmpty().MaximumLength(255);",
        "example_java": "@NotBlank(message = \"Name is required\")\n@Size(max = 255)\nprivate String name;",
    },
    # =========================================================
    # LINQ → STREAMS
    # =========================================================
    {
        "id": "linq-001",
        "category": "linq",
        "dotnet": "LINQ .Where() .Select() .FirstOrDefault() .Any() .Count()",
        "java": "Java Streams .filter() .map() .findFirst() .anyMatch() .count()",
        "keywords": ["linq", "where", "select", "firstordefault", "any", "count", "stream", "filter", "map"],
        "example_dotnet": "var active = products.Where(p => p.IsActive).Select(p => p.Name).ToList();",
        "example_java": "List<String> active = products.stream()\n    .filter(Product::isActive)\n    .map(Product::getName)\n    .collect(Collectors.toList());",
    },
    {
        "id": "linq-002",
        "category": "linq",
        "dotnet": "LINQ .GroupBy() .OrderBy() .Distinct()",
        "java": "Java Streams .collect(groupingBy()) .sorted() .distinct()",
        "keywords": ["groupby", "orderby", "distinct", "groupingby", "sorted"],
        "example_dotnet": "products.GroupBy(p => p.CategoryId).ToDictionary(g => g.Key, g => g.ToList());",
        "example_java": "Map<Long, List<Product>> byCategory = products.stream()\n    .collect(Collectors.groupingBy(Product::getCategoryId));",
    },
    # =========================================================
    # PROPERTY PATTERNS
    # =========================================================
    {
        "id": "prop-001",
        "category": "model",
        "dotnet": "C# auto-properties { get; set; } / { get; init; }",
        "java": "Lombok @Data (generates getters/setters) or @Value (immutable) or Java record",
        "keywords": ["property", "getter", "setter", "lombok", "data", "getset"],
        "example_dotnet": "public string Name { get; set; }\npublic int Price { get; init; }",
        "example_java": "@Data // generates all getters, setters, equals, hashCode, toString\npublic class Product {\n    private String name;\n    private BigDecimal price;\n}",
    },
    # =========================================================
    # PAGINATION
    # =========================================================
    {
        "id": "page-001",
        "category": "data",
        "dotnet": "Manual pagination with Skip().Take()",
        "java": "Pageable + Page<T> with Spring Data",
        "keywords": ["pagination", "skip", "take", "pageable", "page", "pagesize"],
        "example_dotnet": "var page = query.Skip((pageNum - 1) * pageSize).Take(pageSize).ToList();",
        "example_java": "Page<Product> page = productRepository.findAll(PageRequest.of(pageNum, pageSize));\n\n// Controller:\n@GetMapping\npublic Page<ProductDto> list(@PageableDefault(size = 20) Pageable pageable) { }",
    },
    # =========================================================
    # TRANSACTIONS
    # =========================================================
    {
        "id": "tx-001",
        "category": "data",
        "dotnet": "using var transaction = await _context.Database.BeginTransactionAsync()",
        "java": "@Transactional annotation on service methods",
        "keywords": ["transaction", "begintransaction", "transactional", "rollback", "commit"],
        "example_dotnet": "using var tx = await _context.Database.BeginTransactionAsync();\ntry { ... await tx.CommitAsync(); } catch { await tx.RollbackAsync(); }",
        "example_java": "@Transactional\npublic void transferFunds(Long from, Long to, BigDecimal amount) {\n    // Spring manages begin/commit/rollback automatically\n}",
    },
    # =========================================================
    # TESTING
    # =========================================================
    {
        "id": "test-001",
        "category": "testing",
        "dotnet": "xUnit / NUnit with Moq for mocking",
        "java": "JUnit 5 with Mockito (@ExtendWith(MockitoExtension.class) @Mock @InjectMocks)",
        "keywords": ["xunit", "nunit", "moq", "junit", "mockito", "mock", "test"],
        "example_dotnet": "[Fact]\npublic async Task GetById_ReturnsProduct() {\n    _mockRepo.Setup(r => r.GetByIdAsync(1)).ReturnsAsync(product);\n}",
        "example_java": "@Test\nvoid getById_ReturnsProduct() {\n    when(productRepository.findById(1L)).thenReturn(Optional.of(product));\n    ProductDto result = productService.findById(1L);\n    assertThat(result.name()).isEqualTo(\"Test\");\n}",
    },
    {
        "id": "test-002",
        "category": "testing",
        "dotnet": "WebApplicationFactory for integration tests",
        "java": "@SpringBootTest + @AutoConfigureMockMvc with MockMvc",
        "keywords": ["webapplicationfactory", "integrationtest", "springboottest", "mockmvc"],
        "example_dotnet": "var factory = new WebApplicationFactory<Program>();\nvar client = factory.CreateClient();",
        "example_java": "@SpringBootTest\n@AutoConfigureMockMvc\nclass ProductControllerTest {\n    @Autowired MockMvc mockMvc;\n    @Test\n    void shouldReturnProducts() throws Exception {\n        mockMvc.perform(get(\"/api/products\")).andExpect(status().isOk());\n    }\n}",
    },
]
