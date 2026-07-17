<?php
/**
 * bold2lox – erzeugt Loxone-Config-Vorlagen (.lxAddon) zum Download.
 *
 *   template.php?type=vo   Virtueller Ausgang: Schloss auslösen (open/close)
 *   template.php?type=vi   Virtueller UDP-Eingang: Status (online/ausgeloest)
 *
 * Eine .lxAddon-Datei kann laut Loxone nur Eingaenge ODER Ausgaenge enthalten,
 * daher zwei getrennte Dateien. XML-Struktur entspricht dem LoxBerry-
 * TemplateBuilder (der VirtualOut-Zweig des Moduls ist fehlerhaft, daher hier
 * direkt und korrekt erzeugt).
 */
require_once "loxberry_system.php";
require_once "Bold.php";

$bold = new Bold();
$settings = $bold->readSettings();

$ip      = $_SERVER['SERVER_ADDR'] ?? 'LOXBERRY-IP';
$secret  = $settings['trigger_secret'] ?? '';
$udpPort = (int)($settings['miniserver']['udp_port'] ?? 4001);

$type = $_GET['type'] ?? 'vo';
$enc  = ENT_XML1 | ENT_QUOTES;

function attr($s, $enc) { return htmlspecialchars((string)$s, $enc); }

if ($type === 'vi') {
    $filename = 'bold2lox_status.lxAddon';
    $rows = [
        ['Bold Connect online',      'bold_gateway_online=\v'],
        ['Letzte Ausloesung ok',     'bold_action_ok=\v'],
        ['Letzte Ausloesung (Zeit)', 'bold_last_action=\v'],
    ];
    $xml  = '<?xml version="1.0" encoding="utf-8"?>' . "\r\n";
    $xml .= '<VirtualInUdp Title="Bold Smart Lock Status" Comment="bold2lox" Address="" Port="' . $udpPort . '" >' . "\r\n";
    foreach ($rows as $r) {
        $xml .= "\t" . '<VirtualInUdpCmd Title="' . attr($r[0], $enc) . '" Comment="" Address="" '
              . 'Check="' . attr($r[1], $enc) . '" Signed="true" Analog="true" '
              . 'SourceValLow="0" DestValLow="0" SourceValHigh="100" DestValHigh="100" '
              . 'DefVal="0" MinVal="-2147483647" MaxVal="2147483647"/>' . "\r\n";
    }
    $xml .= '</VirtualInUdp>' . "\r\n";
} else {
    $filename = 'bold2lox_output.lxAddon';
    $base    = 'http://' . $ip;
    $cmdOpen  = '/plugins/bold2lox/activate.php?key=' . rawurlencode($secret) . '&cmd=open';
    $cmdClose = '/plugins/bold2lox/activate.php?key=' . rawurlencode($secret) . '&cmd=close';
    $xml  = '<?xml version="1.0" encoding="utf-8"?>' . "\r\n";
    $xml .= '<VirtualOut Title="Bold Smart Lock" Comment="bold2lox" Address="' . attr($base, $enc) . '" '
          . 'CmdInit="" CloseAfterSend="true" CmdSep=";" >' . "\r\n";
    $xml .= "\t" . '<VirtualOutCmd Title="Hauseingang oeffnen" Comment="" '
          . 'CmdOnMethod="GET" CmdOn="' . attr($cmdOpen, $enc) . '" CmdOnHTTP="" CmdOnPost="" '
          . 'CmdOffMethod="GET" CmdOff="' . attr($cmdClose, $enc) . '" CmdOffHTTP="" CmdOffPost="" '
          . 'Analog="false" Repeat="0" RepeatRate="0"/>' . "\r\n";
    $xml .= '</VirtualOut>' . "\r\n";
}

header('Content-Type: application/xml; charset=utf-8');
header('Content-Disposition: attachment; filename="' . $filename . '"');
header('Content-Length: ' . strlen($xml));
echo $xml;
