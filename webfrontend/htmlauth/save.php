<?php
/**
 * bold2lox – lightweight save of the settings (authenticated), called by the
 * test buttons before diagnose/activate. No service restart, and the existing
 * access_token is kept (no forced refresh).
 */
require_once "loxberry_system.php";
require_once "Bold.php";

header('Content-Type: application/json; charset=utf-8');

$bold = new Bold();
$bold->saveSettings([
    'bold' => [
        'client_id'     => trim($_POST['client_id'] ?? ''),
        'client_secret' => trim($_POST['client_secret'] ?? ''),
        'refresh_token' => trim($_POST['refresh_token'] ?? ''),
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

echo json_encode(["ok" => true]);
