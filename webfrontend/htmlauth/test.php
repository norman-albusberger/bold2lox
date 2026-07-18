<?php
/**
 * bold2lox – test/diagnostic endpoint for the web UI (authenticated).
 *
 *   test.php?what=diagnose  -> step-by-step check (does NOT trigger)
 *   test.php?what=activate  -> triggers the lock as a test
 *
 * Arbeitet auf den gespeicherten Einstellungen (settings.json).
 */
require_once "loxberry_system.php";
require_once "Bold.php";

header('Content-Type: application/json; charset=utf-8');

$bold = new Bold();
$what = $_GET['what'] ?? 'diagnose';

if ($what === 'activate') {
    $res = $bold->runEngine('activate');
} else {
    $res = $bold->runEngine('diagnose');
}

// The engine prints JSON on stdout; pass it through unchanged.
// If it isn't JSON (e.g. a Python traceback), wrap it cleanly.
$decoded = json_decode($res['output'], true);
if ($decoded === null) {
    echo json_encode([
        "ok" => false,
        "steps" => [[
            "name" => "Engine",
            "ok" => false,
            "detail" => $res['output'] !== '' ? $res['output'] : 'no output'
        ]]
    ]);
} else {
    echo $res['output'];
}
