#!/bin/bash
#
# bold2lox – preinstall (runs as the loxberry user)
# Checks the plugin's Python dependencies.
#
# The plugin itself only needs the Python standard library; 'requests' is only
# used if present – otherwise the engine falls back to urllib.
# Here we only make sure python3 is present.

echo "<INFO> bold2lox: checking prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "<ERROR> python3 is not installed. Please provide python3."
    exit 1
fi
echo "<OK> python3 found: $(python3 --version 2>&1)"

# 'requests' is optional – don't abort the install if it fails.
if python3 -c "import requests" >/dev/null 2>&1; then
    echo "<OK> python3-requests present."
else
    echo "<INFO> python3-requests missing (optional). The engine uses urllib as a fallback."
fi

echo "<OK> bold2lox: preinstall complete."
exit 0
