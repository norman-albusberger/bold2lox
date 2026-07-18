#!/bin/bash
#
# bold2lox – preupgrade (runs as the loxberry user, ONLY on update)
#
# CRITICAL: LoxBerry's installer calls purge_installation() on every update, which
# does "rm -rf <lbhome>/data/plugins/<plugin>/" – i.e. the whole plugin data folder
# including settings.json (tokens, device/gateway id, trigger secret) is deleted
# BEFORE the new data/* is copied in. preupgrade runs *before* that purge, so this
# is the only safe place to rescue the user's configuration.
#
# The backup is written outside every folder the purge removes and is restored by
# postinstall.sh.
#
# Args from the installer: $1=tempfile $2=pname $3=pfolder $4=pversion $5=lbhomedir $6=tempfolder

PFOLDER="$3"
LBHOME="$5"
[ -n "$PFOLDER" ] || PFOLDER="bold2lox"
[ -n "$LBHOME" ] || LBHOME="/opt/loxberry"

LIVE="$LBHOME/data/plugins/$PFOLDER/settings.json"
BACKUP="$LBHOME/data/system/${PFOLDER}_settings_backup.json"

if [ -f "$LIVE" ]; then
    if cp -p "$LIVE" "$BACKUP" 2>/dev/null; then
        chmod 600 "$BACKUP" 2>/dev/null
        echo "<OK> bold2lox: configuration backed up before update ($BACKUP)"
    else
        echo "<ERROR> bold2lox: could NOT back up $LIVE – aborting to avoid losing your configuration."
        exit 2
    fi
else
    echo "<INFO> bold2lox: no existing settings.json found, nothing to back up."
fi

exit 0
