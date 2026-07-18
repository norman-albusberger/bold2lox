# bold2lox – Bold Smart Lock for Loxone

LoxBerry plugin that lets you operate a **Bold Smart Lock** from the **Loxone app**.
The Miniserver (including **Gen 1**) only fires a simple local HTTP GET; the LoxBerry
does HTTPS + OAuth2 against the Bold cloud, which triggers the lock through your
**Bold Connect** (the socket bridge).

```
Loxone app → Miniserver (Virtual Output, HTTP GET) → LoxBerry activate.php
          → bold_engine.py → HTTPS → Bold cloud → Bold Connect → lock
Status:   Bold cloud → bold2lox.service (poller) → UDP → Miniserver (Virtual UDP Input) → app
```

## Installation

Install as a LoxBerry plugin (ZIP via the LoxBerry plugin manager, or auto-update via
`release.cfg`). During setup these run automatically:

- `preinstall.sh` – checks for `python3`.
- `postroot.sh` – creates the systemd service `bold2lox.service` (status poller).
- `uninstall/uninstall` – stops/removes the service and cleans data/logs.

Requirements: LoxBerry ≥ 3.0, a **Bold Connect** in the home, and a **Bold account**.

## Setup (LoxBerry web menu → bold2lox)

1. **Login** tab: "Open Bold login" → sign in in the browser → paste the
   `boldsmartlock://auth?code=…` result back into the plugin (see below).
2. **Settings** tab: the lock dropdown loads from your account (**Discover**). Pick your
   lock → `device_id`/`gateway_id` are set. Generate a **trigger secret**, enter the
   **Miniserver IP** + **UDP port**, and save.
3. Under **Test connection**, run "Run diagnosis" (checks token / device / Bold Connect)
   and optionally "Open lock now (test)".
4. On **Overview**, download the ready-made Loxone templates or copy the Virtual Output URLs.

## Authentication (OAuth2, set-and-forget)

Bold uses **OAuth2**: a **short-lived** access token per request, renewed via a
**long-lived refresh token**. The plugin stores both and **refreshes the access token
automatically** at the token endpoint (`grant_type=refresh_token`) when it expires — so:
set it up once, and it keeps working.

**First sign-in – in the plugin, no external tools** (Login tab), exactly the OAuth2
authorization-code flow the Bold app uses:

1. **"Open Bold login"** → Bold's sign-in page opens (password or Apple/Google/Microsoft).
   Best in a **desktop browser without the Bold app installed**.
2. After signing in, the browser tries to open `boldsmartlock://auth?code=…` and shows an
   error – that is expected. Copy the **whole URL** (or just `code=…`) from the address bar.
3. Paste it into the plugin → it exchanges the code for an access + refresh token
   (`grant_type=authorization_code`, fixed `BoldApp` credentials) and stores them in
   `settings.json`.

After that the auto-refresh takes over (`grant_type=refresh_token`, same credentials) —
**self-contained, no third-party server, never repeat it**. The code is single-use and
short-lived, so paste it right after signing in. The `BoldApp` credentials and the
`User-Agent` (a version gate, see below) come from a live capture of the Bold app.

> History: Bold disabled the old password login (`grant_type=password`, error
> `OldAppVersion`); the app now uses the authorization-code flow above.

If the refresh token becomes invalid (password change, revocation, long inactivity), just
run the Login tab again. Diagnostic: `bold_engine.py token` forces a refresh and reports
the remaining lifetime.

## Loxone Config

**Easiest – ready-made `.LxAddOn` templates** (Overview tab → downloads), imported in
Loxone Config via **"Device Templates → Import template…"**. They are pre-filled with your
IP, trigger secret and UDP port, so finish the setup first. Two files, because one
`.LxAddOn` can only contain inputs **or** outputs:

- `bold2lox-output.LxAddOn` – Virtual Output: trigger the lock (open/close)
- `bold2lox-status.LxAddOn` – Virtual UDP Input: status

**Or by hand:**

*Control (app button → lock):*
1. **Virtual Output**, address `http://<loxberry-ip>` (port 80).
2. **Virtual Output Command**, *ON:*
   `/plugins/bold2lox/activate.php?key=SECRET&cmd=open` (GET).
3. Connect it to a **push-button** and place it in the app. Optional *OFF:*
   `cmd=close` for `remote-deactivation`.

*Feedback (status → app):*
1. **Virtual UDP Input** on the port chosen in Settings.
2. Command-recognition entries:
   `bold_gateway_online=\v`, `bold_action_ok=\v`, `bold_last_action=\v`.

## Layout (plugin folder → target paths on the LoxBerry)

| Repo                                | Target (`bold2lox` plugin)                                   |
| ----------------------------------- | ----------------------------------------------------------- |
| `plugin.cfg`, `*.sh`, `uninstall/`  | Plugin root / LoxBerry lifecycle                            |
| `bin/bold_engine.py`                | `$LBPBIN/bold2lox/` – core (activate/status/discover)       |
| `bin/bold2lox-daemon`               | `$LBPBIN/bold2lox/` – status poller (systemd)               |
| `webfrontend/htmlauth/*`            | Web UI (Overview/Login/Settings/About)                      |
| `webfrontend/html/activate.php`     | **unauth.** trigger for the Miniserver                      |
| `data/settings.json`                | `$LBPDATA/bold2lox/` – runtime config (tokens etc.)         |
| `templates/lang/language_en.ini`    | Language file                                               |

## Design decisions

- **No persistent open/closed state** – Bold is a momentary cylinder; the app shows
  "last activated" + online, not "locked/unlocked".
- **Feedback via raw UDP** – version-independent, no MQTT needed.
- **OAuth2 with auto-refresh** – the engine renews the short-lived access token on its
  own; only the one-time first authorization is manual.

## Confirmed Bold API endpoints

`https://api.boldsmartlock.com` –
`POST /v1/devices/{id}/remote-activation`,
`POST /v1/devices/{id}/remote-deactivation`,
`GET /v2/effective-device-permissions`,
`GET /v1/gateways/{id}/current-status`,
token/refresh/login `POST /v2/oauth/token`
(sources: [bold_smart_lock](https://github.com/lwestenberg/bold_smart_lock),
[homeassistant_bold](https://github.com/lwestenberg/homeassistant_bold),
[homebridge-bold](https://github.com/StefanNienhuis/homebridge-bold)).

## Test / diagnostics (web UI)

- **Login tab**: OAuth sign-in (open Bold login → paste the redirect code).
- **Settings → Test connection**: "Run diagnosis" checks token / device / Bold Connect
  step by step (without triggering); "Open lock now (test)" actually activates the lock.
- CLI: `bold_engine.py diagnose` or `bold_engine.py token`.
