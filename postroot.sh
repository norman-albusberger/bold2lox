#!/bin/bash
#
# bold2lox – postroot (laeuft als root)
# Richtet den Status-Daemon als systemd-Dienst ein (optionale Rueckmeldung an
# den Miniserver). Der Dienst laeuft als loxberry-User und liest settings.json.

DAEMON="$LBPBIN/bold2lox/bold2lox-daemon"
SETTINGS_FILE="$LBPDATA/bold2lox/settings.json"
SERVICE_FILE="/etc/systemd/system/bold2lox.service"

echo "<INFO> bold2lox: Richte systemd-Dienst ein..."

if [ ! -f "$DAEMON" ]; then
    echo "<ERROR> Daemon nicht gefunden: $DAEMON. Bitte Plugin neu installieren."
    exit 1
fi
chmod +x "$DAEMON" 2>/dev/null

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=bold2lox status poller (Bold Smart Lock -> Loxone)
After=network-online.target
Wants=network-online.target

[Service]
Environment="BOLD2LOX_SETTINGS=$SETTINGS_FILE"
ExecStart=/usr/bin/python3 $DAEMON
Restart=always
RestartSec=15
User=loxberry
Group=loxberry

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bold2lox.service
systemctl restart bold2lox.service

if [ $? -eq 0 ]; then
    echo "<OK> bold2lox.service laeuft."
else
    echo "<ERROR> bold2lox.service konnte nicht gestartet werden."
    exit 1
fi

echo "<OK> bold2lox: postroot abgeschlossen."
exit 0
