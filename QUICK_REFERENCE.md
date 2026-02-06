# Quick Reference Guide

## Common Commands

```bash
# Basic replay (no modifications)
python -m avada_kedavra requests.json

# With configuration
python -m avada_kedavra requests.json -c config.yaml

# Through Burp proxy
python -m avada_kedavra requests.json -c config.yaml \
  --proxy http://127.0.0.1:8080 --no-verify

# High concurrency with delay
python -m avada_kedavra requests.json -c config.yaml -t 20 -d 0.1

# Custom timeout
python -m avada_kedavra requests.json --timeout 30

# No redirects
python -m avada_kedavra requests.json --no-redirects
```

## Configuration Snippets

### SQL Injection Testing
```yaml
rules:
  - filter:
      method: GET
    target:
      type: url
      name: id
    payloads:
      type: file
      source: 'sqli_payloads.txt'
```

### XSS Testing
```yaml
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
```

### Header Fuzzing
```yaml
rules:
  - target:
      type: header
      name: User-Agent
    payloads:
      type: list
      source:
        - 'Mozilla/5.0'
        - 'curl/7.68.0'
        - 'sqlmap/1.0'
```

### Cookie Manipulation
```yaml
rules:
  - target:
      type: cookie
      name: session_id
    payloads:
      type: file
      source: 'session_tokens.txt'
```

### Multi-Rule Configuration
```yaml
rules:
  # Test POST /login for SQLi
  - filter:
      method: POST
      url_path_contains: /login
    target:
      type: body
      name: username
    payloads:
      type: file
      source: 'sqli.txt'

  # Test all GET for XSS
  - filter:
      method: GET
    target:
      type: url
      name: search
    payloads:
      type: file
      source: 'xss.txt'
```

## Filter Options

| Filter | Type | Example | Description |
|--------|------|---------|-------------|
| `method` | string/list | `POST` or `[GET, POST]` | HTTP method |
| `url_contains` | string | `/api/users/` | Substring in full URL |
| `url_path_contains` | string | `/login` | Substring in path only |
| `header_present` | string | `Authorization` | Header exists |
| `header_value_contains` | dict | `{Content-Type: json}` | Header value substring |

## Target Types

| Type | Example | Description |
|------|---------|-------------|
| `url` | `name: id` | URL query parameter |
| `header` | `name: User-Agent` | HTTP header (case-insensitive) |
| `cookie` | `name: session` | Cookie value |
| `body` | `name: email` | JSON or form parameter |

## Payload Sources

| Type | Example | Description |
|------|---------|-------------|
| `list` | `source: [a, b, c]` | Inline list |
| `file` | `source: 'payloads.txt'` | One per line |
| `single` | `source: 'test'` | Single value |

## Project Structure Quick Reference

```
avada_kedavra/
├── __main__.py          # Entry point - run with `python -m avada_kedavra`
├── core/
│   ├── config.py        # load_config(), merge_cli_args()
│   ├── request_parser.py # load_requests(), prepare_request_components()
│   ├── payload_loader.py # load_payloads()
│   ├── filter.py        # request_matches_filter()
│   └── modifier.py      # apply_modification()
├── network/
│   └── requester.py     # make_request_worker()
├── ui/
│   └── console.py       # create_results_table()
├── models/
│   └── request.py       # RequestComponents, AppConfig, TaskData
└── utils/
    └── exceptions.py    # Custom exceptions
```

## Troubleshooting

### Problem: SSL Certificate Error
```bash
# Solution: Disable verification
python -m avada_kedavra requests.json --no-verify
```

### Problem: Connection Timeout
```bash
# Solution: Increase timeout
python -m avada_kedavra requests.json --timeout 30
```

### Problem: Proxy Not Working
```bash
# Check proxy is running
curl -x http://127.0.0.1:8080 http://example.com

# Use with --no-verify for self-signed certs
python -m avada_kedavra requests.json \
  --proxy http://127.0.0.1:8080 --no-verify
```

### Problem: No Requests Generated
```
# Check:
1. Filters match your requests (method, URL, headers)
2. Target parameters exist in requests
3. Payload files are readable and non-empty
4. File paths are relative to current directory
```

### Problem: Rate Limited
```bash
# Solution: Add delay between requests
python -m avada_kedavra requests.json -c config.yaml -d 0.5
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (config, parsing, etc.) |
| 130 | User interrupted (Ctrl+C) |

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set PYTHONPATH (if not installed)
export PYTHONPATH=/path/to/workspace:$PYTHONPATH

# Run
python -m avada_kedavra requests.json -c config.yaml
```

## Code Examples

### Programmatic Usage
```python
from avada_kedavra.core.config import load_config
from avada_kedavra.core.request_parser import load_requests, prepare_request_components
from avada_kedavra.core.filter import request_matches_filter
from avada_kedavra.core.modifier import apply_modification

# Load configuration
config = load_config('config.yaml')

# Load requests
requests_data = load_requests('requests.json')

# Parse first request
components = prepare_request_components(requests_data[0])

# Check filter
rule = config.rules[0]
if request_matches_filter(components, rule.get('filter')):
    # Apply modification
    modified, success = apply_modification(
        components,
        rule.get('target'),
        'test_payload'
    )
```

### Custom Exception Handling
```python
from avada_kedavra.utils.exceptions import (
    ConfigurationError,
    RequestParsingError,
    PayloadLoadError
)

try:
    # Your code here
    pass
except ConfigurationError as e:
    print(f"Config error: {e}")
except RequestParsingError as e:
    print(f"Parse error: {e}")
except PayloadLoadError as e:
    print(f"Payload error: {e}")
```

## Performance Tips

1. **Start Small**: Begin with 5-10 threads
2. **Use Delays**: Add 100-500ms delay for stability
3. **Limit Payloads**: Test with small payload sets first
4. **Monitor Resources**: Watch CPU/memory usage
5. **Use Filters**: Narrow down to relevant requests only

## Best Practices

1. **Always test locally first** before targeting production
2. **Use proxy** to inspect and verify requests
3. **Keep payloads organized** in separate files
4. **Document your configs** with comments
5. **Backup original files** before modification
6. **Check authorization** before testing any system

## Useful One-Liners

```bash
# Count total requests
cat requests.json | jq length

# Extract all URLs
cat requests.json | jq -r '.[].url'

# Count POST requests
cat requests.json | jq '[.[] | select(.method == "POST")] | length'

# Find requests to specific endpoint
cat requests.json | jq '.[] | select(.url | contains("/api/login"))'

# Count lines in payload file
wc -l payloads.txt
```

## Version Info

```bash
# Check version
python -m avada_kedavra --version

# Check Python version
python --version

# Check dependencies
pip list | grep -E "requests|rich|pyyaml"
```
