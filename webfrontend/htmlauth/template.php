<?php
/**
 * bold2lox – erzeugt Loxone-Config-Vorlagen (.LxAddOn) zum Download.
 *
 *   template.php?type=vo   Virtueller Ausgang: Schloss auslösen (open/close)
 *   template.php?type=vi   Virtueller UDP-Eingang: Status
 *
 * Format nach echten Loxone-Library-Vorlagen: eine .LxAddOn ist ein ZIP aus
 * <name>.xml + desc.json. Die XML traegt ein <Info templateType=".."/> und ein
 * UTF-8-BOM. templateType: "3" = Virtueller Ausgang, "2" = Virtueller Eingang.
 * Eine Datei kann nur Eingaenge ODER Ausgaenge enthalten -> zwei Dateien.
 */
require_once "loxberry_system.php";
require_once "Bold.php";

const LX_MIN_VERSION = "14000328";
const LX_BOM = "\xEF\xBB\xBF";

$bold = new Bold();
$settings = $bold->readSettings();

$ip      = $_SERVER['SERVER_ADDR'] ?? 'LOXBERRY-IP';
$secret  = $settings['trigger_secret'] ?? '';
$udpPort = (int)($settings['miniserver']['udp_port'] ?? 4001);

$type = $_GET['type'] ?? 'vo';
$enc  = ENT_XML1 | ENT_QUOTES;
$a = fn($s) => htmlspecialchars((string)$s, $enc);

// Der Ausgang braucht das Trigger-Secret in der URL – sonst waere die Vorlage
// kaputt (activate.php antwortet mit 403). Also erst nach Konfiguration ausliefern.
if ($type !== 'vi' && $secret === '') {
    http_response_code(409);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Set the trigger secret in Settings first.';
    exit;
}

if ($type === 'vi') {
    $name = 'bold2lox-status';
    $templateType = '2';
    $rows = [
        ['Bold Connect online',   'bold_gateway_online=\v'],
        ['Last activation OK',    'bold_action_ok=\v'],
        ['Last activation (time)', 'bold_last_action=\v'],
    ];
    $xml  = LX_BOM . '<?xml version="1.0" encoding="utf-8"?>' . "\r\n";
    $xml .= '<VirtualInUdp Title="Bold Smart Lock Status" Comment="bold2lox" Address="" Port="' . $udpPort . '">' . "\r\n";
    $xml .= "\t" . '<Info templateType="' . $templateType . '" minVersion="' . LX_MIN_VERSION . '"/>' . "\r\n";
    foreach ($rows as $r) {
        $xml .= "\t" . '<VirtualInUdpCmd Title="' . $a($r[0]) . '" Comment="" Address="" '
              . 'Check="' . $a($r[1]) . '" Signed="true" Analog="true" '
              . 'SourceValLow="0" DestValLow="0" SourceValHigh="100" DestValHigh="100" '
              . 'DefVal="0" MinVal="-2147483647" MaxVal="2147483647"/>' . "\r\n";
    }
    $xml .= '</VirtualInUdp>' . "\r\n";
} else {
    $name = 'bold2lox-output';
    $templateType = '3';
    $cmdOpen  = '/plugins/bold2lox/activate.php?key=' . rawurlencode($secret) . '&cmd=open';
    $cmdClose = '/plugins/bold2lox/activate.php?key=' . rawurlencode($secret) . '&cmd=close';
    $xml  = LX_BOM . '<?xml version="1.0" encoding="utf-8"?>' . "\r\n";
    $xml .= '<VirtualOut Title="Bold Smart Lock" Comment="bold2lox" Address="' . $a("http://$ip") . '" '
          . 'CmdInit="" CloseAfterSend="true" CmdSep="">' . "\r\n";
    $xml .= "\t" . '<Info templateType="' . $templateType . '" minVersion="' . LX_MIN_VERSION . '"/>' . "\r\n";
    $xml .= "\t" . '<VirtualOutCmd Title="Open lock" Comment="bold2lox" '
          . 'CmdOnMethod="GET" CmdOffMethod="GET" CmdOn="' . $a($cmdOpen) . '" CmdOnHTTP="" CmdOnPost="" '
          . 'CmdOff="' . $a($cmdClose) . '" CmdOffHTTP="" CmdOffPost="" CmdAnswer="" '
          . 'Analog="false" Repeat="0" RepeatRate="0"/>' . "\r\n";
    $xml .= '</VirtualOut>' . "\r\n";
}

$desc = json_encode([
    "type" => "template",
    "name" => $name,
    "uuid" => bold_uuid4(),
    "version" => "1.0.0",
    "id" => $name,
    "file" => "$name.xml",
    "templateType" => $templateType,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);

$archive = zip_store([
    "$name.xml" => $xml,
    "desc.json" => $desc,
]);

header('Content-Type: application/octet-stream');
header('Content-Disposition: attachment; filename="' . $name . '.LxAddOn"');
header('Content-Length: ' . strlen($archive));
echo $archive;


/**
 * Minimaler ZIP-Writer OHNE ext-zip. Nutzt Deflate (Methode 8) wie die echten
 * Loxone-Library-Vorlagen; faellt auf Store zurueck, falls gzdeflate fehlt.
 * $files = [name => inhalt].
 */
function zip_store(array $files): string
{
    $local = '';
    $central = '';
    $offset = 0;
    $count = 0;
    foreach ($files as $fname => $data) {
        $crc = crc32($data);
        $ulen = strlen($data);
        $comp = function_exists('gzdeflate') ? gzdeflate($data, 6) : false;
        if ($comp === false) {
            $method = 0;
            $comp = $data;
        } else {
            $method = 8;
        }
        $clen = strlen($comp);
        $lh = "PK\x03\x04" . pack('v', 20) . pack('v', 0) . pack('v', $method)
            . pack('v', 0) . pack('v', 0)
            . pack('V', $crc) . pack('V', $clen) . pack('V', $ulen)
            . pack('v', strlen($fname)) . pack('v', 0) . $fname;
        $local .= $lh . $comp;
        $central .= "PK\x01\x02" . pack('v', 20) . pack('v', 20)
            . pack('v', 0) . pack('v', $method) . pack('v', 0) . pack('v', 0)
            . pack('V', $crc) . pack('V', $clen) . pack('V', $ulen)
            . pack('v', strlen($fname)) . pack('v', 0) . pack('v', 0)
            . pack('v', 0) . pack('v', 0) . pack('V', 0)
            . pack('V', $offset) . $fname;
        $offset += strlen($lh) + $clen;
        $count++;
    }
    $eocd = "PK\x05\x06" . pack('v', 0) . pack('v', 0)
        . pack('v', $count) . pack('v', $count)
        . pack('V', strlen($central)) . pack('V', strlen($local)) . pack('v', 0);
    return $local . $central . $eocd;
}

function bold_uuid4(): string
{
    $d = random_bytes(16);
    $d[6] = chr((ord($d[6]) & 0x0f) | 0x40);
    $d[8] = chr((ord($d[8]) & 0x3f) | 0x80);
    return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($d), 4));
}
