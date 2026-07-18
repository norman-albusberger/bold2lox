<?php
/**
 * bold2lox – local trigger endpoint for the Loxone Miniserver.
 *
 * Reachable (unauthenticated, LAN only) at:
 *   http://<loxberry-ip>/plugins/bold2lox/activate.php?key=SECRET&cmd=open
 * The Miniserver calls it via a Virtual Output (HTTP GET) – no TLS needed.
 *
 * cmd=open  -> remote-activation (default)
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

// Check the shared secret (prevents triggering by strangers on the LAN).
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
