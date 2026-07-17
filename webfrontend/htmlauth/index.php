<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";
require_once "Bold.php";

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=1'>";

$bold = new Bold();
$settings = $bold->readSettings();

require_once "navigation.php";
$navbar[1]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");

$server_ip = $_SERVER['SERVER_ADDR'] ?? 'LOXBERRY-IP';
$secret    = $settings['trigger_secret'] ?? '';
$udpPort   = $settings['miniserver']['udp_port'] ?? 4001;
$hasToken  = !empty($settings['bold']['refresh_token']);
$hasDevice = !empty($settings['bold']['device_id']);
$configComplete = $hasToken && $hasDevice && $secret !== '';

$baseUrl  = "http://{$server_ip}/plugins/bold2lox/activate.php";
$openUrl  = $baseUrl . "?key=" . rawurlencode($secret) . "&cmd=open";
$closeUrl = $baseUrl . "?key=" . rawurlencode($secret) . "&cmd=close";
?>

<div class="ui-content">
    <p><?= $L['OVERVIEW.INTRO'] ?></p>

    <h2><?= $L['OVERVIEW.STATUS'] ?></h2>
    <ul class="bold-status">
        <li class="<?= $hasToken ? 'ok' : 'bad' ?>">
            <?= $hasToken ? $L['OVERVIEW.TOKEN_OK'] : $L['OVERVIEW.TOKEN_MISSING'] ?>
        </li>
        <li class="<?= $hasDevice ? 'ok' : 'bad' ?>">
            Device ID: <?= htmlspecialchars((string)($settings['bold']['device_id'] ?? '–')) ?>
            &nbsp;|&nbsp; Gateway ID: <?= htmlspecialchars((string)($settings['bold']['gateway_id'] ?? '–')) ?>
        </li>
    </ul>

    <h2><?= $L['OVERVIEW.OPEN_URL'] ?></h2>
    <div class="url-row">
        <code class="url" id="openUrl"><?= htmlspecialchars($openUrl) ?></code>
        <button class="copy-btn ui-btn ui-btn-a ui-corner-all ui-btn-inline" data-target="openUrl"><?= $L['COMMON.COPY'] ?></button>
    </div>

    <h2><?= $L['OVERVIEW.CLOSE_URL'] ?></h2>
    <div class="url-row">
        <code class="url" id="closeUrl"><?= htmlspecialchars($closeUrl) ?></code>
        <button class="copy-btn ui-btn ui-btn-a ui-corner-all ui-btn-inline" data-target="closeUrl"><?= $L['COMMON.COPY'] ?></button>
    </div>

    <p class="hint"><?= $L['OVERVIEW.UDP_HINT'] ?> <strong><?= htmlspecialchars((string)$udpPort) ?></strong>
        (<code>bold_gateway_online=\v</code>, <code>bold_action_ok=\v</code>, <code>bold_last_action=\v</code>).</p>

    <h2><?= $L['OVERVIEW.TEMPLATES'] ?></h2>
    <p class="hint"><?= $L['OVERVIEW.TEMPLATES_HELP'] ?></p>
    <?php if ($configComplete): ?>
        <p>
            <a href="template.php?type=vo" class="ui-btn ui-btn-a ui-corner-all ui-btn-inline"><?= $L['OVERVIEW.TEMPLATE_VO'] ?></a>
            <a href="template.php?type=vi" class="ui-btn ui-btn-a ui-corner-all ui-btn-inline"><?= $L['OVERVIEW.TEMPLATE_VI'] ?></a>
        </p>
    <?php else: ?>
        <p>
            <button class="ui-btn ui-btn-a ui-corner-all ui-btn-inline" disabled><?= $L['OVERVIEW.TEMPLATE_VO'] ?></button>
            <button class="ui-btn ui-btn-a ui-corner-all ui-btn-inline" disabled><?= $L['OVERVIEW.TEMPLATE_VI'] ?></button>
        </p>
        <div class="diag-step bad"><span class="mark">✗</span><span class="detail"><?= $L['OVERVIEW.TEMPLATES_LOCKED'] ?></span></div>
    <?php endif; ?>

    <h2><?= $L['COMMON.TEST'] ?></h2>
    <button id="testOpen" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"
            data-url="<?= htmlspecialchars($openUrl) ?>"
            <?= (!$hasToken || !$hasDevice || $secret === '') ? 'disabled' : '' ?>>
        <?= $L['OVERVIEW.TEST_OPEN'] ?>
    </button>
    <pre id="testResult" class="test-result"></pre>
</div>

<script src='assets/index.js?v=2'></script>
<?php LBWeb::lbfooter(); ?>
