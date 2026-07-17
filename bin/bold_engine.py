#!/usr/bin/env python3
"""
bold2lox – Bridge zwischen Loxone Miniserver (Gen 1) und Bold Smart Lock.

Der Miniserver kann nur einfache lokale HTTP-GETs (Virtual Output) und schwaches
TLS. Diese Bruecke uebernimmt HTTPS + Bearer-Auth gegen die Bold-Cloud und schiebt
den Status per UDP an einen Virtual UDP Input im Miniserver zurueck.

Bestaetigte Endpoints (github.com/lwestenberg/bold_smart_lock):
  POST /v1/devices/{id}/remote-activation
  POST /v1/devices/{id}/remote-deactivation
  GET  /v1/effective-device-permissions
  GET  /v1/gateways/{id}/current-status

Aufruf:
  bold_engine.py activate      # Schloss ausloesen (momentan – Knauf kuppelt kurz ein)
  bold_engine.py deactivate
  bold_engine.py status        # Gateway-Status holen und per UDP an den Miniserver
  bold_engine.py discover      # device_id / gateway_id auflisten (einmalig fuer die Config)
"""
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

CONFIG_PATH = os.environ.get(
    "BOLD2LOX_CONFIG",
    "/opt/loxberry/config/plugins/bold2lox/bold2lox.cfg",
)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        # Kommentar-Keys ("// ...") werden einfach ignoriert.
        return json.load(fh)


def api_request(cfg, method, path):
    url = cfg["api_base"].rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer " + cfg["access_token"])
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("http_timeout_seconds", 15)) as resp:
            body = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise SystemExit("401 Unauthorized – Token abgelaufen. bold_login.py erneut ausfuehren.")
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


def cmd_activate(cfg, deactivate=False):
    verb = "remote-deactivation" if deactivate else "remote-activation"
    status, data = api_request(cfg, "POST", f"/devices/{cfg['device_id']}/{verb}")
    err = data.get("errorCode")
    ok = 1 if (200 <= status < 300 and not err) else 0
    send_udp(cfg, [f"bold_last_action={int(time.time())}", f"bold_action_ok={ok}"])
    print(json.dumps({"http": status, "ok": ok, "errorCode": err}))
    return 0 if ok else 1


def cmd_status(cfg):
    _, gw = api_request(cfg, "GET", f"/gateways/{cfg['gateway_id']}/current-status")
    online = 1 if not gw.get("errorCode") else 0
    lines = [f"bold_gateway_online={online}"]
    # Batterie/Details stecken in den effective-device-permissions.
    _, perms = api_request(cfg, "GET", "/effective-device-permissions")
    for entry in _iter_devices(perms):
        if str(entry.get("id")) == str(cfg["device_id"]):
            batt = entry.get("actualFirmwareVersion") and entry.get("batteryLevel")
            if entry.get("batteryLevel") is not None:
                lines.append(f"bold_battery={entry['batteryLevel']}")
            break
    send_udp(cfg, lines)
    print(json.dumps({"pushed": lines}))
    return 0


def _iter_devices(perms):
    """Die Permissions-Antwort ist eine Liste von Locations mit 'devices'."""
    if isinstance(perms, list):
        for loc in perms:
            for dev in (loc.get("devices") or []):
                yield dev
    elif isinstance(perms, dict):
        for dev in (perms.get("devices") or []):
            yield dev


def cmd_discover(cfg):
    _, perms = api_request(cfg, "GET", "/effective-device-permissions")
    print("Gefundene Geraete (device_id / name / gatewayId):")
    for dev in _iter_devices(perms):
        print(f"  id={dev.get('id')}  name={dev.get('name')!r}  gateway={dev.get('gatewayId')}")
    print("\nEintraege in bold2lox.cfg unter device_id / gateway_id uebernehmen.")
    return 0


def main(argv):
    if len(argv) < 2 or argv[1] not in {"activate", "deactivate", "status", "discover"}:
        print(__doc__)
        return 2
    cfg = load_config()
    action = argv[1]
    if action == "activate":
        return cmd_activate(cfg)
    if action == "deactivate":
        return cmd_activate(cfg, deactivate=True)
    if action == "status":
        return cmd_status(cfg)
    if action == "discover":
        return cmd_discover(cfg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
