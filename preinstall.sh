#!/bin/bash
#
# bold2lox – preinstall (laeuft als loxberry-User)
# Prueft/instaliert die Python-Abhaengigkeiten des Plugins.
#
# Das Plugin selbst kommt mit der Python-Standardlib aus; 'requests' wird nur
# genutzt, wenn vorhanden – ansonsten faellt der Engine auf urllib zurueck.
# Hier stellen wir lediglich sicher, dass python3 vorhanden ist.

echo "<INFO> bold2lox: Pruefe Voraussetzungen..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "<ERROR> python3 ist nicht installiert. Bitte python3 bereitstellen."
    exit 1
fi
echo "<OK> python3 gefunden: $(python3 --version 2>&1)"

# 'requests' ist optional – Installation nicht abbrechen, wenn es fehlschlaegt.
if python3 -c "import requests" >/dev/null 2>&1; then
    echo "<OK> python3-requests vorhanden."
else
    echo "<INFO> python3-requests fehlt (optional). Engine nutzt urllib als Fallback."
fi

echo "<OK> bold2lox: preinstall abgeschlossen."
exit 0
