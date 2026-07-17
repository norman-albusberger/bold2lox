#!/usr/bin/env python3
"""
bold2lox – Bruecke zwischen Loxone Miniserver (Gen 1) und Bold Smart Lock.

Der Miniserver kann nur einfache lokale HTTP-GETs (Virtual Output) und schwaches
TLS. Diese Bruecke uebernimmt HTTPS + OAuth2 gegen die Bold-Cloud und schiebt den
Status per UDP an einen Virtual UDP Input im Miniserver zurueck.

Authentifizierung (OAuth2, set-and-forget):
  Der Engine haelt access_token + refresh_token. Laeuft der (kurzlebige)
  access_token ab, wird er automatisch am Token-Endpoint erneuert
  (grant_type=refresh_token). Neue Tokens werden zurueck in settings.json
  geschrieben. Endpoints bestaetigt aus lwestenberg/homeassistant_bold:
    Token:  https://api.boldsmartlock.com/v2/oauth/token
    API:    https://api.boldsmartlock.com/v1/...
      POST /v1/devices/{id}/remote-activation
      POST /v1/devices/{id}/remote-deactivation
      GET  /v1/effective-device-permissions
      GET  /v1/gateways/{id}/current-status

Aufruf:
  bold_engine.py activate            # Schloss ausloesen (momentan)
  bold_engine.py deactivate
  bold_engine.py status              # Status holen und per UDP an den Miniserver
  bold_engine.py discover [--json]   # device_id / gateway_id auflisten (fuer die Web-UI)
  bold_engine.py token               # Token erneuern/pruefen (Diagnose)
  bold_engine.py diagnose            # Schritt-fuer-Schritt-Check (Token/Geraete/Gateway)

Bootstrap-Login (OAuth2 Authorization Code, Payload als JSON ueber stdin):
  # Browser-Login: https://auth.boldsmartlock.com/?client_id=BoldApp&redirect_uri=boldsmartlock://auth&response_type=code
  # Danach den Code aus der boldsmartlock://auth?code=... Redirect-URL nehmen:
  echo '{"code":"boldsmartlock://auth?code=..."}'    | bold_engine.py login-exchange

Konfiguration: settings.json (Pfad via $BOLD2LOX_SETTINGS oder Standardpfad).
"""
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
# Bold device-type ids (aus der Lib): 1 = Schloss, 2 = Gateway (Bold Connect).
DEVICE_TYPE_LOCK = 1
DEVICE_TYPE_GATEWAY = 2
# Feste Client-Credentials der Bold-App fuer den Legacy-Login (username/password +
# SMS/E-Mail-Code). Oeffentlich bekannt/aus der App; erlaubt Bootstrap ohne eigene
# OAuth-Registrierung. Quelle: StefanNienhuis/homebridge-bold.
LEGACY_CLIENT_ID = "BoldApp"
LEGACY_CLIENT_SECRET = "pgJFgnGB87f9ednFiiHygCbf"
# Sicherheitspuffer: Token vor Ablauf erneuern.
EXPIRY_SKEW_SECONDS = 60


def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_settings(cfg):
    """Atomar zurueckschreiben (erneuerte Tokens persistieren)."""
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, SETTINGS_PATH)


def _short(text, limit=400):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


# Bold weist den Password-Grant mit "OldAppVersion" ab, wenn der User-Agent keine
# aktuelle App-Version traegt. Die App-Version steckt IM User-Agent (z. B.
# "Bold/1172" = iOS-Build 1172); einen separaten Versions-Header gibt es nicht.
# Default = echter, aktueller App-UA (aus einem Live-Mitschnitt der iOS-App).
# Wird Bold die Mindestversion irgendwann anheben, hier bzw. im UI-Feld
# "auth_user_agent" die aktuelle Build-Nummer nachziehen. Zusatz-Header via
# "auth_headers".
DEFAULT_USER_AGENT = "Bold/1172 CFNetwork/3860.700.1 Darwin/25.6.0"


def _with_common_headers(cfg, headers):
    """Ergaenzt User-Agent + konfigurierte Zusatz-Header (fuer alle Bold-Calls)."""
    merged = dict(headers)
    merged.setdefault("User-Agent", cfg.get("auth_user_agent") or DEFAULT_USER_AGENT)
    for key, val in (cfg.get("auth_headers") or {}).items():
        merged[key] = val
    return merged


def _raw_request(url, method, headers, data, timeout):
    """Roher HTTP-Aufruf, der Fehlerbodies zurueckgibt statt zu werfen –
    damit der Login-Wizard Bold-Fehlermeldungen anzeigen kann."""
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
# OAuth2 Token-Handling
# --------------------------------------------------------------------------- #

def _bold(cfg):
    return cfg.setdefault("bold", {})


def _refresh_access_token(cfg):
    """Tauscht den refresh_token gegen einen frischen access_token und
    persistiert das Ergebnis. Gibt den neuen access_token zurueck."""
    bold = _bold(cfg)
    token_url = cfg.get("token_url", DEFAULT_TOKEN_URL)
    missing = [k for k in ("client_id", "client_secret", "refresh_token") if not bold.get(k)]
    if missing:
        raise SystemExit("Zugang unvollstaendig – fehlt: " + ", ".join(missing) + " (Einstellungen).")

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
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code in (400, 401):
            raise SystemExit(
                "Token-Refresh abgelehnt (" + str(exc.code) + "): " + detail +
                " – refresh_token vermutlich ungueltig/widerrufen. Bitte neu autorisieren."
            )
        raise SystemExit(f"Token-Refresh fehlgeschlagen HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Netzwerkfehler beim Token-Refresh: {exc.reason}")

    access = payload.get("access_token")
    if not access:
        raise SystemExit("Token-Endpoint lieferte keinen access_token: " + json.dumps(payload))
    bold["access_token"] = access
    bold["access_token_expiry"] = int(time.time()) + int(payload.get("expires_in", 3600))
    # Manche Provider rotieren den refresh_token bei jedem Refresh mit.
    if payload.get("refresh_token"):
        bold["refresh_token"] = payload["refresh_token"]
    save_settings(cfg)
    return access


def get_access_token(cfg, force=False):
    """Liefert einen gueltigen access_token; erneuert bei Bedarf automatisch."""
    bold = _bold(cfg)
    now = int(time.time())
    if (not force
            and bold.get("access_token")
            and bold.get("access_token_expiry", 0) > now + EXPIRY_SKEW_SECONDS):
        return bold["access_token"]
    return _refresh_access_token(cfg)


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
        # 401 trotz frischem Token -> einmal erzwungenen Refresh versuchen.
        if exc.code == 401 and _retry:
            get_access_token(cfg, force=True)
            return api_request(cfg, method, path, base=base, _retry=False)
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise SystemExit("401 Unauthorized trotz Token-Refresh – Zugang pruefen (Einstellungen).")
        if exc.code == 429:
            raise SystemExit("429 Too Many Requests – Bold-API drosselt. Spaeter erneut.")
        raise SystemExit(f"HTTP {exc.code} bei {method} {path}: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Netzwerkfehler bei {method} {path}: {exc.reason}")


def send_udp(cfg, lines):
    """Schickt 'key=value'-Zeilen an den Virtual UDP Input des Miniservers."""
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


def cmd_activate(cfg, deactivate=False):
    verb = "remote-deactivation" if deactivate else "remote-activation"
    status, data = api_request(cfg, "POST", f"/devices/{_device_id(cfg)}/{verb}")
    err = data.get("errorCode") if isinstance(data, dict) else None
    ok = 1 if (200 <= status < 300 and not err) else 0
    send_udp(cfg, [f"bold_last_action={int(time.time())}", f"bold_action_ok={ok}"])
    print(json.dumps({"http": status, "ok": ok, "errorCode": err}))
    return 0 if ok else 1


def _v2_devices(perms):
    """v2 /effective-device-permissions: Liste von {permissions, device}.
    Liefert je (id, name, type_id)."""
    if not isinstance(perms, list):
        return
    for entry in perms:
        dev = (entry or {}).get("device") or {}
        type_id = (((dev.get("model") or {}).get("type") or {}).get("id"))
        yield dev.get("id"), dev.get("name"), type_id


def _fetch_permissions(cfg):
    return api_request(cfg, "GET", "/effective-device-permissions",
                       base=cfg.get("api_base_v2", DEFAULT_API_BASE_V2))


def _detect_gateway_id(cfg):
    """Sucht das Gateway (Bold Connect, Typ 2) in den Permissions."""
    _, perms = _fetch_permissions(cfg)
    for dev_id, _name, type_id in _v2_devices(perms):
        if type_id == DEVICE_TYPE_GATEWAY:
            return dev_id
    return 0


def cmd_status(cfg):
    if not _bold(cfg).get("refresh_token") or not _gateway_id(cfg):
        print(json.dumps({"skipped": "zugang/gateway fehlt"}))
        return 0
    _, gw = api_request(cfg, "GET", f"/gateways/{_gateway_id(cfg)}/current-status")
    online = 1 if not (isinstance(gw, dict) and gw.get("errorCode")) else 0
    send_udp(cfg, [f"bold_gateway_online={online}"])
    print(json.dumps({"pushed": [f"bold_gateway_online={online}"]}))
    return 0


def cmd_discover(cfg, as_json=False):
    _, perms = _fetch_permissions(cfg)
    parsed = list(_v2_devices(perms))
    gateway_id = next((i for i, _n, t in parsed if t == DEVICE_TYPE_GATEWAY), 0)
    # Schloesser (Typ 1) sind auswaehlbar; unbekannter Typ wird als Schloss gewertet.
    devices = [
        {"id": i, "name": n, "gatewayId": gateway_id}
        for i, n, t in parsed if t != DEVICE_TYPE_GATEWAY
    ]
    if as_json:
        print(json.dumps({"devices": devices, "gatewayId": gateway_id}))
        return 0
    print("Gefundene Geraete (device_id / name):")
    for dev in devices:
        print(f"  id={dev['id']}  name={dev['name']!r}")
    print(f"Gateway (Bold Connect): {gateway_id or 'nicht gefunden'}")
    return 0


def cmd_token(cfg):
    """Diagnose: erzwingt einen Refresh und meldet die Restlaufzeit."""
    get_access_token(cfg, force=True)
    remaining = _bold(cfg).get("access_token_expiry", 0) - int(time.time())
    print(json.dumps({"ok": True, "expires_in_seconds": remaining}))
    return 0


def cmd_diagnose(cfg):
    """Prueft Zugang Schritt fuer Schritt und meldet je Schritt ok + Detail –
    damit man vor der Loxone-Config sofort sieht, woran es haengt. Loest das
    Schloss NICHT aus."""
    steps = []

    # 1) Token aus den Zugangsdaten erneuern
    try:
        get_access_token(cfg, force=True)
        rem = _bold(cfg).get("access_token_expiry", 0) - int(time.time())
        steps.append({"name": "Zugangsdaten / Token", "ok": True,
                      "detail": f"Access-Token erneuert, gueltig ~{rem}s"})
    except SystemExit as exc:
        steps.append({"name": "Zugangsdaten / Token", "ok": False, "detail": str(exc)})
        print(json.dumps({"ok": False, "steps": steps}))
        return 1  # ohne Token keine weiteren Schritte moeglich

    # 2) Geraeteliste – ist das gewaehlte Schloss sichtbar?
    try:
        _, perms = _fetch_permissions(cfg)
        parsed = list(_v2_devices(perms))
        sel = str(_device_id(cfg))
        found = any(str(i) == sel for i, _n, _t in parsed)
        steps.append({"name": "Geraeteliste", "ok": bool(found),
                      "detail": f"{len(parsed)} Geraet(e) sichtbar; device_id {sel} "
                                + ("gefunden" if found else "NICHT gefunden – bitte Discover/Schloss waehlen")})
    except SystemExit as exc:
        steps.append({"name": "Geraeteliste", "ok": False, "detail": str(exc)})

    # 3) Bold Connect erreichbar?
    try:
        gw_id = _gateway_id(cfg)
        if not gw_id:
            steps.append({"name": "Bold Connect", "ok": False, "detail": "keine gateway_id gesetzt"})
        else:
            _, gw = api_request(cfg, "GET", f"/gateways/{gw_id}/current-status")
            online = not (isinstance(gw, dict) and gw.get("errorCode"))
            steps.append({"name": "Bold Connect", "ok": bool(online),
                          "detail": "online" if online else "offline/unerreichbar: " + json.dumps(gw)})
    except SystemExit as exc:
        steps.append({"name": "Bold Connect", "ok": False, "detail": str(exc)})

    ok_all = all(s["ok"] for s in steps)
    print(json.dumps({"ok": ok_all, "steps": steps}))
    return 0 if ok_all else 1


# --------------------------------------------------------------------------- #
# Bootstrap-Login (OAuth2 Authorization Code, wie die aktuelle Bold-App)
# --------------------------------------------------------------------------- #
# Flow: Nutzer meldet sich im Browser an unter
#   https://auth.boldsmartlock.com/?client_id=BoldApp&redirect_uri=boldsmartlock://auth&response_type=code
# Bold leitet auf  boldsmartlock://auth?code=<CODE>  um. Der Code wird hier gegen
# access/refresh getauscht. Client-Credentials = feste BoldApp-Werte -> Refresh
# danach self-contained mit denselben Credentials.

BOLD_REDIRECT_URI = "boldsmartlock://auth"


def _extract_code(raw):
    """Akzeptiert entweder den nackten Code oder die volle
    'boldsmartlock://auth?code=...'-Redirect-URL."""
    raw = (raw or "").strip()
    if "code=" in raw:
        raw = raw.split("code=", 1)[1].split("&", 1)[0]
    return urllib.parse.unquote(raw)


def cmd_login_exchange(cfg, payload):
    """Tauscht den Authorization-Code gegen access/refresh und legt sie samt der
    BoldApp-Client-Credentials in settings.json ab."""
    code = _extract_code(payload.get("code", ""))
    if not code:
        print(json.dumps({"ok": False, "detail": "kein Code angegeben"}))
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
        print(json.dumps({"ok": False, "status": st, "detail": _short(txt)}))
        return 1
    body = json.loads(txt or "{}") or {}
    if not body.get("access_token") or not body.get("refresh_token"):
        print(json.dumps({"ok": False, "detail": "keine Tokens erhalten: " + _short(txt)}))
        return 1
    bold = _bold(cfg)
    bold["client_id"] = LEGACY_CLIENT_ID
    bold["client_secret"] = LEGACY_CLIENT_SECRET
    bold["refresh_token"] = body["refresh_token"]
    bold["access_token"] = body["access_token"]
    bold["access_token_expiry"] = int(time.time()) + int(body.get("expires_in", 3600))
    if body.get("account_id"):
        bold["account_id"] = body["account_id"]
    save_settings(cfg)
    print(json.dumps({"ok": True}))
    return 0


def main(argv):
    action = argv[1] if len(argv) > 1 else ""
    login_actions = {"login-exchange"}
    known = {"activate", "deactivate", "status", "discover", "token", "diagnose"} | login_actions
    if action not in known:
        print(__doc__)
        return 2
    cfg = load_settings()
    if action in login_actions:
        payload = json.load(sys.stdin)  # Code kommt ueber stdin, nicht argv
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
