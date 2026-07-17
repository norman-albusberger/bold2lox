<?php
/**
 * bold2lox – lokaler Trigger-Endpoint fuer den Loxone Miniserver.
 *
 * Erreichbar unter:  http://<loxberry-ip>/plugins/bold2lox/activate.php?key=SECRET&cmd=open
 * Der Miniserver ruft das per Virtual Output (HTTP GET) auf – kein TLS, nur LAN.
 *
 * cmd=open  -> remote-activation (Standard)
 * cmd=close -> remote-deactivation
 */

header('Content-Type: text/plain; charset=utf-8');

$configPath = '/opt/loxberry/config/plugins/bold2lox/bold2lox.cfg';
$engine     = '/opt/loxberry/bin/plugins/bold2lox/bold_engine.py';

$cfg = json_decode(@file_get_contents($configPath), true);
if (!is_array($cfg)) {
    http_response_code(500);
    echo 'config-error';
    exit;
}

// Geteiltes Geheimnis pruefen (verhindert Ausloesen durch Fremde im LAN).
$key = isset($_GET['key']) ? $_GET['key'] : '';
if (!hash_equals((string) $cfg['trigger_secret'], (string) $key)) {
    http_response_code(403);
    echo 'forbidden';
    exit;
}

$cmd    = isset($_GET['cmd']) ? $_GET['cmd'] : 'open';
$action = ($cmd === 'close') ? 'deactivate' : 'activate';

$out = shell_exec(
    'BOLD2LOX_CONFIG=' . escapeshellarg($configPath) . ' ' .
    '/usr/bin/python3 ' . escapeshellarg($engine) . ' ' . escapeshellarg($action) . ' 2>&1'
);

echo trim((string) $out);
