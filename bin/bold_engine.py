#!/usr/bin/env python3
"""
bold2lox – bridge between a Loxone Miniserver (Gen 1) and a Bold Smart Lock.

The Miniserver can only do simple local HTTP GETs (Virtual Output) and weak TLS.
This bridge handles HTTPS + OAuth2 against the Bold cloud and pushes status back
to a Virtual UDP Input on the Miniserver.

Authentication (OAuth2, set-and-forget):
  The engine holds access_token + refresh_token. When the (short-lived) access
  token expires it is refreshed automatically at the token endpoint
  (grant_type=refresh_token). New tokens are written back to settings.json.
  The status daemon also refreshes every keepalive_hours (default 12) so the
  refresh token never sits unused. Every token event goes to auth.log (next to
  settings.json) with a short fingerprint of the token, never the token itself.
  Endpoints:
    Token:  https://api.boldsmartlock.com/v2/oauth/token
    API:    https://api.boldsmartlock.com/{v1,v2}/...
      POST /v1/devices/{id}/remote-activation
      POST /v1/devices/{id}/remote-deactivation
      GET  /v2/effective-device-permissions
      GET  /v1/gateways/{id}/current-status

Usage:
  bold_engine.py activate            # trigger the lock (momentary)
  bold_engine.py deactivate
  bold_engine.py status              # fetch status and push it via UDP to the Miniserver
  bold_engine.py discover [--json]   # list device_id / gateway_id (for the web UI)
  bold_engine.py token               # refresh/check the token (diagnostic)
  bold_engine.py keepalive           # refresh if the last refresh is older than keepalive_hours
  bold_engine.py diagnose            # step-by-step check (token / devices / gateway)

Bootstrap login (OAuth2 authorization code, payload as JSON on stdin):
  # Browser login: https://auth.boldsmartlock.com/?client_id=BoldApp&redirect_uri=boldsmartlock://auth&response_type=code
  # Then take the code from the boldsmartlock://auth?code=... redirect URL:
  echo '{"code":"boldsmartlock://auth?code=..."}'    | bold_engine.py login-exchange

Configuration: settings.json (path via $BOLD2LOX_SETTINGS or the default path).
"""
import contextlib
import fcntl
import hashlib
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SETTINGS_PATH = os.environ.get(
    "BOLD2LOX_SETTINGS",
    "/opt/loxberry/data/plugins/bold2lox/settings.json",
)

DEFAULT_TOKEN_URL = "https://api.boldsmartlock.com/v2/oauth/token"
DEFAULT_API_BASE = "https://api.boldsmartlock.com/v1"
DEFAULT_API_BASE_V2 = "https://api.boldsmartlock.com/v2"
DEFAULT_AUTH_BASE = "https://api.boldsmartlock.com/v2"
# Bold device-type ids (from the lib): 1 = lock, 2 = gateway (Bold Connect).
DEVICE_TYPE_LOCK = 1
DEVICE_TYPE_GATEWAY = 2
# Fixed client credentials of the Bold app. Publicly known / from the app; they let
# the bootstrap login work without registering our own OAuth client, and are used both
# for the authorization-code exchange and for refresh. Source: StefanNienhuis/homebridge-bold.
LEGACY_CLIENT_ID = "BoldApp"
LEGACY_CLIENT_SECRET = "pgJFgnGB87f9ednFiiHygCbf"
# Safety margin: refresh the token before it expires.
EXPIRY_SKEW_SECONDS = 60
# Keepalive: refresh at least this often even if the lock is never used
# (settings key "keepalive_hours", 0 = off). homebridge-bold does it daily.
DEFAULT_KEEPALIVE_HOURS = 12
# After a failed keepalive (network etc.), wait this long before trying again.
KEEPALIVE_RETRY_SECONDS = 15 * 60
# auth.log (token events) is trimmed to the last lines once it grows past the size.
AUTH_LOG_MAX_BYTES = 200_000
AUTH_LOG_KEEP_LINES = 1000
# Who is using the token, for auth.log ("activate", "diagnose", "daemon", ...).
# main() and the daemon set it.
CALLER = "cli"
# Loxone timestamps count seconds since 2009-01-01 00:00:00 UTC, not since 1970.
LOXONE_EPOCH_OFFSET = 1230768000


def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@contextlib.contextmanager
def settings_lock():
    """Exclusive lock for every read-modify-write of settings.json. Shared with the
    web UI (Bold::saveSettings uses PHP flock on the same file; both are flock(2)),
    so a UI save can never overwrite a refresh token the engine just rotated."""
    with open(SETTINGS_PATH + ".lock", "a+") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def save_settings(cfg):
    """Write back atomically and durably. Callers must hold settings_lock().

    fsync before and after the rename: Bold invalidates the old refresh token as
    soon as it issues a new one, so losing the new one to a power cut (SD card)
    would lock the plugin out. The file holds tokens, so it stays 0600.
    """
    tmp = SETTINGS_PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, SETTINGS_PATH)
    dir_fd = os.open(os.path.dirname(SETTINGS_PATH) or ".", os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _short(text, limit=400):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


# Bold rejects requests with "OldAppVersion" when the User-Agent carries no current
# app version. The version is IN the User-Agent (e.g. "Bold/1172" = iOS build 1172);
# there is no separate version header. Default = the real, current app UA (from a live
# capture of the iOS app). If Bold ever raises the minimum version, bump the build
# number here or in the "auth_user_agent" UI field. Extra headers via "auth_headers".
DEFAULT_USER_AGENT = "Bold/1172 CFNetwork/3860.700.1 Darwin/25.6.0"


def _with_common_headers(cfg, headers):
    """Add the User-Agent + configured extra headers (for all Bold calls)."""
    merged = dict(headers)
    merged.setdefault("User-Agent", cfg.get("auth_user_agent") or DEFAULT_USER_AGENT)
    for key, val in (cfg.get("auth_headers") or {}).items():
        merged[key] = val
    return merged


def _raw_request(url, method, headers, data, timeout):
    """Raw HTTP call that returns error bodies instead of raising, so the login
    wizard can display Bold's error messages."""
    req = urllib.request.Request(url, data=data, method=method)
    for key, val in headers.items():
        req.add_header(key, val)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, json.dumps({"error": str(exc.reason)})


# --------------------------------------------------------------------------- #
# OAuth2 token handling
# --------------------------------------------------------------------------- #

def _bold(cfg):
    return cfg.setdefault("bold", {})


def _fingerprint(token):
    """First 6 hex chars of the token's SHA-256. Tells rotated tokens apart in the
    auth log without revealing them."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:6] if token else "-"


def auth_log(event, **fields):
    """Append one line to auth.log next to settings.json, trimmed to the last
    AUTH_LOG_KEEP_LINES lines. Never raises: logging must not get in the way of
    opening the door."""
    path = os.path.join(os.path.dirname(SETTINGS_PATH), "auth.log")
    parts = [time.strftime("%Y-%m-%d %H:%M:%S"), event, f"by={CALLER}"]
    for key, val in fields.items():
        val = str(val)
        parts.append(f"{key}={json.dumps(val) if not val or any(c.isspace() for c in val) else val}")
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(" ".join(parts) + "\n")
        if os.path.getsize(path) > AUTH_LOG_MAX_BYTES:
            with open(path, encoding="utf-8") as fh:
                keep = fh.readlines()[-AUTH_LOG_KEEP_LINES:]
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                fh.writelines(keep)
            os.replace(path + ".tmp", path)
    except OSError:
        pass


def _refresh_access_token(cfg, force=False, reason="expired", max_age=None):
    """Exchange the refresh_token for a fresh access_token and persist the result.
    Returns the new access_token.

    Bold rotates the refresh_token on every refresh, so two processes refreshing
    at the same time (status daemon + trigger/diagnose) would race: the second one
    would send an already-rotated token and get "InvalidRefreshToken". We therefore
    serialise refreshes with an exclusive lock and re-read settings.json inside it,
    so a token another process just obtained is adopted instead of re-refreshed.
    """
    with settings_lock():
        return _refresh_locked(cfg, force, reason, max_age)


def _record_refresh_failure(state, reason, refresh_token, error, relogin=False):
    """Log a failed refresh and persist it in state (caller holds the lock; state=None
    skips persisting). relogin=True marks the refresh token as dead until the next
    login, so the keepalive stops retrying it."""
    error = _short(error, 200)
    auth_log("refresh FAILED", reason=reason, rt=_fingerprint(refresh_token), error=error)
    if state is None:
        return
    sbold = state.setdefault("bold", {})
    sbold["last_error"] = error
    sbold["last_error_at"] = int(time.time())
    if relogin:
        sbold["relogin_required"] = True
    try:
        save_settings(state)
    except OSError:
        pass


def _refresh_locked(cfg, force=False, reason="expired", max_age=None):
    """Actual refresh; must be called while holding the settings lock."""
    # Re-read from disk: another process may have refreshed while we waited, so we
    # always send the newest refresh_token (Bold invalidates rotated ones).
    try:
        fresh = load_settings()
        loaded = True
    except Exception:
        fresh = cfg
        loaded = False
    fresh_bold = fresh.get("bold") or {}
    now = int(time.time())
    recent = max_age is None or now - int(fresh_bold.get("token_refreshed_at", 0)) < max_age
    if (not force and recent
            and fresh_bold.get("access_token")
            and fresh_bold.get("access_token_expiry", 0) > now + EXPIRY_SKEW_SECONDS):
        # Someone else already refreshed - adopt their token instead of racing.
        _bold(cfg).update(fresh_bold)
        return fresh_bold["access_token"]

    # Work on the freshest state so we send the newest refresh_token.
    cfg["bold"] = dict(fresh_bold) or _bold(cfg)
    bold = _bold(cfg)
    token_url = cfg.get("token_url", DEFAULT_TOKEN_URL)
    missing = [k for k in ("client_id", "client_secret", "refresh_token") if not bold.get(k)]
    if missing:
        auth_log("refresh FAILED", reason=reason, error="missing " + ",".join(missing))
        raise SystemExit("Access incomplete – missing: " + ", ".join(missing) + " (Settings).")
    old_rt = bold["refresh_token"]

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": bold["refresh_token"],
        "client_id": bold["client_id"],
        "client_secret": bold["client_secret"],
    }).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    for key, val in _with_common_headers(cfg, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }).items():
        req.add_header(key, val)
    state = fresh if loaded else None
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if "invalid_grant" in detail or "InvalidRefreshToken" in detail:
            _record_refresh_failure(state, reason, old_rt, f"HTTP {exc.code} {detail}", relogin=True)
            raise SystemExit(
                "Token refresh rejected (" + str(exc.code) + "): " + detail +
                " – the refresh token is no longer valid, log in again (Login tab). "
                "Possible causes: the same Bold user signed in somewhere else (Bold "
                "allows only one session per user, so use a dedicated user for this "
                "plugin), a password change, or Bold expired/revoked the token. The "
                "token log on the Settings page shows when it last worked."
            )
        _record_refresh_failure(state, reason, old_rt, f"HTTP {exc.code} {detail}")
        raise SystemExit(f"Token refresh failed HTTP {exc.code}: {detail}")
    except OSError as exc:  # URLError, timeouts and resets while reading the answer
        _record_refresh_failure(state, reason, old_rt, f"network: {getattr(exc, 'reason', exc)}")
        raise SystemExit(f"Network error during token refresh: {getattr(exc, 'reason', exc)}")

    access = payload.get("access_token")
    if not access:
        _record_refresh_failure(state, reason, old_rt, "no access_token in answer")
        raise SystemExit("Token endpoint returned no access_token: " + json.dumps(payload))

    # Persist on the freshly read state so concurrent changes elsewhere survive.
    target = fresh if isinstance(fresh, dict) else cfg
    tbold = target.setdefault("bold", {})
    tbold.update(bold)
    now = int(time.time())
    tbold["access_token"] = access
    tbold["access_token_expiry"] = now + int(payload.get("expires_in", 3600))
    tbold["token_refreshed_at"] = now
    for key in ("relogin_required", "last_error", "last_error_at"):
        tbold.pop(key, None)
    # Bold rotates the refresh_token on every refresh - store the new one.
    if payload.get("refresh_token"):
        tbold["refresh_token"] = payload["refresh_token"]
    save_settings(target)
    auth_log("refresh ok", reason=reason,
             rt=f"{_fingerprint(old_rt)}->{_fingerprint(tbold['refresh_token'])}",
             expires_in=payload.get("expires_in", "?"))
    cfg["bold"] = dict(tbold)
    return access


def get_access_token(cfg, force=False, reason=None, max_age=None):
    """Return a valid access_token; refresh automatically when needed. With max_age
    (seconds) a still-valid token is refreshed too if its last refresh is older
    (keepalive)."""
    bold = _bold(cfg)
    now = int(time.time())
    if (not force and max_age is None
            and bold.get("access_token")
            and bold.get("access_token_expiry", 0) > now + EXPIRY_SKEW_SECONDS):
        return bold["access_token"]
    reason = reason or ("forced" if force else "expired")
    return _refresh_access_token(cfg, force, reason, max_age)


def cmd_keepalive(cfg):
    """Refresh the token once the last successful refresh is older than
    keepalive_hours, independent of the gateway (which most setups can't poll).
    Keeps the refresh token in use, so it can't lapse from inactivity, and notices
    a revoked one within hours instead of at the door. Returns a result dict."""
    bold = _bold(cfg)
    hours = float(cfg.get("keepalive_hours", DEFAULT_KEEPALIVE_HOURS) or 0)
    now = int(time.time())
    if not bold.get("refresh_token"):
        return {"skipped": "no access configured"}
    if hours <= 0:
        return {"skipped": "keepalive disabled"}
    if bold.get("relogin_required"):
        return {"skipped": "refresh token rejected - log in again"}
    max_age = int(hours * 3600)
    if now - int(bold.get("token_refreshed_at", 0)) < max_age:
        return {"skipped": "not due"}
    if now - int(bold.get("last_error_at", 0)) < KEEPALIVE_RETRY_SECONDS:
        return {"skipped": "retrying later after an error"}
    try:
        get_access_token(cfg, reason="keepalive", max_age=max_age)
    except SystemExit as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True}


# --------------------------------------------------------------------------- #
# API-Aufrufe
# --------------------------------------------------------------------------- #

def api_request(cfg, method, path, base=None, _retry=True):
    root = (base or cfg.get("api_base", DEFAULT_API_BASE)).rstrip("/")
    url = root + path
    req = urllib.request.Request(url, method=method)
    for key, val in _with_common_headers(cfg, {
        "Authorization": "Bearer " + get_access_token(cfg),
        "Accept": "application/json",
    }).items():
        req.add_header(key, val)
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            body = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        # 401 despite a fresh token -> try one forced refresh.
        if exc.code == 401 and _retry:
            auth_log("access token rejected (401)", path=path)
            get_access_token(cfg, force=True, reason="401")
            return api_request(cfg, method, path, base=base, _retry=False)
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise SystemExit("401 Unauthorized despite token refresh – check access (Settings).")
        if exc.code == 429:
            raise SystemExit("429 Too Many Requests – Bold API is throttling. Try again later.")
        raise SystemExit(f"HTTP {exc.code} on {method} {path}: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error on {method} {path}: {exc.reason}")


def send_udp(cfg, lines):
    """Send 'key=value' lines to the Miniserver's Virtual UDP Input."""
    ms = cfg.get("miniserver") or {}
    ip, port = ms.get("ip"), ms.get("udp_port")
    if not ip or not port:
        return
    payload = ("\n".join(lines)).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (ip, int(port)))


def _device_id(cfg):
    return _bold(cfg).get("device_id", 0)


def _gateway_id(cfg):
    return _bold(cfg).get("gateway_id", 0)


def _is_error_code(value):
    """Bold returns 2xx with an errorCode field on some failures. Treat only a
    real error value as failure - null/0/"" and the literal strings "None"/"null"
    mean success."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ("", "none", "null", "0")
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def cmd_activate(cfg, deactivate=False):
    verb = "remote-deactivation" if deactivate else "remote-activation"
    status, data = api_request(cfg, "POST", f"/devices/{_device_id(cfg)}/{verb}")
    err = data.get("errorCode") if isinstance(data, dict) else None
    ok = 1 if (200 <= status < 300 and not _is_error_code(err)) else 0
    send_udp(cfg, [
        f"bold_action_ok={ok}",
        # Loxone counts seconds since 2009-01-01, not since 1970.
        f"bold_last_action={int(time.time()) - LOXONE_EPOCH_OFFSET}",
    ])
    # 'response' is included so the UI test shows what Bold actually returned.
    print(json.dumps({"http": status, "ok": ok, "errorCode": err, "response": data}))
    return 0 if ok else 1


def _v2_devices(perms):
    """v2 /effective-device-permissions: list of {permissions, device}.
    Yields (id, name, type_id)."""
    if not isinstance(perms, list):
        return
    for entry in perms:
        dev = (entry or {}).get("device") or {}
        type_id = (((dev.get("model") or {}).get("type") or {}).get("id"))
        yield dev.get("id"), dev.get("name"), type_id


def _fetch_permissions(cfg):
    return api_request(cfg, "GET", "/effective-device-permissions",
                       base=cfg.get("api_base_v2", DEFAULT_API_BASE_V2))


def gateway_status(cfg):
    """Check the Bold Connect. Returns (state, detail) with state in
    'online' | 'offline' | 'unavailable'.

    'unavailable' means the check cannot be performed (no gateway id, or the Bold
    user has no access to the gateway). That is NOT a fault: triggering the lock
    works regardless - only the online feedback is missing.
    """
    gw_id = _gateway_id(cfg)
    if not gw_id:
        return "unavailable", ("optional - no gateway id. Discover only finds the Bold "
                               "Connect if your Bold user has access to it.")
    try:
        _, gw = api_request(cfg, "GET", f"/gateways/{gw_id}/current-status")
    except SystemExit as exc:
        msg = str(exc)
        if "HTTP 403" in msg:
            return "unavailable", (f"optional - no permission for gateway {gw_id}. Invite "
                                   "your Bold user to the Bold Connect to get this status.")
        return "unavailable", f"optional - not available: {_short(msg, 160)}"
    if isinstance(gw, dict) and _is_error_code(gw.get("errorCode")):
        return "offline", "offline / unreachable: " + json.dumps(gw)
    return "online", "online"


def _detect_gateway_id(cfg):
    """Find the gateway (Bold Connect, type 2) in the permissions."""
    _, perms = _fetch_permissions(cfg)
    for dev_id, _name, type_id in _v2_devices(perms):
        if type_id == DEVICE_TYPE_GATEWAY:
            return dev_id
    return 0


def cmd_status(cfg):
    if not _bold(cfg).get("refresh_token"):
        print(json.dumps({"skipped": "no access configured"}))
        return 0
    state, detail = gateway_status(cfg)
    if state == "unavailable":
        # Optional feature - stay quiet instead of spamming the daemon log.
        print(json.dumps({"skipped": detail}))
        return 0
    online = 1 if state == "online" else 0
    send_udp(cfg, [f"bold_gateway_online={online}"])
    print(json.dumps({"pushed": [f"bold_gateway_online={online}"]}))
    return 0


def cmd_discover(cfg, as_json=False):
    _, perms = _fetch_permissions(cfg)
    parsed = list(_v2_devices(perms))
    gateway_id = next((i for i, _n, t in parsed if t == DEVICE_TYPE_GATEWAY), 0)
    # Locks (type 1) are selectable; an unknown type is treated as a lock.
    devices = [
        {"id": i, "name": n, "gatewayId": gateway_id}
        for i, n, t in parsed if t != DEVICE_TYPE_GATEWAY
    ]
    if as_json:
        print(json.dumps({"devices": devices, "gatewayId": gateway_id}))
        return 0
    print("Discovered devices (device_id / name):")
    for dev in devices:
        print(f"  id={dev['id']}  name={dev['name']!r}")
    print(f"Gateway (Bold Connect): {gateway_id or 'not found'}")
    return 0


def cmd_token(cfg):
    """Diagnostic: force a refresh and report the remaining lifetime."""
    get_access_token(cfg, force=True)
    remaining = _bold(cfg).get("access_token_expiry", 0) - int(time.time())
    print(json.dumps({"ok": True, "expires_in_seconds": remaining}))
    return 0


def cmd_diagnose(cfg):
    """Check access step by step, reporting ok + detail per step, so you can see
    what's wrong before touching the Loxone config. Does NOT trigger the lock."""
    steps = []

    # 1) refresh the token from the credentials
    try:
        get_access_token(cfg, force=True)
        rem = _bold(cfg).get("access_token_expiry", 0) - int(time.time())
        steps.append({"name": "Credentials / token", "ok": True,
                      "detail": f"Access token refreshed, valid ~{rem}s"})
    except SystemExit as exc:
        steps.append({"name": "Credentials / token", "ok": False, "detail": str(exc)})
        print(json.dumps({"ok": False, "steps": steps}))
        return 1  # without a token no further steps are possible

    # 2) device list - is the chosen lock visible?
    try:
        _, perms = _fetch_permissions(cfg)
        parsed = list(_v2_devices(perms))
        sel = str(_device_id(cfg))
        found = any(str(i) == sel for i, _n, _t in parsed)
        steps.append({"name": "Device list", "ok": bool(found),
                      "detail": f"{len(parsed)} device(s) visible; device_id {sel} "
                                + ("found" if found else "NOT found – run Discover / pick a lock")})
    except SystemExit as exc:
        steps.append({"name": "Device list", "ok": False, "detail": str(exc)})

    # 3) is the Bold Connect reachable? Optional - triggering works without it.
    try:
        state, detail = gateway_status(cfg)
        if state == "unavailable":
            steps.append({"name": "Bold Connect", "ok": True, "skipped": True, "detail": detail})
        else:
            steps.append({"name": "Bold Connect", "ok": state == "online", "detail": detail})
    except SystemExit as exc:
        steps.append({"name": "Bold Connect", "ok": False, "detail": str(exc)})

    ok_all = all(s["ok"] for s in steps)
    print(json.dumps({"ok": ok_all, "steps": steps}))
    return 0 if ok_all else 1


# --------------------------------------------------------------------------- #
# Bootstrap login (OAuth2 authorization code, like the current Bold app)
# --------------------------------------------------------------------------- #
# Flow: the user signs in in the browser at
#   https://auth.boldsmartlock.com/?client_id=BoldApp&redirect_uri=boldsmartlock://auth&response_type=code
# Bold redirects to  boldsmartlock://auth?code=<CODE>. The code is exchanged here for
# access/refresh getauscht. Client-Credentials = feste BoldApp-Werte -> Refresh
# afterwards self-contained with the same credentials.

BOLD_REDIRECT_URI = "boldsmartlock://auth"


def _extract_code(raw):
    """Accept either the bare code or the full
    'boldsmartlock://auth?code=...' redirect URL."""
    raw = (raw or "").strip()
    if "code=" in raw:
        raw = raw.split("code=", 1)[1].split("&", 1)[0]
    return urllib.parse.unquote(raw)


def cmd_login_exchange(cfg, payload):
    """Exchange the authorization code for access/refresh and store them, together
    with the BoldApp client credentials, in settings.json."""
    code = _extract_code(payload.get("code", ""))
    if not code:
        print(json.dumps({"ok": False, "detail": "no code provided"}))
        return 1
    url = cfg.get("token_url", DEFAULT_TOKEN_URL)
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": LEGACY_CLIENT_ID,
        "client_secret": LEGACY_CLIENT_SECRET,
        "redirect_uri": cfg.get("redirect_uri", BOLD_REDIRECT_URI),
        "code": code,
    }).encode("utf-8")
    st, txt = _raw_request(url, "POST",
                           _with_common_headers(cfg, {"Content-Type": "application/x-www-form-urlencoded",
                                                      "Accept": "application/json"}),
                           form, cfg.get("http_timeout_seconds", 15))
    if not (200 <= st < 300):
        auth_log("login FAILED", http=st, error=_short(txt, 200))
        print(json.dumps({"ok": False, "status": st, "detail": _short(txt)}))
        return 1
    body = json.loads(txt or "{}") or {}
    if not body.get("access_token") or not body.get("refresh_token"):
        auth_log("login FAILED", error="no tokens received")
        print(json.dumps({"ok": False, "detail": "no tokens received: " + _short(txt)}))
        return 1
    with settings_lock():
        # Re-read under the lock: cfg was loaded before the HTTP round trip, and a UI
        # save or a refresh may have written settings.json since then.
        cfg = load_settings()
        bold = _bold(cfg)
        now = int(time.time())
        bold["client_id"] = LEGACY_CLIENT_ID
        bold["client_secret"] = LEGACY_CLIENT_SECRET
        bold["refresh_token"] = body["refresh_token"]
        bold["access_token"] = body["access_token"]
        bold["access_token_expiry"] = now + int(body.get("expires_in", 3600))
        bold["token_refreshed_at"] = now
        for key in ("relogin_required", "last_error", "last_error_at"):
            bold.pop(key, None)
        if body.get("account_id"):
            bold["account_id"] = body["account_id"]
        save_settings(cfg)
        auth_log("login ok", rt=_fingerprint(body["refresh_token"]),
                 expires_in=body.get("expires_in", "?"))
    print(json.dumps({"ok": True}))
    return 0


def main(argv):
    global CALLER
    action = argv[1] if len(argv) > 1 else ""
    login_actions = {"login-exchange"}
    known = ({"activate", "deactivate", "status", "discover", "token", "diagnose", "keepalive"}
             | login_actions)
    if action not in known:
        print(__doc__)
        return 2
    CALLER = action
    cfg = load_settings()
    if action == "keepalive":
        result = cmd_keepalive(cfg)
        print(json.dumps(result))
        return 1 if result.get("ok") is False else 0
    if action in login_actions:
        payload = json.load(sys.stdin)  # code comes via stdin, not argv
        if action == "login-exchange":
            return cmd_login_exchange(cfg, payload)
    if action == "activate":
        return cmd_activate(cfg)
    if action == "deactivate":
        return cmd_activate(cfg, deactivate=True)
    if action == "status":
        return cmd_status(cfg)
    if action == "discover":
        return cmd_discover(cfg, as_json=("--json" in argv))
    if action == "token":
        return cmd_token(cfg)
    if action == "diagnose":
        return cmd_diagnose(cfg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
