<?php
/**
 * bold2lox – Test-/Diagnose-Endpoint fuer die Web-UI (authentifiziert).
 *
 *   test.php?what=diagnose  -> Schritt-fuer-Schritt-Check (loest NICHT aus)
 *   test.php?what=activate  -> loest das Schloss testweise AUS
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

// Der Engine gibt JSON auf stdout aus; unveraendert durchreichen.
// Falls doch kein JSON (z. B. Python-Traceback), sauber verpacken.
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
