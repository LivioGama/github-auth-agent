<div align="center">

# 🔐 GitHub Auth Agent

**Skip the `gh auth login` dance.** Press ⌘G; a menu-bar app OCRs the device code off your screen, drives `agent-browser` against `github.com/login/device`, and clicks **Authorize** for you. ✨

![macOS](https://img.shields.io/badge/macOS-12%2B-000?logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?logo=python&logoColor=white)
![GitHub](https://img.shields.io/badge/Auth-Device%20flow-181717?logo=github&logoColor=white)

<video src="https://github.com/user-attachments/assets/95e1d3fd-9b92-4904-8095-9cfdaf1ef9a0" controls autoplay muted playsinline width="720"></video>

</div>

---

## 🚀 Quickstart

```bash
# 1. install
git clone git@github.com:LivioGama/github-auth-agent.git
cd github-auth-agent
bash scripts/install.sh

# 2. capture a GitHub session (one-time, manual login)
agent-browser --state ~/.config/auth-daemon/github-auth.json \
              open https://github.com/login

# 3. run
open /Applications/GitHubAuthAgent.app
```

Then in any shell, run `gh auth login`, leave the device code on screen, and press **⌘G**. 🎉

---

## 🤔 How it works

Press **⌘G** anywhere → Apple Vision OCRs your visible screen and finds the `XXXX-XXXX` code near GitHub context → the daemon drives `agent-browser` (with saved cookies) → fills the 8 boxes → clicks **Authorize** → 🔔 notification.

---

## 🔓 Permissions

On first launch the agent checks for these and pops a native dialog with an **Open Settings** button for whatever's missing:

| Pane | Why |
|---|---|
| 🦾 Accessibility | catch ⌘G globally |
| 📺 Screen Recording | OCR your screen |
| 🔔 Notifications | enable **GitHub Auth Agent** when prompted |

Find **GitHub Auth Agent** in each list and toggle it on. 🪄

---

## 🍔 Menu-bar app

Click the GitHub icon in the menu bar:

- 🪵 **Open Logs in Terminal** — `tail -f` the daemon log
- 👋 **Quit** — kills the daemon and exits

---

## 🏗️ Layout

```
github-auth-agent/
├── src/{auth_daemon,auth_cli}.py
├── scripts/{install,setup-shell-hook,device-code-hook}.sh
├── assets/{github-mark.png, GitHubAuthAgent.app/}
├── pyproject.toml  Makefile  README.md
```

Runtime state:

| Path | Purpose |
|---|---|
| `/Applications/GitHubAuthAgent.app` | menu-bar app |
| `~/Library/Logs/GitHub Auth Agent/auth-daemon.log` | log |
| `~/.config/auth-daemon/github-auth.json` | saved GitHub cookies (mode `0600`) |

---

## 🐛 Troubleshooting

| Symptom | Fix |
|---|---|
| ⌘G does nothing | Grant Accessibility to `python3`. |
| No notifications | Toggle **GitHub Auth Agent** on under Notifications; disable Focus. |
| `reason=not_found` / `expired` | Code already used or aged out — rerun `gh auth login`. |
| `No GitHub session at …` | Skipped the cookie-capture step. |

📜 `tail -f ~/Library/Logs/GitHub\ Auth\ Agent/auth-daemon.log` or use the menu-bar **Logs** item.

---

## 📄 License

MIT — see [LICENSE](LICENSE). Bundles a re-skinned [terminal-notifier](https://github.com/julienXX/terminal-notifier) (MIT) for native notifications.
