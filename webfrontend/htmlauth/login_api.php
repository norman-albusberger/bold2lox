<?php
/**
 * bold2lox – Login-Proxy fuer den Bootstrap-Wizard (authentifiziert).
 *
 *   login_api.php?step=request   POST: phone, destination
 *   login_api.php?step=verify    POST: phone, code
 *   login_api.php?step=auth      POST: phone, password, mfa_token
 *
 * Reicht die Werte per stdin an den Engine weiter (nicht ueber die Prozessliste).
 */
require_once "loxberry_system.php";
require_once "Bold.php";

header('Content-Type: application/json; charset=utf-8');

$bold = new Bold();
$step = $_GET['step'] ?? '';

switch ($step) {
    case 'request':
        $res = $bold->runEngineStdin('login-request', [
            'phone'       => trim($_POST['phone'] ?? ''),
            'destination' => ($_POST['destination'] ?? 'Phone') === 'Email' ? 'Email' : 'Phone',
            'language'    => 'en',
        ]);
        break;
    case 'verify':
        $res = $bold->runEngineStdin('login-verify', [
            'phone' => trim($_POST['phone'] ?? ''),
            'code'  => trim($_POST['code'] ?? ''),
        ]);
        break;
    case 'auth':
        $res = $bold->runEngineStdin('login-auth', [
            'phone'     => trim($_POST['phone'] ?? ''),
            'password'  => (string)($_POST['password'] ?? ''),
            'mfa_token' => trim($_POST['mfa_token'] ?? ''),
        ]);
        break;
    default:
        http_response_code(400);
        echo json_encode(["ok" => false, "detail" => "unbekannter step"]);
        exit;
}

$decoded = json_decode($res['output'], true);
if ($decoded === null) {
    echo json_encode([
        "ok" => false,
        "detail" => $res['output'] !== '' ? $res['output']
                    : ($res['stderr'] !== '' ? $res['stderr'] : 'keine Ausgabe'),
    ]);
} else {
    echo $res['output'];
}
