<?php
/**
 * bold2lox – lightweight save of the settings (authenticated), called by the
 * test buttons before diagnose/activate. No service restart. Tokens are never
 * part of the form - only the engine writes them (see Bold::saveSettings).
 */
require_once "loxberry_system.php";
require_once "Bold.php";

header('Content-Type: application/json; charset=utf-8');

$bold = new Bold();
$ok = $bold->saveSettings([
    'bold' => [
        'device_id'     => (int)($_POST['device_id'] ?? 0),
        'gateway_id'    => (int)($_POST['gateway_id'] ?? 0),
    ],
    'trigger_secret' => trim($_POST['trigger_secret'] ?? ''),
    'miniserver' => [
        'ip'       => trim($_POST['ms_ip'] ?? ''),
        'udp_port' => (int)($_POST['udp_port'] ?? 4001),
    ],
    'poll_interval_seconds' => (int)($_POST['poll_interval'] ?? 300),
    'auth_user_agent' => trim($_POST['auth_user_agent'] ?? ''),
]);

echo json_encode(["ok" => $ok]);
