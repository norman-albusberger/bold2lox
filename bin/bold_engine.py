#!/usr/bin/env python3
"""
bold2lox – Bruecke zwischen Loxone Miniserver (Gen 1) und Bold Smart Lock.

Der Miniserver kann nur einfache lokale HTTP-GETs (Virtual Output) und schwaches
TLS. Diese Bruecke uebernimmt HTTPS + Bearer-Auth gegen die Bold-Cloud und schiebt
den Status per UDP an einen Virtual UDP Input im Miniserver zurueck.

Bestaetigte Endpoints (github.com/lwestenberg/bold_smart_lock):
  POST /v1/devices/{id}/remote-activation
  POST /v1/devices/{id}/remote-deactivation
  GET  /v1/effective-device-permissions
  GET  /v1/gateways/{id}/current-status

Aufruf:
  bold_engine.py activate            # Schloss ausloesen (momentan)
  bold_engine.py deactivate
  bold_engine.py status              # Status holen und per UDP an den Miniserver
  bold_engine.py discover [--json]   # device_id / gateway_id auflisten (fuer die Web-UI)

Konfiguration: settings.json (Pfad via $BOLD2LOX_SETTINGS oder Standardpfad).
"""
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

SETTINGS_PATH = os.environ.get(
    "BOLD2LOX_SETTINGS",
    "/opt/loxberry/data/plugins/bold2lox/settings.json",
)


def load_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _token(cfg):
    return (cfg.get("bold") or {}).get("access_token", "")


def api_request(cfg, method, path):
    url = cfg.get("api_base", "https://api.boldsmartlock.com/v1").rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer " + _token(cfg))
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            body = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise SystemExit("401 Unauthorized – Bold-Token fehlt oder ist abgelaufen (Einstellungen).")
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
    return (cfg.get("bold") or {}).get("device_id", 0)


def _gateway_id(cfg):
    return (cfg.get("bold") or {}).get("gateway_id", 0)


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
    if not _token(cfg) or not _gateway_id(cfg):
        print(json.dumps({"skipped": "token/gateway fehlt"}))
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
        {
            "id": dev.get("id"),
            "name": dev.get("name"),
            "gatewayId": dev.get("gatewayId"),
        }
        for dev in _iter_devices(perms)
    ]
    if as_json:
        print(json.dumps({"devices": devices}))
        return 0
    print("Gefundene Geraete (device_id / name / gatewayId):")
    for dev in devices:
        print(f"  id={dev['id']}  name={dev['name']!r}  gateway={dev['gatewayId']}")
    return 0


def main(argv):
    action = argv[1] if len(argv) > 1 else ""
    if action not in {"activate", "deactivate", "status", "discover"}:
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


if __name__ == "__main__":
    sys.exit(main(sys.argv))
