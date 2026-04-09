# Avada Kedavra Config YAML Guide

This guide covers how to write configuration YAML files for Avada Kedavra. A config file defines **rules** that control what payloads are injected into which parts of which requests, and what to look for in the responses.

---

## Basic Structure

```yaml
# Global settings (all optional)
threads: 5
delay: 0.0
timeout: 10
verify_ssl: true
allow_redirects: true
proxy: "http://127.0.0.1:8080"

# Rules (required - at least one rule)
rules:
  - payloads:
      type: list
      source:
        - "test"

# Authentication (optional)
auth:
  type: bearer_token
  login_url: "https://example.com/login"
  credentials:
    username: "admin"
    password: "password"
```

---

## Rules

Rules are the core of the config. Each rule is a list item under `rules:`.

### Rule Keys

| Key | Required? | Description |
|-----|-----------|-------------|
| `payloads` | Optional | What values to inject. If omitted, the original request is replayed unmodified. |
| `target` | Optional | Where to inject the payload. If omitted, payloads are injected into **every** parameter in the request (wildcard/sniper mode). Ignored when `payloads` is also omitted. |
| `filter` | Optional | Which requests to apply this rule to. If omitted, the rule applies to **all** requests in the capture file. |
| `conditions` | Optional | What to look for in responses. If omitted, all responses are shown regardless. |

**All rule keys are optional**, but a rule must have at least one key to be useful.

### Minimal Rules

**Replay with payloads** -- injects every payload into every parameter of every request:

```yaml
rules:
  - payloads:
      type: list
      source:
        - "test_value"
```

**Replay without payloads** -- sends original requests unmodified and checks conditions:

```yaml
rules:
  - conditions:
      string_in_headers: "Strict-Transport-Security"
```

This is useful for auditing responses (security headers, status codes, content checks) without modifying the requests at all.

---

## Payloads

Payloads define the values to inject. Every payload config needs a `type` and a `source`.

### Inline List

```yaml
payloads:
  type: list
  source:
    - "payload_one"
    - "payload_two"
    - "' OR '1'='1"
```

### From File

Reads one payload per line from a text file:

```yaml
payloads:
  type: file
  source: "wordlists/sqli.txt"
```

### Single Value

Shorthand for a one-item list:

```yaml
payloads:
  type: single
  source: "<script>alert(1)</script>"
```

---

## Target

The target controls which part of the request gets the payload injected.

### Target Types

| Type | `name` required? | Description |
|------|-------------------|-------------|
| `method` | No | Replaces the HTTP method (GET, POST, etc.) |
| `url` | Yes | Replaces a URL query parameter value |
| `header` | Yes | Replaces a request header value (case-insensitive lookup) |
| `cookie` | Yes | Replaces a cookie value |
| `body` | Yes | Replaces a body parameter value (JSON or form) |

### Examples

**Replace a specific URL parameter:**
```yaml
target:
  type: url
  name: q
```

**Replace a specific body field:**
```yaml
target:
  type: body
  name: email
```

**Replace a header value:**
```yaml
target:
  type: header
  name: X-Forwarded-For
```

**Replace a cookie:**
```yaml
target:
  type: cookie
  name: session_id
```

**Enumerate HTTP methods:**
```yaml
target:
  type: method
payloads:
  type: list
  source: [GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD]
```

### Wildcard Targets

When no target is specified, or when you use `"*"`, the rule applies to **all injectable parameters** in the request (URL params, headers, cookies, body fields). Each parameter gets its own request with the payload -- this is sniper mode, one parameter modified per request.

All three of these are equivalent:

```yaml
# Option 1: Omit target entirely
rules:
  - payloads:
      type: list
      source: ["test"]

# Option 2: Explicit wildcard string
rules:
  - target: "*"
    payloads:
      type: list
      source: ["test"]

# Option 3: Wildcard with type filter (only body params)
rules:
  - target:
      type: body
      name: "*"
    payloads:
      type: list
      source: ["test"]
```

The third form lets you wildcard within a specific type -- e.g. inject into all body parameters but not headers or cookies.

---

## Filter

Filters control which requests from the capture file a rule applies to. If no filter is set, the rule applies to all requests. All filter conditions must match (AND logic).

### Filter Keys

| Key | Description |
|-----|-------------|
| `method` | Match HTTP method. String or list: `"GET"` or `[GET, POST]` |
| `url_contains` | Match if the full URL contains this substring |
| `url_path_contains` | Match if the URL path contains this substring |
| `header_present` | Match if request has this header (case-insensitive) |
| `header_value_contains` | Match if header exists and its value contains a substring |

### Examples

**Only POST requests:**
```yaml
filter:
  method: POST
```

**Only requests to API endpoints:**
```yaml
filter:
  url_contains: /api/
```

**Only requests with a specific path and method:**
```yaml
filter:
  method: [GET, POST]
  url_path_contains: /search
```

**Only requests that have a JSON content type:**
```yaml
filter:
  header_value_contains:
    Content-Type: "application/json"
```

**Only requests that have an Authorization header:**
```yaml
filter:
  header_present: Authorization
```

---

## Conditions

Conditions check response data and flag matches in the output. Without conditions, every response is shown. With conditions, only responses that match are highlighted.

### Match Mode

Controls how multiple conditions combine:

- `match_mode: "any"` (default) -- flag the response if **any** condition matches (OR logic)
- `match_mode: "all"` -- only flag if **every** condition matches (AND logic)

### Available Conditions

| Key | Value type | Description |
|-----|------------|-------------|
| `status_code` | int or list | Match specific HTTP status code(s) |
| `string_in_body` | string | Response body contains this string |
| `string_in_headers` | string | Response headers contain this string |
| `regex_in_body` | string | Regex pattern matches in response body |
| `regex_in_headers` | string | Regex pattern matches in response headers |
| `content_length_gt` | int | Response size > N bytes |
| `content_length_lt` | int | Response size < N bytes |
| `content_length_eq` | int | Response size == N bytes |
| `response_time_gt` | float | Response took longer than N seconds |
| `response_time_lt` | float | Response was faster than N seconds |

### Examples

**Flag server errors:**
```yaml
conditions:
  status_code: 500
```

**Flag successful responses with specific content:**
```yaml
conditions:
  match_mode: "all"
  status_code: [200, 201]
  string_in_body: "Welcome"
```

**Flag SQL errors using regex (OR mode):**
```yaml
conditions:
  match_mode: "any"
  regex_in_body: "sql syntax|ORA-[0-9]+|SQLSTATE|unclosed quotation"
  status_code: 500
```

**Flag slow responses (time-based blind injection):**
```yaml
conditions:
  response_time_gt: 4.5
```

**Check for a security header:**
```yaml
conditions:
  string_in_headers: "Strict-Transport-Security"
```

---

## Global Settings

These go at the top level of the YAML file, outside `rules:`. All are optional and have sensible defaults. CLI arguments override these when provided.

| Key | Default | Description |
|-----|---------|-------------|
| `threads` | 5 | Number of concurrent request threads |
| `delay` | 0.0 | Delay in seconds between requests |
| `timeout` | 10 | Request timeout in seconds |
| `verify_ssl` | true | Verify SSL certificates |
| `allow_redirects` | true | Follow HTTP redirects |
| `proxy` | none | Proxy URL (e.g. `http://127.0.0.1:8080` for Burp) |
| `continue_on_auth_errors` | false | Don't pause on 401s when no auth is configured |

---

## Authentication

The `auth:` block configures automatic authentication and re-authentication on 401 responses.

### Auth Types

#### Bearer Token

Logs in to an endpoint, extracts a token from the response, and injects it as a header.

```yaml
auth:
  type: bearer_token
  login_url: "https://example.com/api/login"
  login_method: POST                    # optional, default: POST
  credentials:
    email: "admin@example.com"
    password: "secret"
  credentials_format: json              # optional: "json" or "form", default: json
  token_location: body                  # optional: "body" or "header", default: body
  token_field: "token"                  # optional, JSON field name, default: token
  inject_as: header                     # optional: "header" or "cookie", default: header
  inject_name: "Authorization"          # optional, header/cookie name, default: Authorization
  inject_prefix: "Bearer "             # optional, prepended to token, default: ""
```

#### Session Cookie

Logs in and extracts a session cookie or header value.

```yaml
auth:
  type: session_cookie
  login_url: "https://example.com/login"
  credentials:
    username: "admin"
    password: "password"
  credentials_format: form
  token_location: header                # extract from response headers
  token_field: "Set-Cookie"             # which header to extract
  inject_as: cookie                     # inject as cookie
  inject_name: "session"
```

#### Static API Key

No login -- injects a fixed key into every request.

```yaml
auth:
  type: api_key
  api_key: "sk-abc123def456"
  inject_as: header
  inject_name: "X-API-Key"
```

### Auth Options

| Key | Required for | Default | Description |
|-----|-------------|---------|-------------|
| `type` | all | -- | `bearer_token`, `session_cookie`, or `api_key` |
| `login_url` | bearer_token, session_cookie | -- | Login endpoint URL |
| `login_method` | -- | POST | HTTP method for login request |
| `credentials` | -- | {} | Key-value pairs sent as login body |
| `credentials_format` | -- | json | `"json"` or `"form"` |
| `token_location` | -- | body | Where to find the token: `"body"` or `"header"` |
| `token_field` | -- | token | JSON field name or header name to extract |
| `inject_as` | -- | header | Inject token as `"header"` or `"cookie"` |
| `inject_name` | -- | Authorization | Name of the header or cookie to inject |
| `inject_prefix` | -- | "" | String prepended to token value (e.g. `"Bearer "`) |
| `api_key` | api_key | -- | The static API key value |
| `max_retries` | -- | 3 | Max re-authentication attempts on 401 |
| `cooldown` | -- | 1.0 | Seconds between re-auth attempts |
| `auth_failure_codes` | -- | [401] | Status codes that trigger re-authentication |

---

## Complete Examples

### 1. SQL Injection -- Wildcard, All Parameters

No filter, no target. Injects into every parameter of every request.

```yaml
rules:
  - payloads:
      type: list
      source:
        - "'"
        - "' OR '1'='1'--"
        - "' UNION SELECT NULL--"
    conditions:
      match_mode: "any"
      regex_in_body: "sql syntax|you have an error|SQLSTATE"
      status_code: 500
```

### 2. XSS on Search Endpoints

Filtered to GET requests on `/search`, targeting the `q` parameter.

```yaml
rules:
  - filter:
      method: GET
      url_path_contains: /search
    target:
      type: url
      name: q
    payloads:
      type: list
      source:
        - "<script>alert(1)</script>"
        - "<img src=x onerror=alert(1)>"
    conditions:
      regex_in_body: "<script>alert|onerror=alert"
```

### 3. Security Header Audit

Replay requests unmodified and check for security headers.

```yaml
rules:
  - conditions:
      string_in_headers: "Strict-Transport-Security"
```

### 4. Time-Based Blind SQL Injection

```yaml
threads: 3
delay: 0.5

rules:
  - payloads:
      type: list
      source:
        - "' AND SLEEP(5)--"
        - "'; WAITFOR DELAY '0:0:5'--"
        - "'; SELECT pg_sleep(5)--"
    conditions:
      response_time_gt: 4.5
```

### 5. Authenticated API Fuzzing via Burp Proxy

```yaml
threads: 10
delay: 0.1
proxy: "http://127.0.0.1:8080"
verify_ssl: false

auth:
  type: bearer_token
  login_url: "https://api.example.com/auth/login"
  credentials:
    email: "tester@example.com"
    password: "T3st!ng123"
  token_field: "access_token"
  inject_prefix: "Bearer "

rules:
  - filter:
      method: POST
      url_contains: /api/
    payloads:
      type: file
      source: "wordlists/api_fuzz.txt"
    conditions:
      match_mode: "any"
      status_code: [200, 500]
      content_length_gt: 500
```

### 6. Method Enumeration on API Routes

```yaml
rules:
  - filter:
      url_contains: /api/
    target:
      type: method
    payloads:
      type: list
      source: [GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD]
    conditions:
      status_code: [200, 201, 204, 405]
```

---

## CLI Features (Not Config)

These features are enabled via command-line flags, not the YAML config:

| Flag | Description |
|------|-------------|
| `--baseline-mode` | Capture baseline responses without fuzzing |
| `--diff-analysis` | Compare fuzzed responses against baselines |
| `--detect-reflection` | Detect if payloads appear in responses (XSS) |
| `--auto-throttle` | Auto-detect and back off from rate limiting |
| `--waf-detect` | Detect Web Application Firewall presence |
| `--no-live` | Disable Rich Live table (for piped output / Windows) |
| `--continue-on-auth-errors` | Don't pause on 401s when no auth configured |

Typical workflow:

```bash
# Step 1: Capture baselines
python -m avada_kedavra requests.json --baseline-mode

# Step 2: Fuzz with analysis
python -m avada_kedavra requests.json -c config.yaml --diff-analysis --detect-reflection --waf-detect
```
