# bold2lox – Bold Smart Lock für Loxone

LoxBerry-Plugin, das ein **Bold Smart Lock** aus der **Loxone-App** bedienbar
macht. Der Miniserver (auch **Gen 1**) feuert nur einen simplen lokalen HTTP-GET;
der LoxBerry macht HTTPS + Bearer-Auth gegen die Bold-Cloud, die über deinen
**Bold Connect** (das Steckdosengerät) das Schloss auslöst.

```
Loxone App → Miniserver (Virtual Output, HTTP-GET) → LoxBerry activate.php
          → bold_engine.py → HTTPS → Bold-Cloud → Bold Connect → Schloss
Status:   Bold-Cloud → bold2lox.service (Poller) → UDP → Miniserver (Virtual UDP Input) → App
```

## Installation

Als LoxBerry-Plugin installieren (ZIP über die LoxBerry-Plugin-Verwaltung, oder
Auto-Update über `release.cfg`). Beim Einrichten laufen automatisch:

- `preinstall.sh` – prüft `python3` (Abhängigkeiten; `requests` optional).
- `postroot.sh` – legt den systemd-Dienst `bold2lox.service` an (Status-Poller).
- `uninstall/uninstall` – stoppt/entfernt den Dienst und räumt Daten/Logs auf.

Voraussetzungen: LoxBerry ≥ 3.0, ein **Bold Connect** im Haus, ein gültiger
**Bold-Access-Token**.

## Einrichtung (im LoxBerry-Webmenü → bold2lox)

1. Tab **Login**: mit Telefonnummer + Code + Passwort einmalig anmelden
   (holt die Tokens automatisch, siehe unten).
2. Tab **Einstellungen**: speichern → das Geräte-Dropdown füllt sich (**Discover**).
   Schloss auswählen → `device_id`/`gateway_id` werden gesetzt.
3. Im **Verbindungstest** unten „Diagnose" laufen lassen (zeigt Token/Gerät/Bold
   Connect) und optional „Schloss jetzt öffnen (Test)".
4. **Trigger-Secret** per Button erzeugen, **Miniserver-IP** + **UDP-Port**
   eintragen, speichern.
5. Auf **Übersicht** die fertigen Virtual-Output-URLs kopieren.

## Authentifizierung (OAuth2, set-and-forget)

Bold nutzt **OAuth2**: ein **kurzlebiger** Access-Token für jeden Aufruf, erneuert
über einen **langlebigen Refresh-Token**. Das Plugin speichert Access- +
Refresh-Token und **erneuert den Access-Token automatisch** am Token-Endpoint
(`grant_type=refresh_token`), sobald er abläuft — deshalb: einmal einrichten,
dann läuft es verlässlich. Bestätigte Endpoints (aus
[homeassistant_bold](https://github.com/lwestenberg/homeassistant_bold)):

- Token/Refresh/Login: `https://api.boldsmartlock.com/v2/oauth/token`
- Verifizierung: `https://api.boldsmartlock.com/v2/verification/{request-code,verify-code}`

**Erst-Anmeldung – im Plugin, ohne externe Tools** (Tab **Login**): Ein
3-Schritt-Assistent holt die Tokens direkt über deinen Bold-Account:

1. **Telefonnummer** (Bold-Account, international z. B. `+49170…`) → Code per
   SMS oder E-Mail anfordern.
2. **Verifizierungscode** eingeben.
3. **Bold-Passwort** eingeben → das Plugin holt Access- + Refresh-Token und legt
   sie (samt der festen App-Client-Credentials) in `settings.json` ab.

Danach übernimmt der Auto-Refresh; du musst das nie wiederholen. Der Login nutzt
den **Legacy-Flow** mit den Client-Credentials der Bold-App (`BoldApp`, aus
[homebridge-bold](https://github.com/StefanNienhuis/homebridge-bold)) — daher ist
**keine eigene OAuth-Registrierung** nötig.

> Hinweis: Der Legacy-Login erlaubt nur **eine** aktive Session — deine Bold-App
> auf dem Handy wird dabei ggf. abgemeldet. Für eine Steuerbrücke meist ok.

Wird der Refresh-Token ungültig (Passwortänderung, Widerruf, lange Inaktivität),
einfach den Login-Tab erneut durchlaufen. Diagnose: `bold_engine.py token`
erzwingt einen Refresh und zeigt die Restlaufzeit.

## Loxone Config

**Steuerung (App-Taster → Schloss):**
1. **Virtual Output**, Adresse `http://<loxberry-ip>` (Port 80).
2. **Virtual Output Command**, *ON:*
   `/plugins/bold2lox/activate.php?key=SECRET&cmd=open` (GET).
3. Mit einem **Taster** verbinden und in die App legen. Optional zweiter Command
   `cmd=close` für `remote-deactivation`.

**Rückmeldung (Status → App):**
1. **Virtual UDP Input** auf dem in den Einstellungen gewählten Port.
2. Command-Recognition-Einträge:
   `bold_battery=\v`, `bold_gateway_online=\v`, `bold_action_ok=\v`,
   `bold_last_action=\v`.

## Aufbau (Plugin-Ordner → Zielpfade auf dem LoxBerry)

| Repo                                | Ziel (`bold2lox`-Plugin)                                     |
| ----------------------------------- | ----------------------------------------------------------- |
| `plugin.cfg`, `*.sh`, `uninstall/`  | Plugin-Root / LoxBerry-Lifecycle                            |
| `bin/bold_engine.py`                | `$LBPBIN/bold2lox/` – Kern (activate/status/discover)       |
| `bin/bold2lox-daemon`               | `$LBPBIN/bold2lox/` – Status-Poller (systemd)               |
| `webfrontend/htmlauth/*`            | Web-UI (Übersicht/Einstellungen/About)                     |
| `webfrontend/html/activate.php`     | **unauth.** Trigger für den Miniserver                     |
| `data/settings.json`                | `$LBPDATA/bold2lox/` – Konfig (Token etc., zur Laufzeit)    |
| `templates/lang/language_en.ini`    | Sprachdatei                                                 |

## Design-Entscheidungen

- **Kein persistenter Auf/Zu-Status** – Bold ist ein momentaner Zylinder; die App
  zeigt „zuletzt ausgelöst" + Batterie/Online, nicht „verriegelt/entriegelt".
- **Rückmeldung per rohem UDP** – versionsunabhängig, kein MQTT nötig.
- **OAuth2 mit Auto-Refresh** – der Engine erneuert den kurzlebigen Access-Token
  selbstständig; nur die einmalige Erst-Autorisierung ist manuell.

## Bestätigte Bold-API-Endpoints

`https://api.boldsmartlock.com` –
`POST /v1/devices/{id}/remote-activation`,
`POST /v1/devices/{id}/remote-deactivation`,
`GET /v1/effective-device-permissions`,
`GET /v1/gateways/{id}/current-status`,
Token/Refresh/Login `POST /v2/oauth/token`,
Verifizierung `POST /v2/verification/{request-code,verify-code}`
(Quellen: [bold_smart_lock](https://github.com/lwestenberg/bold_smart_lock),
[homeassistant_bold](https://github.com/lwestenberg/homeassistant_bold),
[homebridge-bold](https://github.com/StefanNienhuis/homebridge-bold)).
Feldnamen `batteryLevel`/`gatewayId` sind über `homeassistant_bold/const.py`
bestätigt.

## Test / Diagnose (Web-UI)

- **Login-Tab**: 3-Schritt-Anmeldung (Telefonnummer → Code → Passwort).
- **Einstellungen → Verbindungstest**: „Diagnose" prüft Token/Gerät/Bold Connect
  Schritt für Schritt (ohne auszulösen); „Schloss jetzt öffnen (Test)" löst real aus.
- CLI-Diagnose: `bold_engine.py diagnose` bzw. `bold_engine.py token`.
