#!/usr/bin/env python3
"""
Einmalige/wiederholte Token-Beschaffung fuer bold2lox.

Nutzt die offizielle Community-Bibliothek 'bold-smart-lock', damit hier KEINE
Auth-Endpoints von Hand nachgebaut werden (die kann Bold jederzeit aendern):

    pip3 install bold-smart-lock aiohttp

Legacy-Login (E-Mail/Passwort + E-Mail-Verifizierungscode). Achtung: der
Legacy-Weg erlaubt nur EINE aktive Session – wenn du ihn nutzt, wird ggf. deine
Handy-App abgemeldet. Fuer eine reine Steuerbruecke ist das meist ok.

Deine Zugangsdaten gibst DU hier selbst ein; das Skript speichert nur den
erhaltenen Token in die bold2lox.cfg.
"""
import asyncio
import getpass
import json
import os

import aiohttp
from bold_smart_lock.auth import Auth  # aus der bold-smart-lock Lib

CONFIG_PATH = os.environ.get(
    "BOLD2LOX_CONFIG",
    "/opt/loxberry/config/plugins/bold2lox/bold2lox.cfg",
)


async def run():
    email = input("Bold E-Mail: ").strip()
    password = getpass.getpass("Bold Passwort: ")

    async with aiohttp.ClientSession() as session:
        auth = Auth(session)
        # 1) Verifizierungscode per E-Mail anfordern
        await auth.request_verification_token(email, password)
        code = input("Verifizierungscode aus der E-Mail: ").strip()
        # 2) Login abschliessen -> liefert Token-Daten
        token_data = await auth.authenticate(email, password, code)

    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg["access_token"] = token_data.get("token") or token_data.get("access_token", "")
    cfg["refresh_token"] = token_data.get("refresh_token", "")
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)

    print("Token gespeichert. Jetzt 'bold_engine.py discover' ausfuehren.")


if __name__ == "__main__":
    asyncio.run(run())
