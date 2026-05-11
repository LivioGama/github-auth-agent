Yes. The cleanest approach is to treat the OAuth/device-flow login like an OS automation problem, not a browser automation problem.

Most CLI auth systems like GitHub GitHub Copilot use one of these:

1. Device Flow (copy code + open URL)
2. Localhost callback OAuth (http://127.0.0.1:PORT/callback)
3. Custom URI scheme (vscode://...)

Copilot CLI / extensions mainly use device flow.

The best architecture on macOS is:

I. Intercept the auth flow at OS level
II. Auto-open/fill browser session
III. Auto-confirm using existing GitHub cookies/session
IV. Return token to CLI automatically

You do NOT want Selenium/Playwright for this. Too slow and fragile.

You want:

* AppleScript
* Shortcuts
* Accessibility API
* UI automation
* maybe Hammerspoon
* maybe UI-TARS for fallback visual targeting

The serious stack is:

* Hammerspoon
    https://github.com/Hammerspoon/hammerspoon
* yabai if you want workspace/window control
    https://github.com/koekeishiya/yabai
* Karabiner-Elements for triggers
    https://github.com/pqrs-org/Karabiner-Elements
* Accessibility API (AXUIElement)
* Optional:
    UI-TARS-desktop
    https://github.com/bytedance/UI-TARS-desktop

The real trick:
You do not automate GitHub auth itself.
You automate:

* detecting the login code
* opening the auth URL
* clicking authorize
* waiting for success
* closing tab/window

Example flow:

gh auth login

CLI outputs:

First copy your one-time code: XXXX-XXXX
Press Enter to open github.com/login/device

Your automation layer:

* watches terminal output
* regex extracts device code
* automatically opens browser
* injects code
* presses authorize
* returns focus to terminal

You can do this with:

script -q /tmp/session.log gh auth login

Then tail logs:

tail -f /tmp/session.log

Regex detect:

[A-Z0-9]{4}-[A-Z0-9]{4}

Then trigger AppleScript.

Minimal viable architecture:

Terminal Output Watcher
    ↓
Regex Extractor
    ↓
Browser Automation
    ↓
Accessibility API Clicks
    ↓
Token Success Detection

The most robust implementation today is probably:

* Python watcher
* macOS Accessibility API
* AppleScript for browser control
* Optional OCR fallback
* Optional UI-TARS fallback

NOT Puppeteer.

For browser/session reuse:
Use your already logged-in GitHub profile.

Example AppleScript:

tell application "Google Chrome"
    activate
    open location "https://github.com/login/device"
end tell

Then use:

* JavaScript injection
* Accessibility API
* or Keyboard Maestro

Honestly, Keyboard Maestro is probably the fastest production-ready solution:
https://www.keyboardmaestro.com/main/

Because it can:

* watch terminal text
* detect regex
* manipulate browser
* click buttons
* wait for images/text
* run scripts
* run indefinitely

This is exactly the kind of “human desktop middleware” it excels at.

If you want ultra-serious fully autonomous auth automation:

Agent
 ├── terminal watcher
 ├── browser controller
 ├── cookie/session manager
 ├── OCR fallback
 ├── visual detector
 └── auth state validator

At that point you are basically building:

* a local Computer Use agent
* specialized for OAuth/device-flow auth

The extremely important detail:
GitHub aggressively rate-limits suspicious auth behavior.

So:

* DO NOT create fresh browser sessions
* DO NOT use headless browsers
* DO NOT rotate fingerprints
* DO NOT automate login credentials

Instead:
reuse your already authenticated browser profile.

That’s the stable path.

If you want the “operator-grade” solution:
build a tiny local daemon:

copilot-auth-agent

Responsibilities:

* detect auth prompts
* orchestrate browser
* confirm success
* cache sessions
* expose local socket/API

Then every tool:

* Claude Code
* OpenCode
* Gemini CLI
* Copilot CLI
* custom agents

can delegate auth to the same local auth broker.

This becomes VERY powerful once you manage:

* GitHub
* Google
* Anthropic
* OpenAI
* Slack
* Linear
* Atlassian

centrally.