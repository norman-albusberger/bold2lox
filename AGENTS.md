# AGENTS.md – bold2lox

Guidance for coding agents working on this repo. `CLAUDE.md` imports this file.
LoxBerry facts below were verified against the LoxBerry core source on master
(4.0.1.x, Oct 2026): `sbin/plugininstall.pl`, `sbin/pluginsupdate.pl`,
`libs/perllib/LoxBerry/AppStore.pm`, `libs/perllib/LoxBerry/System/PluginDB.pm`,
and the official `LoxBerry-Plugin-SamplePlugin-V4`. Re-check those files if behaviour
seems to differ.

## 1. What this is

A LoxBerry plugin that lets a Loxone Miniserver (including Gen 1, which only manages
plain HTTP GET) trigger a **Bold Smart Lock** through the Bold cloud.

```
Loxone app → Miniserver Virtual Output (HTTP GET) → webfrontend/html/activate.php (?key=SECRET)
          → bin/bold_engine.py → HTTPS + OAuth2 → Bold cloud → Bold Connect → lock
Status:   bold2lox.service (bin/bold2lox-daemon, systemd) → UDP → Miniserver Virtual UDP Input
```

| Component | Role |
|---|---|
| `bin/bold_engine.py` | Core logic, **Python stdlib only** (no pip). CLI: `activate`, `deactivate`, `status`, `discover [--json]`, `token`, `diagnose`, `login-exchange` (JSON on stdin). Prints JSON for the web UI. |
| `bin/bold2lox-daemon` | Poll loop → `cmd_status` → UDP. Runs as a systemd unit that `postroot.sh` creates. |
| `webfrontend/htmlauth/*.php` | Admin UI (LoxBerry auth): Overview, Login, Settings, About. `Bold.php` wraps `settings.json` and the engine. |
| `webfrontend/html/activate.php` | **Unauthenticated** trigger for the Miniserver, protected only by `trigger_secret` (`hash_equals`). |
| `data/settings.default.json` | Shipped template. The live `settings.json` (tokens!) only exists on the LoxBerry and never in git. |
| `templates/lang/language_en.ini` | UI strings (English only; `readlanguage` falls back to `en`). |

Domain rules that must not regress:
- **Bold rotates the refresh token on every refresh.** Refreshes are serialised with
  `flock` on `settings.json.lock` and re-read from disk (see `_refresh_access_token`).
  Never add a second refresh path that skips this.
- **No "close" output for Loxone**: the cylinder releases by itself. The trigger is momentary.
- **The gateway (Bold Connect) is optional**: 403 or missing id means "skipped", not "failed".
- Loxone timestamps are seconds since 2009-01-01 (`LOXONE_EPOCH_OFFSET`).
- `auth_user_agent` (e.g. `Bold/1172 …`) is a version gate. Bold answers `OldAppVersion` if it is too old.

## 2. Safety rules for agents

- **`bold_engine.py activate` and `test.php?what=activate` physically unlock a real door.**
  Never run them without the user's explicit OK.
- **Never run the engine against a copy of a live `settings.json`.** The refresh
  rotates the token and silently logs out the LoxBerry.
- Never commit tokens, secrets or a real `settings.json`. Keep `chmod 600` on it.
- Never change the plugin identity fields (see 4.1). Never bump `release.cfg` /
  `prelease.cfg` outside a release (see 5). A push to `main` touching those files
  **deploys to every user**.

## 3. Conventions

- Code, comments, UI strings, README: **English**. Commit messages: German, short (existing history).
- New UI text goes in `templates/lang/language_en.ini` (`[SECTION]` → `$L['SECTION.KEY']`).
- Assets are cache-busted by query string (`styles.css?v=5`, `index.js?v=4`, `login.js?v=3`).
  Bump `v` in **every** page that references the asset (`grep -n '?v=' webfrontend/htmlauth/*.php`).
- Every new setting must get a default in `data/settings.default.json`. On install/upgrade,
  `postinstall.sh` deep-merges defaults **under** the user's values. Renaming or removing a
  key needs explicit migration code in `postinstall.sh`.
- Prefer LoxBerry paths over hardcoded `/opt/loxberry/...`: PHP constants `LBPDATADIR`,
  `LBPBINDIR` (from `loxberry_system.php`), shell env `$LBPDATA` etc., or installer
  placeholders (4.4). Existing hardcoded paths: `activate.php`, `bold_engine.py`
  default `SETTINGS_PATH`, script fallbacks.
- Local checks (there is no LoxBerry runtime locally):
  ```bash
  python3 -m py_compile bin/bold_engine.py bin/bold2lox-daemon
  bash -n preinstall.sh preupgrade.sh postinstall.sh postroot.sh uninstall/uninstall
  for f in webfrontend/html/*.php webfrontend/htmlauth/*.php; do php -l "$f"; done
  ```
  Real testing means installing the ZIP on a LoxBerry: fresh install, **upgrade from the
  previous tag** (settings must survive), and uninstall.
- Logs on the LoxBerry: install log `$LBHOMEDIR/log/system/plugininstall/bold2lox.log`,
  update check `$LBHOMEDIR/log/system_tmpfs/pluginsupdatecheck.log`, daemon `journalctl -u bold2lox`.

## 4. LoxBerry plugin concepts

### 4.1 `plugin.cfg` (what the installer actually reads)

| Key | Notes |
|---|---|
| `[AUTHOR] NAME`, `EMAIL` | **Identity.** Plugin id = `md5(AUTHOR.NAME + AUTHOR.EMAIL + PLUGIN.NAME + PLUGIN.FOLDER)`. Changing any of these four turns the next install into a *new* plugin (name/folder clash → installed as `bold2lox_xyz`, settings lost). **Never change them.** For a new maintainer, add `[MAINTAINER] NAME/EMAIL` (LB ≥ 4.0.1, older versions ignore it). |
| `[PLUGIN] VERSION` | What LoxBerry shows and compares. See 5.1. |
| `[PLUGIN] NAME`, `FOLDER` | Identity (above). The installer filters them to `[A-Za-z0-9_-]`. |
| `[PLUGIN] TITLE` | Display name. **More than 25 chars gets cut to 22 + `...`.** The AppStore also matches on it (6.3). |
| `[PLUGIN] WEBSITE` | Optional link in Plugin Management. |
| `[AUTOUPDATE] AUTOMATIC_UPDATES`, `RELEASECFG`, `PRERELEASECFG` | See 5.2. |
| `[SYSTEM] INTERFACE` | Must be `2.0` (1.0 is rejected since LB 3). |
| `[SYSTEM] LB_MINIMUM`, `LB_MAXIMUM` | Install is refused outside this range (unless the user tracks LoxBerry "latest commit"). |
| `[SYSTEM] ARCHITECTURE`, `REBOOT`, `CUSTOM_LOGLEVELS` | `false` = no restriction / no reboot / no loglevel selector. |

`PLUGINDB_KEY`, `PRIORITY` and `[INSTALL] API_INSTALLED` in our `plugin.cfg` are **not
read** by the installer. They are harmless leftovers.

### 4.2 Install and upgrade sequence (`plugininstall.pl`)

Install and update use the same flow (ZIP upload, URL, AppStore button, or autoupdate).
It counts as an **upgrade** if the plugin id (md5) is already in `plugindatabase.json`.

1. Create or update the DB entry. On upgrade, the new `plugin.cfg` values overwrite the
   stored ones (including the `RELEASECFG` URLs). The user's autoupdate mode is kept.
2. On all text files: replace `REPLACELB*` placeholders (4.4), run `dos2unix`.
3. `preroot*` – **root**
4. `preupgrade*` – loxberry, **upgrade only**
5. **Purge (upgrade only):** `rm -rf` of `config/`, `bin/`, `data/`, `templates/`,
   `webfrontend/htmlauth/`, `webfrontend/html/` plugin folders, plus icons, cron entries,
   daemon, sudoers file, uninstall script and `data/system/install/<folder>`.
   **This deletes `settings.json`.** What survives: `log/plugins/<folder>`, the plugin DB
   entry, `cron.d` crontab, and anything outside the plugin folders (for example
   `/etc/systemd/system/bold2lox.service` and our backup in `data/system/`).
6. `preinstall*` – loxberry
7. Copy `config/ bin/ templates/ cron/ data/ webfrontend/ icons/ daemon/ uninstall/ sudoers/`, install `dpkg/apt*` packages.
8. `postinstall*` – loxberry
9. `postupgrade*` – loxberry, **upgrade only**
10. `postroot*` – **root**
11. Save the log, set the reboot flag if `REBOOT=true`.

Script arguments: `$1` temp name, `$2` NAME, `$3` FOLDER (may carry a suffix),
`$4` VERSION, `$5` LBHOMEDIR (still passed, though the V4 sample calls it unused),
`$6` full temp path. Variables from `/etc/environment` are available too.
**Exit codes:** `0` ok, `1` error logged but install continues, `≥2` abort.
Output tags `<OK> <INFO> <WARNING> <ERROR> <FAIL>` colour the install log.

How bold2lox survives the purge:
- `preupgrade.sh` copies `settings.json` to `$LBHOMEDIR/data/system/bold2lox_settings_backup.json`
  (outside the purge). It exits 2 if that fails, which aborts *before* the purge.
- `postinstall.sh` merges backup over defaults and deletes the backup only on success.
- `postroot.sh` rewrites and restarts the systemd unit.

### 4.3 Uninstall

`uninstall/uninstall` is copied to `$LBHOMEDIR/data/system/uninstall/<NAME>` and run **as
root** on uninstall. Afterwards LoxBerry removes all plugin folders (including log) and the DB entry.
Our script only has to remove things outside those folders (the systemd unit).

### 4.4 Paths and runtime

| Repo | Installed to | URL |
|---|---|---|
| `webfrontend/htmlauth/` | `$LBHOMEDIR/webfrontend/htmlauth/plugins/<folder>/` | `/admin/plugins/<folder>/` (auth) |
| `webfrontend/html/` | `$LBHOMEDIR/webfrontend/html/plugins/<folder>/` | `/plugins/<folder>/` (no auth) |
| `bin/` `data/` `config/` `templates/` | `$LBHOMEDIR/{bin,data,config,templates}/plugins/<folder>/` | – |
| `icons/icon_{64,128,256,512}.png` (or `icon.svg`, LB 4) | system icon dir | – |
| (no `log/` folder) | `$LBHOMEDIR/log/plugins/<folder>/` is tmpfs (RAM) | – |

- Installer placeholders in text files: `REPLACELBHOMEDIR`, `REPLACELBPPLUGINDIR` (folder
  name), `REPLACELBPDATADIR`, `REPLACELBPBINDIR`, `REPLACELBPCONFIGDIR`, `REPLACELBPLOGDIR`,
  `REPLACELBPHTMLDIR`, `REPLACELBPHTMLAUTHDIR`, `REPLACELBPTEMPLATEDIR`.
- The installer warns (as a user notification) about hardcoded `/opt/loxberry`.
  Currently it only scans files without an extension, but don't rely on that.
- `<folder>` is `bold2lox` unless it collides on that system, in which case it gets a suffix.
- `sudo`: user `loxberry` has `NOPASSWD: /bin/systemctl` (LoxBerry `lbdefaults`), which is
  why `Bold.php::restartService()` works. Other root commands need a `sudoers/sudoers` file.
- Optional plugin folders we don't use: `cron/cron.{reboot,01min,…,daily,…}` and
  `cron/crontab`, `daemon/daemon` (root, at boot), `dpkg/apt` and `apt<debian-major>`,
  `config/`. We use a systemd unit instead of `daemon/`.

## 5. Release mechanism

### 5.1 Versions

- Format `MAJOR.MINOR.PATCH`. Git tag `vX.Y.Z`. `VERSION=` values have **no** `v`.
- LB ≥ 4.0 compares SemVer (`1.4.1-beta.3 < 1.4.1`, `v1.4.1 == 1.4.1`).
  **LB 3.x only understands plain numeric versions** (`version::is_lax`). There, a suffix
  like `-beta.1` is "not a real version number". If the *installed* version has one,
  that LoxBerry skips the plugin in every future update check.
  As long as `LB_MINIMUM=3.0`, ship **numeric versions only**, prereleases included.
- Autoupdate only installs **strictly newer** versions, so there is no rollback through
  `release.cfg`. Roll forward with a new patch version.

### 5.2 Autoupdate

- LoxBerry's `cron.daily` runs `sbin/pluginsupdate.pl` (or the user clicks "check" in
  Plugin Management). For each plugin it fetches the `RELEASECFG` / `PRERELEASECFG`
  URLs **stored at install time** (shadow plugin DB), compares `VERSION`, and acts on the
  user's per-plugin mode:
  `1` off (check only), `2` notify only, `3` install releases, `4` install prereleases and releases.
- **New installs start in mode 3.** So bumping `release.cfg` on `main` = automatic
  rollout to most users within about 24 h.
- Mode 4: if both channels are newer, the release wins, unless the installed version
  is itself a prerelease ("sticky prerelease", LB 4).
- Format of `release.cfg` / `prelease.cfg`:
  ```ini
  [AUTOUPDATE]
  VERSION=0.2.3
  ARCHIVEURL=https://github.com/norman-albusberger/bold2lox/archive/refs/tags/v0.2.3.zip
  INFOURL=https://github.com/norman-albusberger/bold2lox/releases/tag/v0.2.3
  ```
  `INFOURL` becomes the link in the update notification, so set it.
- **Our URLs are frozen in every installed copy:**
  `https://raw.githubusercontent.com/norman-albusberger/bold2lox/refs/heads/main/{release,prelease}.cfg`.
  Keep the repo name, the `main` branch and the file names. `prelease.cfg` is a typo of
  the usual `prerelease.cfg` but **must keep this name**. To move URLs, ship the new URL in
  `plugin.cfg` and keep serving the old files indefinitely.
- `ARCHIVEURL` is a GitHub tag archive. The installer accepts `plugin.cfg` one folder
  deep (`bold2lox-0.2.3/plugin.cfg`). The archive contains every tracked file.
  Exclude non-plugin files with `export-ignore` in `.gitattributes`.
  **Never move or delete a published tag**: the archive is generated on the fly, so
  its content would change silently.

### 5.3 Release checklist

1. `main` clean. Change tested on a LoxBerry (fresh install plus upgrade from the previous tag).
2. Bump `VERSION` in `plugin.cfg`.
3. Update the channel file(s): `VERSION`, `ARCHIVEURL` (new tag), `INFOURL`.
   - **Stable:** `release.cfg` **and** `prelease.cfg` (keep prerelease ≥ release).
   - **Prerelease:** `prelease.cfg` only.
4. Check consistency: `grep -H '^VERSION=' plugin.cfg release.cfg prelease.cfg`
5. Commit, then tag and push both in one step so `release.cfg` never points to a missing tag:
   ```bash
   git tag -a v0.2.3 -m "v0.2.3"
   ```
   ```bash
   git push --atomic origin main v0.2.3
   ```
6. Create the GitHub release (add `--prerelease` for the prerelease channel):
   ```bash
   gh release create v0.2.3 --title "v0.2.3" --generate-notes
   ```
7. Verify (raw.githubusercontent caches for about 5 min). Expect `200`, then the new `VERSION`:
   ```bash
   curl -sL -o /dev/null -w '%{http_code}\n' https://github.com/norman-albusberger/bold2lox/archive/refs/tags/v0.2.3.zip
   ```
   ```bash
   curl -fsSL https://raw.githubusercontent.com/norman-albusberger/bold2lox/refs/heads/main/release.cfg
   ```
8. **Stable only:** update the wiki plugin data box (section 6): `Version`,
   `Release Download`, and `Min. LB Version` / `Status` if they changed. Also update the
   wiki page text if setup steps changed.

Promote, don't rebuild: a prerelease `0.3.0` that proved itself becomes stable by
pointing `release.cfg` at the **same** tag (`gh release edit v0.3.0 --prerelease=false`).
Stable users get the identical ZIP, and prerelease users are already on it.

## 6. LoxBerry AppStore (LB ≥ 4.0)

### 6.1 How it works

- System widget "AppStore" (`/admin/system/appstore.cgi`). It is a searchable catalog with
  status filter, an installed/not installed filter, and default sort "newest updates".
- **Catalog source:** `https://wiki.loxberry.de/_media/appstore/plugins.json`. It is
  exported about hourly from the **plugin data box (DokuWiki struct)** of each wiki page
  `plugins:<name>:start` (`"source": "loxberry-wiki/struct"`). Sub-pages are not listed.
- Each LoxBerry caches the catalog for 60 min in `/dev/shm/appstore/`, with a persistent
  fallback up to 24 h old. **A wiki edit takes up to about 2 h** to show up.
- **Install button** → `/admin/system/plugininstall.cgi?url=<zip>`, then the normal
  installer with SecurePIN. It only shows if `zip` is http(s) and the running LB version
  ≥ `min_lb_version`. Otherwise you get a version hint, or "open repo" when only `repo` is set.
- **The AppStore never updates plugins.** Updates come only via `release.cfg` (5.2).
  The wiki `Release Download` is what **new** users install. If it is stale, they install
  an old version and get updated later through autoupdate.

### 6.2 Wiki data box → catalog fields

| Wiki label | JSON | Effect |
|---|---|---|
| page title (H1) | `title` | Card title, search, **installed detection** (6.3) |
| Autor | `author` | "by …" |
| Logo | `logo` | Card icon |
| Status | `status` | Badge: `STABLE`, `BETA`, `UNSTABLE`, `ALPHA`, `STOPPED` |
| Version | `version` | Shown as `v…` (display only, never compared with installs) |
| Min. LB Version | `min_lb_version` | Gates the install button |
| Release Download | `zip` | Install URL. Must be `http(s)` |
| (repo field) | `repo` | Fallback button when there is no zip |
| Beschreibung | `description` | Card text, search |
| Sprachen | `languages` | Tag |
| (forum field) | `forum` | Forum button |
| – | `wiki`, `lastmodified` | Page link. Last edit date drives the default sort |

Current bold2lox entry (2026-10-14): title `bold2lox – Bold Smart Lock for Loxone`,
STABLE, version 0.2.2, min LB `3`, zip = `v0.2.2` tag archive, `repo`/`forum` empty,
languages `en`, wiki https://wiki.loxberry.de/plugins/bold2lox/start.

### 6.3 Installed detection (important)

The AppStore marks a plugin as installed if **only the title** matches: lower-cased,
with every non-`[a-z0-9]` stripped. It compares the wiki title against the local
`PLUGINDB_TITLE`, which is `plugin.cfg TITLE` **after** the 25-char truncation.
Author is ignored. If they differ, users who already have the plugin see an "Install"
button. Clicking it reinstalls the same plugin as an upgrade: harmless but confusing.
**Keep the wiki title and `TITLE` equal after normalisation, and `TITLE` ≤ 25 chars.**

## 7. Known open points (as of 2026-10-14)

- `TITLE` was `Bold Smart Lock for Loxone` (26 chars, shown as `Bold Smart Lock for Lo...`)
  up to v0.2.2. It is now `bold2lox`. **Still to do:** rename the wiki page H1 to
  `bold2lox`, otherwise the AppStore title match (6.3) keeps failing. The new `TITLE`
  reaches users with the next release.
- The wiki page text still describes two `.LxAddOn` templates with UDP port. The current
  code ships one output template. Update it with the next stable release.
- Wiki data box: fill the repo field (GitHub URL) and the forum field once a LoxForum thread exists.
- Hardcoded `/opt/loxberry/...` and `/plugins/bold2lox/` paths (see 3).
