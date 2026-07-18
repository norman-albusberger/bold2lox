<?php
/**
 * bold2lox – Login-Proxy fuer den Bootstrap (authentifiziert).
 *
 *   login_api.php?step=exchange   POST: code  (Code oder boldsmartlock://auth?code=... URL)
 *
 * Reicht den Code per stdin an den Engine weiter, der ihn gegen Tokens tauscht.
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
