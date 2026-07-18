#!/bin/bash
#
# bold2lox – postinstall (runs as the loxberry user, on install AND update)
#
# Restores the configuration that preupgrade.sh rescued before LoxBerry purged the
# plugin data folder, and makes sure settings.json exists and gains any NEW default
# keys. User values always win over defaults.
#
# Paths are derived from the installer arguments, NOT from $LBPDATA: the script is
# started via "sudo -n -u loxberry", so the LoxBerry environment variables are not
# guaranteed to be present.
#
# Args from the installer: $1=tempfile $2=pname $3=pfolder $4=pversion $5=lbhomedir $6=tempfolder

PFOLDER="$3"
LBHOME="$5"
[ -n "$PFOLDER" ] || PFOLDER="bold2lox"
[ -n "$LBHOME" ] || LBHOME="/opt/loxberry"

DATADIR="$LBHOME/data/plugins/$PFOLDER"
DEFAULT="$DATADIR/settings.default.json"
LIVE="$DATADIR/settings.json"
BACKUP="$LBHOME/data/system/${PFOLDER}_settings_backup.json"

if [ ! -f "$DEFAULT" ]; then
    echo "<ERROR> bold2lox: $DEFAULT missing – cannot create settings."
    exit 1
fi

python3 - "$DEFAULT" "$LIVE" "$BACKUP" <<'PY'
import json, os, sys

default_path, live_path, backup_path = sys.argv[1], sys.argv[2], sys.argv[3]

def load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"<WARNING> bold2lox: {os.path.basename(path)} unreadable ({exc}), ignored")
        return None

defaults = load(default_path) or {}
backup = load(backup_path)          # rescued by preupgrade.sh (update)
live = load(live_path)              # normally absent after the purge

def overlay(base, top):
    """Return base with top merged over it (top wins, recursively)."""
    out = dict(base)
    for key, val in (top or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = overlay(out[key], val)
        else:
            out[key] = val
    return out

# Defaults provide any NEW keys; the rescued backup and an existing file win.
result = defaults
if isinstance(backup, dict):
    result = overlay(result, backup)
if isinstance(live, dict):
    result = overlay(result, live)

tmp = live_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2, ensure_ascii=False)
os.replace(tmp, live_path)

restored = bool(backup) and bool((backup or {}).get("bold", {}).get("refresh_token"))
if restored:
    print("<OK> bold2lox: configuration restored from backup (login and lock kept)")
elif live:
    print("<OK> bold2lox: settings.json migrated (user values kept)")
else:
    print("<OK> bold2lox: settings.json created from defaults")
PY

rc=$?
if [ $rc -ne 0 ]; then
    echo "<ERROR> bold2lox: could not prepare settings.json – your backup is kept at $BACKUP"
    exit 1
fi

chmod 600 "$LIVE" 2>/dev/null   # contains tokens
rm -f "$BACKUP" 2>/dev/null     # restored successfully, backup no longer needed
echo "<OK> bold2lox: postinstall complete."
exit 0
