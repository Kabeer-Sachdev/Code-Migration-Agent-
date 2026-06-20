"""
Packager - bundles all generated Java files, pom.xml, application.yml,
and test files into a proper Maven project ZIP archive in memory.
"""
import io
import logging
import zipfile
from typing import List

from .converter import JavaFile, MigrationOutput

logger = logging.getLogger(__name__)

_DEFAULT_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>Migrated Application</name>
    <description>Auto-migrated from .NET to Spring Boot 3</description>

    <properties>
        <java.version>21</java.version>
        <mapstruct.version>1.6.0</mapstruct.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-cache</artifactId>
        </dependency>

        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <!-- MapStruct -->
        <dependency>
            <groupId>org.mapstruct</groupId>
            <artifactId>mapstruct</artifactId>
            <version>${mapstruct.version}</version>
        </dependency>

        <!-- Database -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- JWT -->
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-api</artifactId>
            <version>0.12.6</version>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-impl</artifactId>
            <version>0.12.6</version>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-jackson</artifactId>
            <version>0.12.6</version>
            <scope>runtime</scope>
        </dependency>

        <!-- OpenAPI / Swagger -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.6.0</version>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.mapstruct</groupId>
                            <artifactId>mapstruct-processor</artifactId>
                            <version>${mapstruct.version}</version>
                        </path>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""

_DEFAULT_APP_YML = """\
spring:
  application:
    name: migrated-app
  datasource:
    url: jdbc:h2:mem:migrationdb;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE
    driver-class-name: org.h2.Driver
    username: sa
    password:
  h2:
    console:
      enabled: true
      path: /h2-console
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: true
    properties:
      hibernate:
        format_sql: true
  cache:
    type: caffeine
    caffeine:
      spec: maximumSize=500,expireAfterWrite=5m

server:
  port: 8080

logging:
  level:
    root: INFO
    com.example.app: DEBUG

springdoc:
  api-docs:
    path: /api-docs
  swagger-ui:
    path: /swagger-ui.html

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
"""

_MAIN_CLASS_TEMPLATE = """\
package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Application entry point - auto-generated by the Migration Agent.
 */
@SpringBootApplication
@EnableCaching
@EnableScheduling
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
"""


def build_zip(output: MigrationOutput) -> bytes:
    """
    Create an in-memory ZIP with the full Maven project structure.
    Returns the raw bytes of the ZIP file.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # pom.xml
        pom = output.pom_xml.strip() or _DEFAULT_POM.strip()
        zf.writestr("app/pom.xml", pom)

        # application.yml
        app_yml = output.application_yml.strip() or _DEFAULT_APP_YML.strip()
        zf.writestr("app/src/main/resources/application.yml", app_yml)

        # Main Application.java (ensure it always exists)
        has_main = any("Application.java" in f.filename for f in output.java_files)
        if not has_main:
            zf.writestr(
                "app/src/main/java/com/example/app/Application.java",
                _MAIN_CLASS_TEMPLATE,
            )

        # Java source files
        for jf in output.java_files:
            path = f"app/{jf.filename}" if not jf.filename.startswith("app/") else jf.filename
            zf.writestr(path, jf.content)
            logger.debug("Packaged: %s", path)

        # Test files
        for tf in output.test_files:
            path = f"app/{tf.filename}" if not tf.filename.startswith("app/") else tf.filename
            zf.writestr(path, tf.content)
            logger.debug("Packaged test: %s", path)

        # .gitignore
        zf.writestr("app/.gitignore", "target/\n*.class\n.idea/\n*.iml\n")

        # README stub
        readme = (
            "# Migrated Spring Boot Application\n\n"
            "Auto-migrated from .NET by the Migration Agent.\n\n"
            "## Run\n```bash\ncd app\nmvn spring-boot:run\n```\n\n"
            "## Swagger UI\nhttp://localhost:8080/swagger-ui.html\n"
        )
        zf.writestr("app/README.md", readme)

    buf.seek(0)
    logger.info(
        "ZIP built: %d java files, %d test files, %d bytes",
        len(output.java_files),
        len(output.test_files),
        buf.getbuffer().nbytes,
    )
    return buf.getvalue()
