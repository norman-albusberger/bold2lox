#!/bin/bash
#
# bold2lox – postroot (runs as root)
# Sets up the status daemon as a systemd service (optional feedback to
# the Miniserver). The service runs as the loxberry user and reads settings.json.

DAEMON="$LBPBIN/bold2lox/bold2lox-daemon"
SETTINGS_FILE="$LBPDATA/bold2lox/settings.json"
SERVICE_FILE="/etc/systemd/system/bold2lox.service"

echo "<INFO> bold2lox: setting up systemd service..."

if [ ! -f "$DAEMON" ]; then
    echo "<ERROR> Daemon not found: $DAEMON. Please reinstall the plugin."
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
    echo "<OK> bold2lox.service is running."
else
    echo "<ERROR> bold2lox.service could not be started."
    exit 1
fi

echo "<OK> bold2lox: postroot complete."
exit 0
