# Avada Kedavra 🧙‍♂️

A powerful HTTP request replay and fuzzing tool for security testing and penetration testing workflows.

## Features

### Core Features
- **Request Replay**: Replay captured HTTP requests from JSON files
- **Smart Fuzzing**: Apply payloads to specific request components (URL params, headers, cookies, body)
- **Flexible Filtering**: Target specific requests using method, URL patterns, headers, and more
- **Response Conditions**: Automatically check responses for patterns, status codes, sizes, and timing
- **Result Export**: Save results to JSON, CSV, or HTML format
- **Concurrent Execution**: Multi-threaded request sending with configurable concurrency
- **Rich Terminal UI**: Real-time progress tracking and results display using Rich
- **Proxy Support**: Route requests through HTTP/HTTPS proxies (e.g., Burp Suite)
- **SSL Options**: Disable SSL verification for testing environments

### 🚀 Phase 1 Security Testing Features (NEW!)
- **Baseline Mode**: Capture baseline responses for differential analysis
- **Differential Analysis**: Detect anomalies by comparing fuzzed responses against baselines
- **Reflection Detection**: Automatically detect if payloads are reflected in responses (XSS testing)
- **Auto-Throttle**: Adaptive rate limiting with automatic detection and backoff
- **WAF Detection**: Identify Web Application Firewall presence

### Architecture
- **Modular Design**: Clean, maintainable codebase with proper separation of concerns
- **Type Safety**: Full type hints throughout
- **Comprehensive Tests**: 68+ unit tests with 89-100% coverage on core modules

## Installation

```bash
cd avada_kedavra
pip install -r requirements.txt
```

## Quick Start

### Basic Request Replay

```bash
python -m avada_kedavra requests.json
```

### With Configuration Rules

```bash
python -m avada_kedavra requests.json -c config.yaml
```

### Through a Proxy

```bash
python -m avada_kedavra requests.json -c config.yaml --proxy http://127.0.0.1:8080 --no-verify
```

### With Custom Threading

```bash
python -m avada_kedavra requests.json -c config.yaml -t 10 -d 0.1
```

### Export Results

```bash
# Export to JSON
python -m avada_kedavra requests.json -c config.yaml -o results.json

# Export to CSV
python -m avada_kedavra requests.json -c config.yaml -o results.csv

# Export to HTML report
python -m avada_kedavra requests.json -c config.yaml -o results.html
```

### 🚀 Phase 1 Security Testing Features

#### Baseline Mode & Differential Analysis

Capture baseline responses, then compare fuzzing results to detect anomalies:

```bash
# Step 1: Capture baselines (run requests without fuzzing)
python -m avada_kedavra requests.json --baseline-mode --baseline-file my_baselines.json

# Step 2: Fuzz with differential analysis
python -m avada_kedavra requests.json -c config.yaml --diff-analysis --baseline-file my_baselines.json
```

**What it detects:**
- Status code changes (200 → 500)
- Response size anomalies (±15% threshold)
- Response time anomalies (±30% threshold)
- New error messages introduced by payloads
- Body content changes

**Output examples:**
- `Δ200→500` - Status changed from 200 to 500
- `Size+234B` - Response 234 bytes larger than baseline
- `Time-12%` - Response 12% faster than baseline
- `ERR!` - New error detected in response

#### Reflection Detection

Automatically detect if your payloads appear in HTTP responses:

```bash
# Enable reflection detection for XSS testing
python -m avada_kedavra requests.json -c xss_config.yaml --detect-reflection
```

**What it detects:**
- Exact payload matches in body or headers
- HTML-encoded payloads (`<script>` → `&lt;script&gt;`)
- URL-encoded payloads
- JavaScript-escaped payloads

**Output examples:**
- `Reflected(body)` - Payload found in response body
- `Reflected(headers)` - Payload found in headers
- `Reflected(both) [html]` - Payload reflected in both, HTML-encoded

#### Auto-Throttle & Rate Limit Detection

Automatically detect and adapt to rate limiting:

```bash
# Enable automatic throttling
python -m avada_kedavra requests.json -c config.yaml --auto-throttle
```

**How it works:**
- Detects 429/503 status codes
- Looks for rate limit keywords ("too many requests", "throttle", etc.)
- Automatically increases delay between requests (exponential backoff)
- Reduces delay after cooldown period
- Shows statistics: `Rate Limiting: Detected 3 times, current delay: 2.50s`

#### WAF Detection

Identify if a Web Application Firewall is blocking requests:

```bash
# Enable WAF detection
python -m avada_kedavra requests.json -c config.yaml --waf-detect
```

**Detects common WAFs:**
- Cloudflare, Akamai, Imperva, F5, ModSecurity, AWS WAF, Barracuda, Sucuri

**Output:** `WAF:CLOUDFLARE`

#### Combining Features

Use multiple Phase 1 features together for comprehensive testing:

```bash
# Full security testing workflow
python -m avada_kedavra requests.json -c sqli_config.yaml \
  --diff-analysis \
  --detect-reflection \
  --auto-throttle \
  --waf-detect \
  -o findings.html
```

## Usage

```
python -m avada_kedavra [-h] [-c CONFIG] [-t THREADS] [-d DELAY]
                        [--timeout TIMEOUT] [--no-verify] [--no-redirects]
                        [--proxy PROXY] [-o OUTPUT]
                        [--baseline-mode] [--baseline-file BASELINE_FILE]
                        [--diff-analysis] [--detect-reflection]
                        [--auto-throttle] [--waf-detect]
                        [--version]
                        input_file

positional arguments:
  input_file            Path to the JSON file containing requests

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the YAML configuration file for modifications
  -t THREADS, --threads THREADS
                        Number of concurrent threads (default: 5)
  -d DELAY, --delay DELAY
                        Delay in seconds between starting threads (default: 0)
  --timeout TIMEOUT     Override request timeout in seconds (default: 10)
  --no-verify           Disable SSL certificate verification
  --no-redirects        Disable following redirects
  --proxy PROXY         HTTP/HTTPS proxy address (e.g., http://127.0.0.1:8080)
  -o OUTPUT, --output OUTPUT
                        Save results to file (.json, .csv, .html)

Phase 1 Security Testing:
  --baseline-mode       Run in baseline mode: capture baseline responses
  --baseline-file FILE  Path to baseline file (default: baselines.json)
  --diff-analysis       Enable differential analysis against baselines
  --detect-reflection   Detect if payloads are reflected in responses
  --auto-throttle       Automatically detect and adapt to rate limiting
  --waf-detect          Attempt to detect Web Application Firewall

  --version             show program's version number and exit
```

## Configuration File Format

The configuration file uses YAML format and supports multiple modification rules with filters:

```yaml
rules:
  # Rule 1: Fuzz email parameter in POST requests
  - filter:
      method: POST
      url_path_contains: /api/users/
    target:
      type: body
      name: email
    payloads:
      type: file
      source: 'payloads/emails.txt'

  # Rule 2: Test different User-Agent headers
  - filter:
      header_present: Authorization
    target:
      type: header
      name: User-Agent
    payloads:
      type: list
      source:
        - 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        - 'curl/7.68.0'
        - 'python-requests/2.25.1'

  # Rule 3: SQL injection testing on search parameter
  - filter:
      method: GET
      url_contains: /search
    target:
      type: url
      name: q
    payloads:
      type: file
      source: 'payloads/sqli.txt'

# Optional global settings
threads: 10
delay: 0.1
timeout: 15
verify_ssl: false
allow_redirects: false
```

### Filter Options

Filters allow you to target specific requests:

- `method`: Filter by HTTP method (GET, POST, etc.) - can be a single value or list
- `url_contains`: Filter by substring in full URL
- `url_path_contains`: Filter by substring in URL path only
- `header_present`: Filter by presence of specific header
- `header_value_contains`: Filter by header value substring (dict format)

### Target Types

Specify where to inject payloads:

- `method`: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) - no `name` field needed
- `url`: URL query parameters
- `header`: HTTP headers (case-insensitive matching)
- `cookie`: Cookie values
- `body`: Request body parameters (JSON or form data)

### Payload Sources

Three ways to specify payloads:

1. **List**: Inline list of values
   ```yaml
   payloads:
     type: list
     source: ['value1', 'value2', 'value3']
   ```

2. **File**: Load from text file (one payload per line)
   ```yaml
   payloads:
     type: file
     source: 'payloads/xss.txt'
   ```

3. **Single**: Single value
   ```yaml
   payloads:
     type: single
     source: 'test_value'
   ```

### Response Conditions (NEW!)

Check HTTP responses for specific characteristics and get real-time feedback:

```yaml
rules:
  - filter:
      method: POST
    target:
      type: body
      name: username
    payloads:
      type: file
      source: 'sqli_payloads.txt'
    conditions:
      # Check for SQL errors in response
      regex_in_body: "error|exception|syntax"
      # Or specific strings
      string_in_body: "admin"
      # Status codes
      status_code: [200, 500]
      # Size anomalies
      content_length_gt: 1000
      # Performance
      response_time_gt: 2.0
```

**Available Conditions:**
- `match_mode`: `"any"` (default - OR logic) or `"all"` (AND logic - only show if all match)
- `string_in_body` / `string_in_headers`: String matching
- `regex_in_body` / `regex_in_headers`: Pattern matching
- `status_code`: HTTP status codes (single or list)
- `content_length_gt/lt/eq`: Response size checks
- `response_time_gt/lt`: Response timing checks

**Match Modes:**
- `match_mode: "any"`: Show if ANY condition matches (displays all matches)
- `match_mode: "all"`: Only show if ALL conditions match (precise filtering)

Matched conditions display in real-time: `✓ Body:'error' | Status=500 | Size>1000`

📖 **[Full Response Conditions Documentation](RESPONSE_CONDITIONS_FEATURE.md)**

## Request JSON Format

The input JSON file should contain an array of request objects captured from tools like Burp Suite or browser DevTools:

```json
[
  {
    "method": "POST",
    "url": "https://example.com/api/login",
    "headers": [
      "POST /api/login HTTP/1.1",
      "Host: example.com",
      "Content-Type: application/json",
      "User-Agent: Mozilla/5.0"
    ],
    "params": [
      {
        "type": "json",
        "name": "username",
        "value": "admin"
      },
      {
        "type": "json",
        "name": "password",
        "value": "password123"
      }
    ]
  }
]
```

### Parameter Types

- `url`: URL query parameter
- `cookie`: Cookie value
- `json`: JSON body parameter
- `body`: Form body parameter or raw body
- `multipart`: Multipart form data

## Project Structure

The refactored codebase follows a modular architecture:

```
avada_kedavra/
├── __init__.py              # Package initialization
├── __main__.py              # Main entry point and CLI
├── requester.py             # Backward compatibility wrapper (deprecated)
├── config.yaml              # Example configuration
├── requirements.txt         # Python dependencies
│
├── core/                    # Core business logic
│   ├── __init__.py
│   ├── config.py           # Configuration loading
│   ├── request_parser.py   # Request parsing logic
│   ├── payload_loader.py   # Payload loading
│   ├── filter.py           # Request filtering
│   └── modifier.py         # Request modification
│
├── network/                 # Network operations
│   ├── __init__.py
│   └── requester.py        # HTTP request execution
│
├── ui/                      # User interface
│   ├── __init__.py
│   └── console.py          # Rich console management
│
├── models/                  # Data models
│   ├── __init__.py
│   └── request.py          # Request component dataclasses
│
└── utils/                   # Utilities
    ├── __init__.py
    └── exceptions.py       # Custom exceptions
```

## Examples

### Example 1: SQLi Testing

```bash
# Create payload file
cat > sqli.txt << EOF
' OR '1'='1
admin'--
' UNION SELECT NULL--
EOF

# Create config
cat > sqli_config.yaml << EOF
rules:
  - filter:
      method: GET
    target:
      type: url
      name: id
    payloads:
      type: file
      source: sqli.txt
EOF

# Run fuzzer
python -m avada_kedavra requests.json -c sqli_config.yaml -t 5
```

### Example 2: XSS Testing

```bash
# Create config for XSS testing
cat > xss_config.yaml << EOF
rules:
  - filter:
      method: POST
      url_path_contains: /comment
    target:
      type: body
      name: message
    payloads:
      type: list
      source:
        - '<script>alert(1)</script>'
        - '<img src=x onerror=alert(1)>'
        - '"><script>alert(String.fromCharCode(88,83,83))</script>'
EOF

python -m avada_kedavra requests.json -c xss_config.yaml --proxy http://127.0.0.1:8080
```

### Example 3: HTTP Method Enumeration

```bash
# Test which HTTP methods are allowed on endpoints
cat > method_enum_config.yaml << EOF
rules:
  - filter:
      url_contains: /api/
    target:
      type: method
    payloads:
      type: list
      source:
        - GET
        - POST
        - PUT
        - DELETE
        - PATCH
        - OPTIONS
        - HEAD
    conditions:
      status_code: [200, 201, 204, 405]  # Track both allowed and disallowed
EOF

python -m avada_kedavra requests.json -c method_enum_config.yaml --detect-reflection
```

### Example 4: Header Fuzzing

```bash
cat > header_config.yaml << EOF
rules:
  - target:
      type: header
      name: X-Forwarded-For
    payloads:
      type: list
      source:
        - '127.0.0.1'
        - '192.168.1.1'
        - '10.0.0.1'
EOF

python -m avada_kedavra requests.json -c header_config.yaml -t 3
```

## Best Practices

### General Best Practices
1. **Start with Low Thread Count**: Begin with 5-10 threads to avoid overwhelming target servers
2. **Use Delays for Rate Limiting**: Add delays (`-d 0.1`) to avoid triggering rate limits
3. **Proxy Through Burp**: Use `--proxy` to route through Burp Suite for additional analysis
4. **Test SSL Issues**: Use `--no-verify` when testing against self-signed certificates
5. **Filter Wisely**: Use filters to target only relevant requests and reduce noise
6. **Organize Payloads**: Keep payload files organized by attack type (sqli/, xss/, etc.)

### Phase 1 Best Practices

#### Baseline & Differential Analysis Workflow
1. **Always capture baselines first** before fuzzing
2. **Use identical conditions** (same network, same time of day) for baseline and fuzzing
3. **Review baseline responses** to ensure they're "normal" before using them
4. **Adjust thresholds** if getting too many/too few anomalies (15% size, 30% time by default)
5. **Focus on anomalies** - responses that differ significantly from baseline are most interesting

```bash
# Good workflow
python -m avada_kedavra requests.json --baseline-mode
python -m avada_kedavra requests.json -c sqli.yaml --diff-analysis --detect-reflection -o results.html
```

#### Reflection Detection Tips
1. **Use with XSS payloads** - designed for detecting reflected input
2. **Check context** - reflection in JavaScript vs HTML matters
3. **Combine with conditions** - look for reflections in 200 responses only
4. **Minimum length** - payloads < 3 chars ignored (reduces false positives)

#### Auto-Throttle Usage
1. **Enable by default** for unknown targets - prevents blocking
2. **Combine with delays** - starts with your base delay, increases if needed
3. **Monitor statistics** - check how many times rate limiting was detected
4. **Test legitimately** - ensure you have permission before aggressive testing

#### WAF Detection
1. **Run early** - detect WAF presence before heavy fuzzing
2. **Adjust tactics** - if WAF detected, use slower, stealthier approaches
3. **Payload selection** - WAFs block common signatures, try encoding/obfuscation
4. **Document findings** - note WAF type in penetration test reports

## Troubleshooting

### SSL Certificate Errors

```bash
python -m avada_kedavra requests.json -c config.yaml --no-verify
```

### Proxy Connection Issues

Ensure your proxy is running and accessible:
```bash
curl -x http://127.0.0.1:8080 http://example.com
```

### No Requests Generated

Check that:
- Your filters match the requests in the JSON file
- Target parameters exist in the filtered requests
- Payload files are readable and non-empty

## Security Notice

This tool is designed for **authorized security testing only**. Ensure you have proper authorization before testing any system. Unauthorized testing may be illegal and unethical.

## Development

### Running Tests

The project includes comprehensive unit tests using pytest:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
cd avada_kedavra
PYTHONPATH=/home/codeuser/workspace:$PYTHONPATH pytest

# Run with verbose output
PYTHONPATH=/home/codeuser/workspace:$PYTHONPATH pytest -v

# Run specific test file
PYTHONPATH=/home/codeuser/workspace:$PYTHONPATH pytest tests/test_condition_checker.py

# Run with coverage report
PYTHONPATH=/home/codeuser/workspace:$PYTHONPATH pytest --cov=avada_kedavra --cov-report=term-missing
```

**Test Coverage:**
- `core/modifier.py`: 100%
- `core/payload_loader.py`: 94%
- `core/filter.py`: 92%
- `core/condition_checker.py`: 89%
- Overall: 54%

**Test Suites:**
- `tests/test_condition_checker.py`: Response condition checking logic (24 tests)
- `tests/test_filter.py`: Request filtering logic (18 tests)
- `tests/test_payload_loader.py`: Payload loading from different sources (14 tests)
- `tests/test_modifier.py`: Request modification logic (14 tests)

### Project Architecture

The codebase follows clean architecture principles with separated concerns:

```
avada_kedavra/
├── __init__.py              # Package initialization
├── __main__.py              # Main entry point and CLI
├── config.yaml              # Example configuration
├── requirements.txt         # Python dependencies
│
├── core/                    # Business logic
│   ├── config.py           # Configuration loading
│   ├── request_parser.py   # Request parsing
│   ├── payload_loader.py   # Payload loading
│   ├── filter.py           # Request filtering
│   ├── modifier.py         # Request modification
│   ├── condition_checker.py # Response conditions
│   ├── diff_analyzer.py    # 🚀 Differential analysis (Phase 1)
│   ├── reflection_detector.py # 🚀 Reflection detection (Phase 1)
│   └── rate_limiter.py     # 🚀 Rate limiting & WAF detection (Phase 1)
│
├── network/                 # Network operations
│   └── requester.py        # HTTP request execution with Phase 1 features
│
├── ui/                      # User interface
│   ├── console.py          # Rich console output
│   └── exporter.py         # Result export (JSON, CSV, HTML)
│
├── models/                  # Data models
│   ├── request.py          # Request components
│   ├── condition.py        # Response conditions
│   └── baseline.py         # 🚀 Baseline data models (Phase 1)
│
├── utils/                   # Utilities
│   └── exceptions.py       # Custom exceptions
│
└── tests/                   # Unit tests (68+ tests)
    ├── test_condition_checker.py
    ├── test_filter.py
    ├── test_modifier.py
    └── test_payload_loader.py
```

## Contributing

Contributions are welcome! The modular architecture makes it easy to add new features:

- Add new filter types in `core/filter.py`
- Add new target types in `core/modifier.py`
- Add new condition types in `core/condition_checker.py`
- Enhance output formats in `ui/console.py` and `ui/exporter.py`
- Add new payload sources in `core/payload_loader.py`

**Before submitting:**
1. Write tests for new features
2. Ensure all existing tests pass
3. Maintain type hints throughout
4. Update documentation

## License

This tool is provided for educational and authorized security testing purposes only.

## Changelog

### Version 2.0.0 - Phase 1 Security Features (Current)
- 🚀 **Baseline Mode**: Capture baseline responses for comparison
- 🚀 **Differential Analysis**: Detect anomalies (status, size, time, errors) vs baseline
- 🚀 **Reflection Detection**: Auto-detect payload reflection with encoding detection
- 🚀 **Auto-Throttle**: Adaptive rate limiting with automatic detection and backoff
- 🚀 **WAF Detection**: Identify common Web Application Firewalls
- ✅ Enhanced result export with Phase 1 data
- ✅ Comprehensive test suite (68+ tests, 89-100% coverage on core modules)
- ✅ Updated documentation and examples

### Version 1.0.0 - Major Refactoring
- ✅ Modular architecture with separated concerns
- ✅ Type hints throughout codebase
- ✅ Custom exceptions for better error handling
- ✅ Data classes for request components
- ✅ Response condition checking
- ✅ Result export (JSON, CSV, HTML)
- ✅ Improved CLI with better help text
- ✅ Backward compatibility with original interface
- ✅ Enhanced documentation
