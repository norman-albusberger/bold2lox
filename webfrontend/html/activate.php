<?php
/**
 * bold2lox – lokaler Trigger-Endpoint fuer den Loxone Miniserver.
 *
 * Erreichbar (unauthentifiziert, nur LAN) unter:
 *   http://<loxberry-ip>/plugins/bold2lox/activate.php?key=SECRET&cmd=open
 * Der Miniserver ruft das per Virtual Output (HTTP GET) auf – kein TLS noetig.
 *
 * cmd=open  -> remote-activation (Standard)
 * cmd=close -> remote-deactivation
 */

header('Content-Type: text/plain; charset=utf-8');

$settingsPath = '/opt/loxberry/data/plugins/bold2lox/settings.json';
$engine       = '/opt/loxberry/bin/plugins/bold2lox/bold_engine.py';

$cfg = json_decode(@file_get_contents($settingsPath), true);
if (!is_array($cfg)) {
    http_response_code(500);
    echo 'config-error';
    exit;
}

// Geteiltes Geheimnis pruefen (verhindert Ausloesen durch Fremde im LAN).
$secret = isset($cfg['trigger_secret']) ? (string) $cfg['trigger_secret'] : '';
$key    = isset($_GET['key']) ? (string) $_GET['key'] : '';
if ($secret === '' || !hash_equals($secret, $key)) {
    http_response_code(403);
    echo 'forbidden';
    exit;
}

$cmd    = isset($_GET['cmd']) ? $_GET['cmd'] : 'open';
$action = ($cmd === 'close') ? 'deactivate' : 'activate';

$out = shell_exec(
    'BOLD2LOX_SETTINGS=' . escapeshellarg($settingsPath) . ' ' .
    '/usr/bin/python3 ' . escapeshellarg($engine) . ' ' . escapeshellarg($action) . ' 2>&1'
);

echo trim((string) $out);
