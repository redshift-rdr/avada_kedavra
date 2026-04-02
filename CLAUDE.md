# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Avada Kedavra is an HTTP request replay and fuzzing tool for authorized security testing. It takes captured HTTP requests (JSON), applies payload modifications via YAML config rules, and sends them with multithreaded execution. It features baseline/diff analysis, reflection detection, auto-throttle, and WAF detection.

## Commands

```bash
# Install dependencies
cd avada_kedavra && pip install -r requirements.txt

# Run the tool
python -m avada_kedavra <requests.json> -c <config.yaml>

# Run all tests
cd avada_kedavra && PYTHONPATH=$(pwd)/.. pytest

# Run a single test file
cd avada_kedavra && PYTHONPATH=$(pwd)/.. pytest tests/test_modifier.py

# Run with coverage
cd avada_kedavra && PYTHONPATH=$(pwd)/.. pytest --cov=avada_kedavra --cov-report=term-missing
```

The venv is at `avada_kedavra/venv/`. Tests require `PYTHONPATH` set to the repo root (parent of `avada_kedavra/`). pytest.ini is inside `avada_kedavra/` and configures `testpaths = tests`.

## Architecture

The package lives under `avada_kedavra/` with `__main__.py` as the CLI entry point.

**Data flow:** CLI args + YAML config -> `core/config.py` loads `AppConfig` -> `core/request_parser.py` parses input JSON into `RequestComponents` -> for each rule, `core/filter.py` checks if request matches -> `core/payload_loader.py` loads payloads -> `core/modifier.py` applies payloads to create modified `RequestComponents` -> `network/requester.py` executes requests via threaded workers -> results displayed via `ui/console.py` (Rich) and optionally exported via `ui/exporter.py`.

**Key dataclasses** (in `models/request.py`): `RequestComponents` (parsed HTTP request), `AppConfig` (runtime config), `TaskData` (a single request task with payload and conditions).

**Rule system:** Each YAML rule has optional `filter` (which requests to target), `target` (which parameter to inject into - supports wildcards via `target: "*"` or omitting target), `payloads` (list/file/single), and `conditions` (response matching criteria with `any`/`all` mode).

**Phase 1 features** (CLI flags, not config): `--baseline-mode`, `--diff-analysis`, `--detect-reflection`, `--auto-throttle`, `--waf-detect`. These are implemented in `core/diff_analyzer.py`, `core/reflection_detector.py`, `core/rate_limiter.py`, with baseline data models in `models/baseline.py`.

**Authentication system:** Configured via an `auth:` block in the YAML config. Supports `bearer_token` (login endpoint + JSON token extraction), `session_cookie` (login endpoint + cookie/header extraction), and `api_key` (static key). `core/auth_handler.py` (`AuthHandler`) manages login, token storage, and thread-safe re-authentication on 401. Auth models live in `models/auth.py`. When no auth config is set, 401s pause the scan and prompt the user unless `--continue-on-auth-errors` is passed.

**Display modes:** Default uses Rich Live table with real-time progress. `--no-live` disables the Live table for compatibility (e.g., Windows, piped output) — shows a simple "Scanning..." message and prints progress on Enter keypress (nmap-style).

**Modifier targets:** `method`, `url`, `header` (case-insensitive), `cookie`, `body` (json/form/raw). Wildcard targets expand to all injectable parameters (sniper mode - one param per request).

`avada_kedavra/requester.py` at the package root is a deprecated backward-compat wrapper; the real requester is `avada_kedavra/network/requester.py`.
