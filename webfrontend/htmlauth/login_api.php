<?php
/**
 * bold2lox – login proxy for the bootstrap (authenticated).
 *
 *   login_api.php?step=exchange   POST: code  (Code oder boldsmartlock://auth?code=... URL)
 *
 * Passes the code to the engine via stdin, which exchanges it for tokens.
 */
require_once "loxberry_system.php";
require_once "Bold.php";

header('Content-Type: application/json; charset=utf-8');

$bold = new Bold();
$step = $_GET['step'] ?? '';

if ($step !== 'exchange') {
    http_response_code(400);
    echo json_encode(["ok" => false, "detail" => "unknown step"]);
    exit;
}

$res = $bold->runEngineStdin('login-exchange', [
    'code' => trim($_POST['code'] ?? ''),
]);

$decoded = json_decode($res['output'], true);
if ($decoded === null) {
    echo json_encode([
        "ok" => false,
        "detail" => $res['output'] !== '' ? $res['output']
                    : ($res['stderr'] !== '' ? $res['stderr'] : 'no output'),
    ]);
} else {
    echo $res['output'];
}
