# bold2lox – Loxone (Gen 1) ⇄ Bold Smart Lock

Bruecke, die dein Bold Smart Lock aus der Loxone-App bedienbar macht. Der
Miniserver Gen 1 feuert nur einen simplen lokalen HTTP-GET; der LoxBerry macht
HTTPS + Bearer-Auth gegen die Bold-Cloud, die ueber deinen **Bold Connect**
(das Steckdosengeraet) das Schloss ausloest.

```
Loxone App → Miniserver (Virtual Output, HTTP-GET) → LoxBerry activate.php
          → bold_engine.py → HTTPS → Bold-Cloud → Bold Connect → Schloss
Status:   Bold-Cloud → bold2lox-daemon → UDP → Miniserver (Virtual UDP Input) → App
```

## Dateien / Zielpfade auf dem LoxBerry

| Datei im Plugin                     | Zielpfad auf dem LoxBerry                                   |
| ----------------------------------- | ---------------------------------------------------------- |
| `bin/bold_engine.py`                | `/opt/loxberry/bin/plugins/bold2lox/bold_engine.py`        |
| `bin/bold_login.py`                 | `/opt/loxberry/bin/plugins/bold2lox/bold_login.py`         |
| `webfrontend/html/activate.php`     | `/opt/loxberry/webfrontend/html/plugins/bold2lox/activate.php` |
| `daemon/bold2lox-daemon`            | `/opt/loxberry/bin/plugins/bold2lox/bold2lox-daemon`       |
| `config/bold2lox.cfg.example`       | `/opt/loxberry/config/plugins/bold2lox/bold2lox.cfg`       |

Der Webfrontend-Pfad ergibt die Trigger-URL: `http://<loxberry-ip>/plugins/bold2lox/activate.php`

## Einrichtung (einmalig)

1. **Abhaengigkeiten:** `pip3 install bold-smart-lock aiohttp`
   (nur fuer `bold_login.py`; `bold_engine.py` selbst nutzt nur die Standardlib.)
2. **Config anlegen:** `bold2lox.cfg.example` → `bold2lox.cfg` kopieren,
   `trigger_secret` auf einen langen Zufallsstring setzen, `miniserver.ip`
   eintragen.
3. **Token holen:** `python3 bold_login.py` – DU gibst Bold-E-Mail/Passwort +
   E-Mail-Code ein; der Token landet in der Config.
   ⚠️ Der Legacy-Login erlaubt nur **eine** aktive Session (ggf. wird deine
   Handy-App abgemeldet). Token laufen ab → bei `401` einfach erneut ausfuehren.
4. **IDs ermitteln:** `python3 bold_engine.py discover` → `device_id` und
   `gateway_id` in die Config uebernehmen.
5. **Test von der Shell:** `python3 bold_engine.py activate` → das Schloss sollte
   kuppeln. Danach `status` testen.

## Loxone Config – Steuerung (App-Taster → Schloss)

1. **Virtual Output** anlegen, Adresse: `http://<loxberry-ip>` (Port 80).
2. Darunter einen **Virtual Output Command**:
   - *Command for ON:* `/plugins/bold2lox/activate.php?key=DEIN_SECRET&cmd=open`
   - HTTP-Methode: GET
3. Diesen Ausgang mit einem **Taster**-Baustein verbinden und als Bedienelement
   in die App legen. Ein Tastendruck = einmal ausloesen (momentan, kein Dauer-
   zustand – das entspricht dem Bold-Prinzip).
4. Optional zweiter Command mit `cmd=close` fuer `remote-deactivation`.

## Loxone Config – Rueckmeldung (Status → App)

1. **Virtual UDP Input** anlegen, gleiche UDP-Portnummer wie in der Config
   (`miniserver.udp_port`, z. B. 4001).
2. Darunter **Virtual UDP Input Commands** mit Digitalfilter „Command
   Recognition":
   - `bold_battery=\v`      → Batteriestand als Analogwert
   - `bold_gateway_online=\v` → Bold-Connect erreichbar (0/1)
   - `bold_action_ok=\v`    → letzte Ausloesung erfolgreich (0/1)
3. Diese Eingaenge als Status-/Statusbaustein in die App legen.
4. `bold2lox-daemon` als LoxBerry-Dienst laufen lassen (pollt alle
   `poll_interval_seconds`) — dann kommt der Status automatisch.

## Was hier bewusst „ohne Kopfstand" bleibt

- **Kein persistenter Auf/Zu-Status** — Bold ist ein momentaner Zylinder; die
  App zeigt „zuletzt ausgeloest" + Batterie/Online, nicht „verriegelt/entriegelt".
- **Rueckmeldung per UDP** statt LoxBerry::IO/MQTT — versionsunabhaengig und
  simpel. Wenn du MQTT ohnehin nutzt, kann der Daemon stattdessen dorthin
  publishen.
- **Token-Refresh** ist bewusst manuell (`bold_login.py` erneut). Automatischer
  Refresh liesse sich ergaenzen, sobald der Refresh-Flow deiner Lib-Version
  feststeht.

## Vor dem Scharfschalten pruefen

- Die Methodennamen in `bold_login.py` (`request_verification_token`,
  `authenticate`) gegen die **installierte** Version von `bold-smart-lock`
  abgleichen — die Auth-API der Lib hat sich zwischen Versionen geaendert
  (aeltere Versionen hatten den Login eingebaut, neuere delegieren an eine
  eigene Token-Beschaffung). Aktivierung/Status-Endpoints sind stabil.
- `effective-device-permissions`-Antwortformat einmal mit `discover` ansehen und
  die Feldnamen (`batteryLevel`, `gatewayId`) im Engine ggf. anpassen.
```
