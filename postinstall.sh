#!/bin/bash
#
# bold2lox – postinstall (runs as the loxberry user, on install AND update)
#
# LoxBerry copies data/* over the plugin data folder on every update. That is why
# the shipped file is called settings.default.json: the live settings.json is never
# overwritten. Here we make sure settings.json exists and gains any NEW default
# keys, while keeping every value the user already configured (tokens, device_id,
# gateway_id, trigger secret, ...).

DATADIR="$LBPDATA/bold2lox"
DEFAULT="$DATADIR/settings.default.json"
LIVE="$DATADIR/settings.json"

if [ ! -f "$DEFAULT" ]; then
    echo "<ERROR> bold2lox: $DEFAULT missing – cannot create settings."
    exit 1
fi

python3 - "$DEFAULT" "$LIVE" <<'PY'
import json, os, sys

default_path, live_path = sys.argv[1], sys.argv[2]

with open(default_path, encoding="utf-8") as fh:
    defaults = json.load(fh)

live = {}
existed = os.path.exists(live_path)
if existed:
    try:
        with open(live_path, encoding="utf-8") as fh:
            live = json.load(fh)
    except Exception as exc:                      # corrupt file -> keep a backup
        os.replace(live_path, live_path + ".broken")
        print(f"<WARNING> bold2lox: settings.json unreadable ({exc}); kept as .broken")
        live, existed = {}, False

def merge(defaults, current):
    """Add missing default keys; never overwrite existing user values."""
    for key, val in defaults.items():
        if isinstance(val, dict) and isinstance(current.get(key), dict):
            merge(val, current[key])
        elif key not in current:
            current[key] = val
    return current

merged = merge(defaults, live)

tmp = live_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(merged, fh, indent=2, ensure_ascii=False)
os.replace(tmp, live_path)

print("<OK> bold2lox: settings.json " + ("migrated (user values kept)" if existed else "created from defaults"))
PY

rc=$?
if [ $rc -ne 0 ]; then
    echo "<ERROR> bold2lox: could not prepare settings.json"
    exit 1
fi

chmod 600 "$LIVE" 2>/dev/null   # contains tokens
echo "<OK> bold2lox: postinstall complete."
exit 0
