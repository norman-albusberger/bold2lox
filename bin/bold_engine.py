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
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
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

def api_request(cfg, method, path, _retry=True):
    url = cfg.get("api_base", DEFAULT_API_BASE).rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer " + get_access_token(cfg))
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            body = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        # 401 trotz frischem Token -> einmal erzwungenen Refresh versuchen.
        if exc.code == 401 and _retry:
            get_access_token(cfg, force=True)
            return api_request(cfg, method, path, _retry=False)
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


def _iter_devices(perms):
    """Permissions-Antwort: Liste von Locations mit 'devices' (oder dict)."""
    if isinstance(perms, list):
        for loc in perms:
            for dev in (loc.get("devices") or []):
                yield dev
    elif isinstance(perms, dict):
        for dev in (perms.get("devices") or []):
            yield dev


def cmd_status(cfg):
    if not _bold(cfg).get("refresh_token") or not _gateway_id(cfg):
        print(json.dumps({"skipped": "zugang/gateway fehlt"}))
        return 0
    _, gw = api_request(cfg, "GET", f"/gateways/{_gateway_id(cfg)}/current-status")
    online = 1 if not (isinstance(gw, dict) and gw.get("errorCode")) else 0
    lines = [f"bold_gateway_online={online}"]
    _, perms = api_request(cfg, "GET", "/effective-device-permissions")
    for dev in _iter_devices(perms):
        if str(dev.get("id")) == str(_device_id(cfg)):
            if dev.get("batteryLevel") is not None:
                lines.append(f"bold_battery={dev['batteryLevel']}")
            break
    send_udp(cfg, lines)
    print(json.dumps({"pushed": lines}))
    return 0


def cmd_discover(cfg, as_json=False):
    _, perms = api_request(cfg, "GET", "/effective-device-permissions")
    devices = [
        {"id": dev.get("id"), "name": dev.get("name"), "gatewayId": dev.get("gatewayId")}
        for dev in _iter_devices(perms)
    ]
    if as_json:
        print(json.dumps({"devices": devices}))
        return 0
    print("Gefundene Geraete (device_id / name / gatewayId):")
    for dev in devices:
        print(f"  id={dev['id']}  name={dev['name']!r}  gateway={dev['gatewayId']}")
    return 0


def cmd_token(cfg):
    """Diagnose: erzwingt einen Refresh und meldet die Restlaufzeit."""
    get_access_token(cfg, force=True)
    remaining = _bold(cfg).get("access_token_expiry", 0) - int(time.time())
    print(json.dumps({"ok": True, "expires_in_seconds": remaining}))
    return 0


def main(argv):
    action = argv[1] if len(argv) > 1 else ""
    if action not in {"activate", "deactivate", "status", "discover", "token"}:
        print(__doc__)
        return 2
    cfg = load_settings()
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


if __name__ == "__main__":
    sys.exit(main(sys.argv))
