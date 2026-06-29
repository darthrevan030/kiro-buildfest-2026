# Requirements Document

## Introduction

Cloud Janitor is a production-grade, AI-native infrastructure remediation tool. This requirements document specifies the changes needed to make the package pip-installable and production-ready for distribution on PyPI. The project currently has complete core logic (17 agents, MCP server, property-based tests, Streamlit dashboard) but lacks packaging, CLI entry points, CI/CD, proper logging, and resilient LLM integration needed for a distributable package.

## Glossary

- **CLI**: The command-line interface executable installed by `pip install cloud-janitor`
- **Build_System**: The pyproject.toml [build-system] configuration that enables `pip install` and wheel generation
- **Package_Layout**: The directory structure under `src/cloud_janitor/` that Python packaging tools discover as importable modules
- **CI_Pipeline**: The GitHub Actions workflow that runs lint, type checking, tests, build verification, and publishing
- **LLM_Client**: The `core/llm_client.py` module that provides OpenAI-compatible client configuration for all AI agents
- **Dashboard**: The Streamlit-based web UI for visualizing scan results and approvals
- **MCP_Server**: The FastMCP-based server exposing 10 infrastructure tools via stdio transport
- **Provider**: A backend implementation (AWS, GCP, Azure, Fixture) supplying cloud resource data

## Requirements

### Requirement 1: CLI Entry Point

**User Story:** As a user who has pip-installed cloud-janitor, I want a `cloud-janitor` command available in my terminal, so that I can run scans, approve remediations, trigger rollbacks, launch the dashboard, and start the MCP server without invoking Python scripts directly.

#### Acceptance Criteria

1. WHEN a user runs `cloud-janitor scan`, THE CLI SHALL execute the full audit pipeline (FinOps + SecOps + Remediation Architect), print a summary line indicating the number of findings produced, and exit with code 0
2. WHEN a user runs `cloud-janitor scan --finops`, THE CLI SHALL execute only the FinOps auditor agent, print a summary line indicating the number of findings produced, and exit with code 0
3. WHEN a user runs `cloud-janitor scan --secops`, THE CLI SHALL execute only the SecOps guard agent, print a summary line indicating the number of findings produced, and exit with code 0
4. WHEN a user runs `cloud-janitor approve <id>`, THE CLI SHALL instantiate `Orchestrator` and call `orchestrator.approve(command="APPROVE <id>")`, print a confirmation message if `ApprovalResult.success` is True, and exit with code 0
5. WHEN a user runs `cloud-janitor rollback <id>`, THE CLI SHALL instantiate `Orchestrator` and call `orchestrator.rollback(command="ROLLBACK <id>")`, print a confirmation message if `RollbackResult.success` is True or `needs_confirmation` is True, and exit with code 0
6. WHEN a user runs `cloud-janitor dashboard`, THE CLI SHALL launch the Streamlit dashboard server and print the local URL where the dashboard is accessible
7. WHEN a user runs `cloud-janitor mcp`, THE CLI SHALL start the MCP server on stdio transport
8. WHEN a user runs `cloud-janitor --version`, THE CLI SHALL print the installed package version to stdout and exit with code 0
9. IF an unknown subcommand is provided, THEN THE CLI SHALL print a help message listing all available commands and exit with code 1
10. IF `cloud-janitor approve <id>` or `cloud-janitor rollback <id>` is invoked with an identifier that does not match any existing remediation, THEN THE CLI SHALL print an error message to stderr indicating the identifier was not found and exit with code 1
11. IF a scan pipeline agent encounters a runtime error, THEN THE CLI SHALL print an error message indicating which agent failed and exit with code 1
12. THE `cloud-janitor scan` command SHALL delegate to the existing `Orchestrator` class (from `cloud_janitor.orchestrator`) rather than reimplementing pipeline sequencing logic in the CLI module

### Requirement 2: Build System Declaration

**User Story:** As a package maintainer, I want a declared build system in pyproject.toml, so that `pip install .` and `pip wheel .` produce valid distributable artifacts.

#### Acceptance Criteria

1. THE Build_System SHALL declare a `[build-system]` table in pyproject.toml containing `build-backend = "hatchling.build"` and a `requires` list that includes `hatchling`
2. WHEN `pip install .` is executed in the project root, THE Build_System SHALL produce an installation where the package is importable via `import cloud_janitor` and all console_scripts entry points defined in `[project.scripts]` are available as executable commands on PATH
3. WHEN `pip wheel .` is executed in the project root, THE Build_System SHALL produce a `.whl` file that passes `twine check` with no errors and contains the project metadata (name, version, requires-python) matching pyproject.toml
4. IF `[project.scripts]` declares one or more entry points, THEN THE Build_System SHALL register each declared entry point such that invoking the command name with `--help` exits with code 0; IF any declared entry point fails to respond to `--help` with exit code 0, THEN the build verification step SHALL be considered failed

### Requirement 3: Package Structure Configuration

**User Story:** As a developer importing cloud-janitor in another project, I want all modules discoverable under `cloud_janitor.*`, so that imports work predictably after pip installation.

#### Acceptance Criteria

1. THE Package_Layout SHALL organize all source code under `src/cloud_janitor/` following the src-layout convention, with an `__init__.py` file present in `src/cloud_janitor/` and in each subpackage directory
2. THE Package_Layout SHALL expose `agents`, `core`, `mcp_server`, and `orchestrator` as subpackages of `cloud_janitor`, each containing an `__init__.py` so that `import cloud_janitor.agents`, `import cloud_janitor.core`, `import cloud_janitor.mcp_server`, and `import cloud_janitor.orchestrator` succeed without raising ImportError
3. WHEN a user runs `from cloud_janitor import __version__`, THE Package_Layout SHALL return a version string that conforms to PEP 440 and matches the version declared in `pyproject.toml`
4. THE Package_Layout SHALL include a `py.typed` marker file in `src/cloud_janitor/` so type checkers recognize exported annotations
5. WHEN the package is installed via pip, THE Package_Layout SHALL make the `cloud-janitor` CLI command available as a console-script entry point declared in `pyproject.toml` `[project.scripts]`; THE CLI command SHALL require proper entry point configuration to function, so that running `cloud-janitor --help` in a shell exits with code 0 and displays usage information
6. IF a user attempts to import a subpackage that does not exist under `cloud_janitor` (e.g., `import cloud_janitor.nonexistent`), THEN THE Package_Layout SHALL raise a standard `ModuleNotFoundError`

### Requirement 4: Dependency Hygiene

**User Story:** As a user installing cloud-janitor, I want only necessary production dependencies installed, so that my environment stays lean and test-only libraries are excluded.

#### Acceptance Criteria

1. THE Build_System SHALL exclude `anthropic` from the `[project.dependencies]` list
2. THE Build_System SHALL move `hypothesis` from `[project.dependencies]` to the `[dependency-groups]` dev group
3. THE Build_System SHALL add `packaging` to the `[project.dependencies]` list
4. THE Build_System SHALL declare `streamlit` as an optional dependency under `[project.optional-dependencies]` in a group named `dashboard`
5. WHEN a user runs `pip install cloud-janitor`, THE Build_System SHALL install only the packages listed in `[project.dependencies]` without `anthropic`, `hypothesis`, or `streamlit`
6. WHEN a user runs `pip install cloud-janitor[dashboard]`, THE Build_System SHALL install all packages from `[project.dependencies]` plus `streamlit`
7. THE Build_System SHALL add `click` to the `[project.dependencies]` list
8. THE Build_System SHALL add `ruff` and `mypy` to the `[dependency-groups]` dev group alongside existing dev dependencies (`moto`, `pytest`)
9. WHEN a user runs `pip install cloud-janitor`, THE Build_System SHALL NOT install any packages listed exclusively in `[dependency-groups]` dev or `[project.optional-dependencies]`

### Requirement 5: GitHub Actions CI Pipeline

**User Story:** As a maintainer, I want automated CI on every push and pull request, so that code quality, type safety, test correctness, and package buildability are verified before merging.

#### Acceptance Criteria

1. WHEN code is pushed to any branch or a pull request is opened or synchronized, THE CI_Pipeline SHALL run `ruff check` on the entire codebase and exit with a non-zero status if any violations are found
2. WHEN code is pushed to any branch or a pull request is opened or synchronized, THE CI_Pipeline SHALL run `mypy` type checking on the `src/` directory and exit with a non-zero status if any type errors are found
3. WHEN code is pushed to any branch or a pull request is opened or synchronized, THE CI_Pipeline SHALL run `pytest` across a matrix of Python 3.12 and Python 3.13, reporting results independently for each version
4. WHEN code is pushed to any branch or a pull request is opened or synchronized, THE CI_Pipeline SHALL build the package wheel and verify it installs successfully by confirming the install command exits with code 0 and the package is importable
5. WHEN a Git tag matching `v*` is pushed AND all lint, type-check, test, and build steps have passed, THEN THE CI_Pipeline SHALL publish the package to PyPI using trusted publishing
6. IF any lint, type-check, or test step fails, THEN THE CI_Pipeline SHALL mark the workflow run as failed and set the corresponding GitHub commit status check to failure
7. IF any lint, type-check, or test step fails, THEN THE CI_Pipeline SHALL prevent subsequent dependent steps from executing

### Requirement 6: README Accuracy

**User Story:** As a prospective user reading the README, I want accurate documentation of the project's capabilities, so that I can trust the installation instructions and feature descriptions.

#### Acceptance Criteria

1. THE README SHALL describe the AWS provider as a complete implementation in both the "Running Modes" section and the "Provider backends" table, stating that it queries live AWS infrastructure via boto3 (not a stub or placeholder)
2. THE README SHALL include `pip install cloud-janitor` as the primary installation method in the Quick Start section
3. THE README SHALL document all CLI commands (`scan`, `approve`, `rollback`, `dashboard`, `mcp`) with their invocation syntax (e.g., `cloud-janitor scan`, `cloud-janitor approve <resource-id>`) and a one-sentence description of each command's purpose
4. THE README SHALL document the optional dashboard dependency: `pip install cloud-janitor[dashboard]`
5. THE README SHALL replace `pip install -r requirements.txt` in the Quick Start section with `pip install cloud-janitor`, retaining no references to `requirements.txt` as a user-facing installation step
6. THE README SHALL list the AWS provider status as "Complete" (not "Stub") in the Provider backends table under the MCP Server section

### Requirement 7: Structured Logging

**User Story:** As an operator running cloud-janitor in production, I want structured log output with configurable levels, so that I can filter, aggregate, and debug pipeline runs without parsing ad-hoc print statements.

#### Acceptance Criteria

1. THE LLM_Client SHALL use Python's `logging` module instead of `print()` for all diagnostic output
2. WHEN the `JANITOR_LOG_LEVEL` environment variable is set to a valid level (DEBUG, INFO, WARNING, ERROR), THE CLI SHALL configure the root logger to the specified level using case-insensitive matching
3. WHILE no `JANITOR_LOG_LEVEL` is set, THE CLI SHALL default the logging level to INFO
4. THE CLI SHALL format log records as `%(asctime)s %(levelname)s %(name)s %(message)s` with timestamps in ISO 8601 format and emit all log output to stderr
5. WHEN an agent produces diagnostic output, THE agent SHALL log through a module-level logger (e.g., `logging.getLogger(__name__)`) instead of using `print()`; this requirement applies only to newly written or modified code — existing agent `print()` calls that write structured data to `findings_store.json` or output files SHALL NOT be replaced with logging calls
6. IF `JANITOR_LOG_LEVEL` is set to a value not in (DEBUG, INFO, WARNING, ERROR), THEN THE CLI SHALL emit a WARNING-level log message indicating the invalid value and fall back to INFO

### Requirement 8: LLM Call Resilience

**User Story:** As an operator, I want LLM calls to automatically retry on transient failures with exponential backoff, so that a single rate-limit or network error does not abort the entire pipeline.

#### Acceptance Criteria

1. WHEN an LLM API call returns HTTP 429 (rate limited), THE LLM_Client SHALL retry the request up to a maximum of 3 retry attempts (4 total calls including the original request) using exponential backoff
2. WHEN an LLM API call returns HTTP 500, 502, 503, or 504, THE LLM_Client SHALL retry the request up to a maximum of 3 retry attempts (4 total calls including the original request) using exponential backoff
3. WHEN an LLM API call fails due to a network timeout (no response received within 30 seconds), THE LLM_Client SHALL retry the request up to a maximum of 3 retry attempts (4 total calls including the original request) using exponential backoff
4. IF all retry attempts are exhausted, THEN THE LLM_Client SHALL raise an exception to the calling agent that includes the final HTTP status code or error type, the total number of attempts made, and the total elapsed time across all attempts
5. THE LLM_Client SHALL log each retry attempt including the attempt number (e.g., "retry 1 of 3"), the wait duration in seconds before the next attempt, and the error reason (HTTP status code or timeout indication)
6. THE LLM_Client SHALL use a base backoff delay of 1 second with a multiplier of 2 (delays of 1s, 2s, 4s for retries 1, 2, 3 respectively); IF an HTTP 429 response includes a Retry-After header with a value not exceeding 60 seconds, THE LLM_Client SHALL use the Retry-After value as the delay for that retry instead of the calculated exponential backoff
7. IF an HTTP 429 Retry-After header value exceeds 60 seconds, THEN THE LLM_Client SHALL treat the request as non-retriable and immediately raise an exception indicating the rate-limit wait exceeds the maximum allowable delay
8. THE retry logic SHALL be implemented as a manual retry loop (not tenacity) to allow deterministic control over delay calculation and Retry-After header inspection without fighting library-imposed jitter

### Requirement 9: Importable Version

**User Story:** As a developer integrating with cloud-janitor programmatically, I want to access the package version at runtime, so that I can include version information in logs, diagnostics, and compatibility checks.

#### Acceptance Criteria

1. WHEN a user executes `import cloud_janitor; print(cloud_janitor.__version__)`, THE Package_Layout SHALL return a version string of type `str` that exactly matches the `version` value defined in pyproject.toml with no leading or trailing whitespace
2. THE Package_Layout SHALL use `importlib.metadata` to dynamically read the version from installed package metadata so that pyproject.toml remains the single source of truth
3. IF `importlib.metadata` raises `PackageNotFoundError` (e.g., the package is run from source without being installed via pip install or pip install -e), THEN THE Package_Layout SHALL set `__version__` to the string "0.0.0-dev"
4. THE Package_Layout SHALL expose `__version__` as a module-level attribute that conforms to PEP 440 version format
5. THE test suite SHALL include a test that mocks `importlib.metadata.version` to raise `PackageNotFoundError` and verifies `cloud_janitor.__version__` returns "0.0.0-dev"

### Requirement 10: Type Annotation Marker

**User Story:** As a developer using cloud-janitor as a library dependency, I want type checkers (mypy, pyright) to recognize the package's type annotations, so that I get static analysis support for cloud-janitor's public API.

#### Acceptance Criteria

1. THE Package_Layout SHALL include a `py.typed` marker file at `src/cloud_janitor/py.typed` that is an empty (0-byte) file
2. THE Build_Configuration SHALL declare `py.typed` as package data so that it is included in both sdist and wheel distributions
3. WHEN mypy or pyright resolves imports from `cloud_janitor`, THE type checker SHALL report no "missing library stubs" or "not typed" diagnostic for the package, confirming PEP 561 compliance; verification SHALL confirm both successful import resolution AND the presence of the `py.typed` marker file
4. IF the `py.typed` marker file is absent from the installed package directory, THEN THE type checker SHALL report a "missing type stubs" diagnostic, confirming the marker is required for typed recognition

### Requirement 11: Stub Provider Warnings

**User Story:** As a user who configures a GCP or Azure backend, I want a clear warning at configuration time, so that I understand the provider is not yet implemented rather than encountering a silent failure.

#### Acceptance Criteria

1. WHEN the `JANITOR_BACKEND` environment variable is set to `gcp` and the GCPProvider is instantiated, THE Provider SHALL emit a WARNING-level log message stating GCP support is not yet implemented
2. WHEN the `JANITOR_BACKEND` environment variable is set to `azure` and the AzureProvider is instantiated, THE Provider SHALL emit a WARNING-level log message stating Azure support is not yet implemented
3. IF a stub provider method is called, THEN THE Provider SHALL raise `NotImplementedError` with a message identifying the provider name and the method called
4. AFTER the warning is emitted, THE Provider SHALL remain instantiable and usable for any non-stub operations (such as introspection or configuration validation) without raising an exception

### Requirement 12: Optional Dashboard Dependency

**User Story:** As a user who only needs CLI/MCP functionality, I want to install cloud-janitor without the 100MB+ Streamlit dependency, so that my environment stays minimal.

#### Acceptance Criteria

1. WHEN `pip install cloud-janitor` is run without extras, THE Build_System SHALL not install `streamlit` or its transitive dependencies
2. IF the `dashboard` extra is not installed, THEN WHEN a user runs `cloud-janitor dashboard`, THE CLI SHALL print an error message to stderr indicating that the dashboard extra is required and instructing the user to install with `pip install cloud-janitor[dashboard]`, and exit with status code 1
3. WHEN `pip install cloud-janitor[dashboard]` is run, THE Build_System SHALL install `streamlit` and THE CLI SHALL accept the `cloud-janitor dashboard` command without raising an import error
4. THE CLI module SHALL NOT import `streamlit` at module level in any context (production, development, or testing); the import SHALL be deferred to inside the `dashboard` command handler using a `try/except ImportError` guard, so that all other CLI commands remain functional when the `dashboard` extra is not installed
5. WHEN `pip install cloud-janitor` is run without extras, THE Build_System SHALL produce a total installed package size at least 50MB smaller than when installed with the `[dashboard]` extra

## Implementation Order

### Batch 1 (First)

- Requirement 1: CLI Entry Point
- Requirement 2: Build System Declaration
- Requirement 7: Structured Logging
- Requirement 8: LLM Call Resilience
- Requirement 9: Importable Version
- Requirement 11: Stub Provider Warnings
- Requirement 12: Optional Dashboard Dependency

### Batch 2 (After Batch 1 Verified)

- Requirement 6: README Accuracy

### Batch 3 (Last)

- Requirement 4: Dependency Hygiene
- Requirement 3: Package Structure Configuration
- Requirement 5: GitHub Actions CI Pipeline
- Requirement 10: Type Annotation Marker
