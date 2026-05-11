# Architecture Documentation

Comprehensive design of auth daemon for multi-service OAuth automation.

## Problem Statement

Modern CLI tools (GitHub CLI, gcloud, Copilot CLI, etc) require OAuth authentication. Currently:

1. **No automation**: Users must manually open browser, click buttons, wait for redirect
2. **Repetitive**: Different auth flows for different services
3. **Error-prone**: Easy to forget credentials or get rate-limited
4. **Fragmented**: Each tool has its own auth implementation

## Solution: Auth Daemon

A local daemon that:
- Watches terminal for device codes
- Orchestrates browser automation via Accessibility API
- Caches tokens for reuse
- Exposes local HTTP API for programmatic access

## Design Decisions

### 1. Why Python?

- **Accessibility**: Python has better macOS Accessibility API bindings
- **Simplicity**: Easy to prototype and extend
- **Speed**: Fast enough for local daemon
- **Libraries**: Good HTTP, regex, session management libraries

Alternatives considered:
- **Swift/Objective-C**: More native, but harder to prototype
- **JavaScript/Node.js**: Poor Accessibility API support
- **Go**: Good, but overkill for local daemon

### 2. Platform-Specific UI Automation

Different platforms use different tools:

**macOS:**
- ✓ Accessibility API (osascript)
- Fast, native, respects cookies

**Linux:**
- ✓ xdotool (X11/Wayland)
- Fast, works with existing browser

**Windows:**
- ✓ pyautogui (fallback: keyboard)
- Simpler implementation, less reliable

Tried alternatives:
- ❌ Selenium: Too slow, resource-heavy
- ❌ Puppeteer/Playwright: Headless-only, can't reuse cookies
- ✓ Platform-specific tools: Fast, reliable, respects cookies

```
Playwright: "Browser not reachable"
 → Creates new headless session
 → GitHub rate-limits → Suspicious behavior

Accessibility API: Uses running Chrome
 → Reuses session cookies
 → GitHub sees legitimate user
 → No rate limit
```

### 3. Why Not Keyboard Maestro / AppleScript?

Keyboard Maestro is more powerful but:
- Requires paid license ($36)
- Not scriptable via CLI
- Harder to integrate with other tools

AppleScript alone:
- Limited to UI automation
- No HTTP server or persistence
- Poor error handling

Accessibility API:
- Built-in, free, reliable
- Can build on top of it
- Better error messages

### 4. Why HTTP Server (not socket/IPC)?

HTTP chosen for:
- **Standard**: Every language has HTTP client
- **Simple**: curl, requests, fetch work out of the box
- **Debuggable**: `curl localhost:8000` shows state
- **Testable**: No special tooling needed
- **Security**: localhost-only, no network exposure

Alternatives:
- ❌ Unix socket: Platform-specific, harder to debug
- ❌ stdin/stdout: Can't support multiple concurrent clients
- ✓ HTTP: Standard, simple, debuggable

### 5. Why Terminal Watching (not OS-level hooks)?

Terminal watching via regex:
- **Simple**: Parse stdout for known patterns
- **Reliable**: Doesn't depend on CI/system integrations
- **Universal**: Works with any terminal
- **Debuggable**: Can print logs

Alternatives:
- ❌ Launchd/system hooks: Complex, slow, OS-specific
- ❌ Library injection: Fragile, security risk
- ✓ Terminal watching: Simple, reliable, standard

### 6. Session Caching Strategy

```python
# Session cache structure
@dataclass
class CachedSession:
    service: str            # github, google, etc
    token: str              # OAuth token
    refresh_token: Optional[str]
    expires_at: float       # Unix timestamp
    created_at: float
```

Stored in: `~/.cache/auth-daemon/sessions.pkl`

Benefits:
- **Persistent**: Survives daemon restart
- **Typed**: Python pickle preserves types
- **Expiry-aware**: Automatically invalidates stale tokens
- **User-isolated**: Per-user cache directory

Considered:
- JSON: Lost type information, harder to deserialize
- SQLite: Overkill for 1-10 sessions
- Keychain: macOS-only, integration complexity

### 7. Service Handler Architecture

```python
class ServiceAuthHandler(ABC):
    def handle_device_code(self, code: str) -> bool:
        # Service-specific logic
        pass
    
    def extract_token(self, response: Dict) -> Optional[str]:
        # Service-specific token extraction
        pass
```

Each service gets a custom handler:
- **GitHub**: Type code into text box
- **Google**: Similar flow, different button labels
- **Slack**: Click "Allow" button directly
- **OAuth generics**: Handle localhost redirect

Benefits:
- **Extensible**: Add new service with few lines
- **Testable**: Mock each handler independently
- **Maintainable**: Service logic isolated

### 8. Error Handling Philosophy

**Fail gracefully, don't crash:**

```python
# Bad: Crash on accessibility failure
self.api.click_button("Authorize")  # Throws if fails

# Good: Fall back to manual
if not self.api.click_button("Authorize"):
    self.logger.warning("Failed to click Authorize (manual click required)")
```

Rationale:
- Accessibility API can be flaky (permissions, app crashes)
- Manual fallback is fine (user can click once)
- Better to partially automate than fully fail

### 9. Why Local Cache, Not OAuth Broker?

Considered: Central OAuth broker service (shared across machines)

Problems:
- **Security**: Storing tokens on shared server is risky
- **Complexity**: Need authentication, encryption, cleanup
- **Overkill**: Local daemon is simpler for single user

Solution: Local daemon only
- Each machine has own daemon
- Tokens never leave machine
- Simpler, safer, easier to manage

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│ User Terminal                                       │
│ $ gh auth login                                     │
│ Device code: XXXX-XXXX                              │
└────────────┬────────────────────────────────────────┘
             │
             ↓ (stdin/stdout capture via script -q)
┌─────────────────────────────────────────────────────┐
│ Auth Daemon (Python, localhost:8000)                │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────┐   │
│ │ Terminal Watcher                             │   │
│ │ - Monitors stdout                            │   │
│ │ - Regex: [A-Z0-9]{4}-[A-Z0-9]{4}             │   │
│ │ - Extracts code: XXXX-XXXX                   │   │
│ └──────────────────────────────────────────────┘   │
│              ↓                                       │
│ ┌──────────────────────────────────────────────┐   │
│ │ Service Handler (GitHub)                     │   │
│ │ - Opens browser: github.com/login/device     │   │
│ │ - Types code: XXXX-XXXX                      │   │
│ │ - Clicks button: "Authorize"                 │   │
│ └──────────────────────────────────────────────┘   │
│              ↓                                       │
│ ┌──────────────────────────────────────────────┐   │
│ │ Accessibility API (macOS)                    │   │
│ │ - osascript → System Events                  │   │
│ │ - Browser window control                     │   │
│ │ - Button clicks, text input                  │   │
│ └──────────────────────────────────────────────┘   │
│              ↓                                       │
│ ┌──────────────────────────────────────────────┐   │
│ │ Session Manager                              │   │
│ │ - Cache token: ~/.cache/auth-daemon/         │   │
│ │ - Store: service, token, expiry              │   │
│ │ - Validate: expiry check on retrieval        │   │
│ └──────────────────────────────────────────────┘   │
│              ↓                                       │
│ ┌──────────────────────────────────────────────┐   │
│ │ HTTP Server (port 8000)                      │   │
│ │ - GET /health                                │   │
│ │ - POST /auth/start {service: "github"}       │   │
│ │ - POST /session/get {service: "github"}      │   │
│ └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
             ↑
             │
┌─────────────────────────────────────────────────────┐
│ CLI Client (auth-cli)                               │
│ $ auth-cli get github                               │
│ {token: "ghu_...", expires_at: 123456}              │
└─────────────────────────────────────────────────────┘
```

## Data Flow

### Device Code Extraction

```
Terminal Output: "First copy your one-time code: XXXX-XXXX"
                 ↓
Regex Match: [A-Z0-9]{4}-[A-Z0-9]{4}
                 ↓
Extract: XXXX-XXXX
                 ↓
Call Handler: handler.handle_device_code("XXXX-XXXX")
```

### Authentication Flow

```
1. Terminal watcher detects: XXXX-XXXX
2. Call GitHub handler
3. Open browser: github.com/login/device
4. Wait: 2 seconds (page load)
5. Type code: XXXX-XXXX (split by -)
6. Type Enter
7. Wait: 1 second
8. Click: "Authorize" button
9. Wait: Success confirmation
10. Extract token from page/API response
11. Store in SessionManager
12. Cache expires_at
```

### Session Retrieval

```
Client requests: POST /session/get {service: "github"}
                 ↓
SessionManager.get("github")
                 ↓
Check expiry: time.time() < session.expires_at
                 ↓
If valid: return {token, refresh_token, expires_at}
If expired: return 404 (trigger new auth)
```

## Thread Safety

Current design: Single-threaded
- HTTP server runs on main thread
- Terminal watcher blocks on I/O
- Session cache uses pickle (atomic writes)

For concurrent auth flows:
- Use threading.Lock around session cache
- Queue-based callback system (future improvement)

## Security Considerations

### Token Storage

```
~/.cache/auth-daemon/sessions.pkl
Permissions: 0o600 (user read/write only)
Format: Binary pickle (not human-readable)
Encryption: None (rely on user home dir permissions)
```

Could improve:
- Encrypt with user's keychain
- Use SQLite with encryption
- Store only refresh tokens, fetch access tokens on demand

### API Access

```
Bound to: 127.0.0.1:8000 (localhost only)
No auth: Only accessible from same machine
No TLS: Not needed (local only)
```

Safe because:
- No network exposure
- Same user context
- No credential transmission over network

### Accessibility API Risk

- Requires explicit user permission
- Can only interact with UI (can't read arbitrary memory)
- System-controlled (macOS enforces permissions)

## Testing Strategy

### Unit Tests
- Regex patterns: Verify auth codes detected correctly
- Session manager: Expiry, persistence, cache misses
- Service handlers: Token extraction, callback registration
- HTTP endpoints: Request/response format

### Integration Tests (manual)
1. Start daemon
2. Run `gh auth login`
3. Verify browser opens
4. Verify code entered
5. Verify token cached
6. Run `auth-cli get github` → see token

### Edge Cases
- Expired tokens (should return 404)
- Network down (graceful degradation)
- Accessibility API fails (manual fallback)
- Multiple concurrent auth flows (queue-based)

## Future Enhancements

1. **Keyboard Maestro fallback**: For flows too complex for Accessibility API
2. **OCR fallback**: Detect buttons via OCR if element finding fails
3. **Encryption**: Use macOS keychain for token storage
4. **Multi-device sync**: iCloud sync for tokens (with caution)
5. **Web UI**: Dashboard to view/manage cached sessions
6. **Proxy mode**: Act as OAuth proxy for browser extensions
7. **CLI plugins**: Support custom auth flows via plugin system
8. **Metrics**: Prometheus metrics for daemon health
9. **Rate limit detection**: Automatic backoff if GitHub rate-limits
10. **Session refresh**: Automatic token refresh via refresh_token

## Performance

- **Startup**: ~500ms (Python import + Accessibility API init)
- **Auth flow**: ~10-20 seconds (browser open + user action)
- **Token cache hit**: ~50ms (pickle load)
- **HTTP request**: ~5-10ms (local socket, no network)

## Compatibility

- **macOS**: 10.14+ (Accessibility API, osascript)
- **Linux**: Any distro with xdotool and X11/Wayland (Ubuntu, Fedora, Arch, etc)
- **Windows**: 7+ (pyautogui, keyboard automation)
- **Python**: 3.8+ (dataclass, subprocess)
- **Browsers**: Chrome, Safari, Firefox (any app with UI automation support)
- **Services**: Any OAuth/device-flow provider

## Known Limitations

1. **Platform-dependent tools**:
   - macOS: Accessibility API (osascript) - very reliable
   - Linux: xdotool (X11/Wayland) - good, but requires graphical session
   - Windows: pyautogui (optional) - keyboard fallback

2. **Browser-dependent**: Requires browser with UI automation support
   - Works: Chrome, Safari, Firefox (all popular browsers)
   - Doesn't work: Headless browsers (no UI to automate)

3. **Visual element detection**: Relies on button text or accessibility labels
   - Might fail if UI changes
   - Fallback: Manual click

4. **Single browser window**: Works best with one browser instance
   - Multiple windows might confuse automation
   - Future: Implement window discovery

5. **Linux-specific**: Requires X11/Wayland session
   - Doesn't work over SSH without X forwarding
   - Wayland support varies (xdotool works but may be limited)

6. **Windows-specific**: Limited without pyautogui
   - Keyboard-only fallback is less reliable
   - OCR/image recognition not yet implemented

## Conclusion

Auth daemon solves the problem of repetitive OAuth automation with a simple, local solution. It's:

- **Simple**: ~500 lines of Python
- **Safe**: No network exposure, local-only
- **Extensible**: Easy to add services
- **Reliable**: Accessibility API is well-supported
- **Debuggable**: Local HTTP API is easy to inspect

Perfect for power users and CLI tool developers.
