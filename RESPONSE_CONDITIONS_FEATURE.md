# Response Conditions Feature

## Overview

The Response Conditions feature allows you to automatically check HTTP responses for specific characteristics and display matches in real-time during fuzzing/testing. This is perfect for:

- **Finding Vulnerabilities**: Detect SQL errors, stack traces, or sensitive data in responses
- **Success Detection**: Identify when payloads successfully trigger specific behaviors
- **Performance Monitoring**: Track slow responses or size anomalies
- **Pattern Matching**: Use regex to find complex patterns in responses

## How It Works

1. **Configure conditions** in your YAML config file under each rule
2. **Choose match mode**: `any` (show all matches) or `all` (only if all match)
3. **Send requests** using avada_kedavra as normal
4. **Automatic checking**: Each response is checked against configured conditions
5. **Visual feedback**: Matched conditions appear in the "Error/Conditions" column with a ✓

## Match Modes

**`match_mode: "any"` (default - OR logic)**
- Shows result if **ANY** condition matches
- Displays all matching conditions
- Great for **discovery** and seeing what matched
- Example: If 2 out of 3 conditions match, shows both

**`match_mode: "all"` (AND logic)**
- Only shows result if **ALL** conditions match
- Great for **precise filtering**
- Example: Only show responses that are Status=200 AND contain "admin" AND size>1000

```yaml
conditions:
  match_mode: "any"  # or "all"
  string_in_body: "success"
  status_code: 200
```

## Available Conditions

### String Matching

**`string_in_body`**: Check if a specific string exists in the response body
```yaml
conditions:
  string_in_body: "error"  # Look for "error" in response
```

**`string_in_headers`**: Check if a specific string exists in response headers
```yaml
conditions:
  string_in_headers: "X-Debug"  # Look for "X-Debug" header
```

### Regex Pattern Matching

**`regex_in_body`**: Match a regex pattern in the response body
```yaml
conditions:
  regex_in_body: "error|exception|stack trace"  # Match any of these
```

**`regex_in_headers`**: Match a regex pattern in response headers
```yaml
conditions:
  regex_in_headers: "Server: Apache/\\d+\\.\\d+"  # Match Apache version
```

### Status Code Checking

**`status_code`**: Match specific HTTP status code(s)
```yaml
conditions:
  status_code: 200  # Single status code

# OR

conditions:
  status_code: [200, 201, 204]  # Multiple codes
```

### Content Length Conditions

**`content_length_gt`**: Response size greater than N bytes
```yaml
conditions:
  content_length_gt: 1000  # Larger than 1000 bytes
```

**`content_length_lt`**: Response size less than N bytes
```yaml
conditions:
  content_length_lt: 100  # Smaller than 100 bytes
```

**`content_length_eq`**: Response size equals N bytes
```yaml
conditions:
  content_length_eq: 512  # Exactly 512 bytes
```

### Response Time Conditions

**`response_time_gt`**: Response time greater than N seconds
```yaml
conditions:
  response_time_gt: 1.0  # Slower than 1 second
```

**`response_time_lt`**: Response time less than N seconds
```yaml
conditions:
  response_time_lt: 0.5  # Faster than 0.5 seconds
```

## Complete Examples

### Example 1: SQL Injection Detection

```yaml
rules:
  - filter:
      method: GET
    target:
      type: url
      name: id
    payloads:
      type: list
      source:
        - "' OR '1'='1"
        - "admin'--"
        - "1' UNION SELECT NULL--"
    conditions:
      # Look for common SQL error messages
      regex_in_body: "SQL|syntax|mysql|postgres|oracle"
      # Or successful injection indicators
      string_in_body: "admin"
      # Check for error status codes
      status_code: [200, 500]
```

### Example 2: XSS Detection

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
        - '"><script>prompt(1)</script>'
    conditions:
      # Check if script tag is reflected
      string_in_body: "<script>"
      # Or img tag
      string_in_body: "<img"
      # Successful responses
      status_code: 200
```

### Example 3: Authentication Bypass

```yaml
rules:
  - target:
      type: cookie
      name: session_id
    payloads:
      type: list
      source:
        - 'admin'
        - 'administrator'
        - '00000000-0000-0000-0000-000000000000'
    conditions:
      # Look for successful access indicators
      string_in_body: "Welcome"
      string_in_body: "Dashboard"
      # Successful status
      status_code: 200
      # Expect substantial response (not just error page)
      content_length_gt: 500
```

### Example 4: API Rate Limiting Detection

```yaml
rules:
  - filter:
      method: POST
      url_contains: /api/
    target:
      type: header
      name: X-API-Key
    payloads:
      type: file
      source: 'api_keys.txt'
    conditions:
      # Detect rate limiting
      status_code: 429
      string_in_body: "rate limit"
      # Or detect successful access
      status_code: 200
      response_time_lt: 1.0
```

### Example 5: File Upload Testing

```yaml
rules:
  - filter:
      method: POST
      url_path_contains: /upload
    target:
      type: body
      name: filename
    payloads:
      type: list
      source:
        - 'shell.php'
        - '../../../etc/passwd'
        - 'test.exe'
    conditions:
      # Look for upload success
      string_in_body: "uploaded successfully"
      status_code: [200, 201]
      # Or path traversal success
      string_in_body: "root:"
      # Or filter rejection messages
      string_in_body: "not allowed"
```

### Example 6: Performance Testing

```yaml
rules:
  - filter:
      method: GET
    target:
      type: url
      name: page_size
    payloads:
      type: list
      source: [10, 100, 1000, 10000]
    conditions:
      # Detect slow queries
      response_time_gt: 2.0
      # Or unusually large responses
      content_length_gt: 100000
      # Successful responses only
      status_code: 200
```

## Match Mode Examples

### Example: ANY mode (default - OR logic)

```yaml
conditions:
  match_mode: "any"  # Show if ANY condition matches
  status_code: 200
  string_in_body: "success"
  content_length_gt: 100
```

**Scenario 1:** Status=200 ✓, Body contains "success" ✓, Size=50 ✗
**Result:** `✓ Status=200 | Body:'success'` (shows 2 matches)

**Scenario 2:** Status=404 ✗, Body contains "success" ✓, Size=150 ✓
**Result:** `✓ Body:'success' | Size>100` (shows 2 matches)

**Scenario 3:** All three match
**Result:** `✓ Status=200 | Body:'success' | Size>100` (shows all 3)

### Example: ALL mode (AND logic)

```yaml
conditions:
  match_mode: "all"  # Only show if ALL conditions match
  status_code: 200
  string_in_body: "admin"
  content_length_gt: 500
```

**Scenario 1:** Status=200 ✓, Body contains "admin" ✓, Size=300 ✗
**Result:** (nothing shown - not all matched)

**Scenario 2:** Status=404 ✗, Body contains "admin" ✓, Size=600 ✓
**Result:** (nothing shown - not all matched)

**Scenario 3:** Status=200 ✓, Body contains "admin" ✓, Size=600 ✓
**Result:** `✓ Status=200 | Body:'admin' | Size>500` (all matched!)

### When to Use Each Mode

**Use `match_mode: "any"`** (default) when:
- Exploring and discovering vulnerabilities
- You want to see partial matches
- Multiple conditions are "OR" alternatives (SQL error OR timing anomaly)
- Testing different attack vectors

**Use `match_mode: "all"`** when:
- You need precise filtering
- All conditions must be true for a valid finding
- Reducing false positives
- Looking for very specific response patterns

## Multiple Conditions

You can combine as many conditions as needed. The behavior depends on `match_mode`:

**With `match_mode: "any"`:**
All matching conditions are displayed

**With `match_mode: "all"`:**
Shows all conditions only if every single one matched

## Output Format

Matched conditions appear in the "Error/Conditions" column with:
- **Green checkmark** (✓) prefix
- **Compact format** to fit in terminal
- **Pipe-separated** for multiple matches

Examples:
```
✓ Body:'email' | Status=200 | Size>100
✓ Regex(body) | Status=500
✓ Hdr:'X-Debug' | Time>2.0s
```

## Use Cases

### Security Testing

1. **SQL Injection**: Detect database errors or data leakage
2. **XSS**: Check if payloads are reflected in responses
3. **SSRF**: Look for internal IP addresses or metadata in responses
4. **XXE**: Detect XML parsing errors or file disclosure
5. **Auth Bypass**: Find successful authentication indicators

### Quality Assurance

1. **Error Detection**: Find 500 errors or exceptions
2. **Performance**: Identify slow endpoints
3. **Size Anomalies**: Detect missing or oversized responses
4. **Header Testing**: Verify security headers are present

### API Testing

1. **Status Codes**: Verify correct status codes
2. **Response Format**: Check for JSON/XML structure
3. **Rate Limiting**: Detect 429 responses
4. **Error Messages**: Find API error patterns

## Performance Considerations

- **Body capture**: Responses are read as text for condition checking
- **Minimal overhead**: Conditions checked only when configured
- **No storage**: Response bodies not stored after checking
- **Concurrent**: Checking happens in request worker threads

## Tips & Best Practices

1. **Start specific**: Use targeted conditions to reduce noise
2. **Combine conditions**: Use multiple conditions for precise detection
3. **Use regex wisely**: Regex is powerful but can be slower
4. **Monitor performance**: Use time conditions to find bottlenecks
5. **Test patterns**: Verify your regex patterns match expected content

## Troubleshooting

### No Conditions Matching

1. Check condition syntax in YAML
2. Verify strings/patterns exist in responses
3. Test with simpler conditions first (e.g., status_code)
4. Check response content manually

### Too Many Matches

1. Make conditions more specific
2. Add additional filtering conditions
3. Use regex with precise patterns
4. Combine multiple conditions with AND logic

### Performance Issues

1. Reduce regex complexity
2. Limit response body size conditions
3. Use filters to reduce request count
4. Lower thread count if needed

## Architecture

### Components

1. **ResponseData**: Data class capturing response info
2. **ConditionChecker**: Logic for evaluating all condition types
3. **Network Layer**: Captures response body and headers
4. **UI Layer**: Displays matched conditions with formatting

### Data Flow

```
HTTP Response
    ↓
Capture (body, headers, status, size, time)
    ↓
Create ResponseData object
    ↓
Check Conditions (if configured)
    ↓
Format Matches
    ↓
Display in Table
```

## Future Enhancements

Potential future additions:
- JSON path conditions (`json_path: "$.user.id"`)
- Header value extraction
- Response comparison (diff from baseline)
- Condition negation (`not_contains`)
- Custom condition scripts
- Export matched responses to file

## See Also

- [README.md](README.md) - Main documentation
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference guide
- [config.yaml](config.yaml) - Example configuration with conditions
