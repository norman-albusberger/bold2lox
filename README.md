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

1. **Einstellungen** öffnen und den **Bold-Access-Token** einfügen.
2. Seite speichern → das Geräte-Dropdown füllt sich (**Discover** über die
   Bold-Cloud). Schloss auswählen → `device_id`/`gateway_id` werden gesetzt.
3. **Trigger-Secret** per Button erzeugen, **Miniserver-IP** + **UDP-Port**
   eintragen, speichern.
4. Auf **Übersicht** die fertigen Virtual-Output-URLs kopieren und den
   „Test: activate now"-Button nutzen.

Der Token wird manuell hinterlegt (bewusste Design-Entscheidung). Läuft er ab,
liefert die API `401` → in den Einstellungen neuen Token eintragen.

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
- **Token manuell** – kein Login-Flow im Plugin (die Bold-Auth-API ist
  versionsabhängig und liefert nur Single-Session-Tokens).

## Bestätigte Bold-API-Endpoints

`https://api.boldsmartlock.com` –
`POST /v1/devices/{id}/remote-activation`,
`POST /v1/devices/{id}/remote-deactivation`,
`GET /v1/effective-device-permissions`,
`GET /v1/gateways/{id}/current-status`
(Quelle: [lwestenberg/bold_smart_lock](https://github.com/lwestenberg/bold_smart_lock)).

## Noch zu verifizieren (an echter API-Antwort)

- Feldnamen `batteryLevel` / `gatewayId` in `effective-device-permissions`
  einmal per `bold_engine.py discover` gegenchecken und ggf. im Engine anpassen.
