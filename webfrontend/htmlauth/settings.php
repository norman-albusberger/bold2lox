<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";
require_once "Bold.php";

error_reporting(E_ALL);
ini_set('display_errors', 1);

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=1'>";

$bold = new Bold();

require_once "navigation.php";
$navbar[2]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");

$successMessage = "";
$errorMessage = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $bold->saveSettings([
        'bold' => [
            'access_token'  => trim($_POST['access_token'] ?? ''),
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
    ]);
    $successMessage = $L['COMMON.SAVED'];

    $result = $bold->restartService();
    if ($result['success']) {
        $successMessage .= "<br>" . $L['SETTINGS.RESTART_OK'];
    } else {
        $errorMessage = $L['SETTINGS.RESTART_ERROR'] . "<br>" . implode("<br>", $result['output']);
    }
}

$settings = $bold->readSettings();

// Geraeteliste holen, sofern ein Token gesetzt ist.
$devices = [];
if (!empty($settings['bold']['access_token'])) {
    $devices = $bold->discover();
}
?>

<?php if (!empty($successMessage)): ?>
    <div id="message-box" class="ui-bar ui-bar-b" role="alert"><?= $successMessage ?></div>
<?php endif; ?>
<?php if (!empty($errorMessage)): ?>
    <div id="error-box" class="ui-bar ui-bar-a" role="alert"><?= $errorMessage ?></div>
<?php endif; ?>
<script>
    setTimeout(function () { $("#message-box").fadeOut(); }, 4000);
</script>

<form method="POST" class="ui-content">
    <h2><?= $L['SETTINGS.BOLD_SECTION'] ?></h2>

    <div class="ui-field-contain">
        <label for="access_token"><?= $L['SETTINGS.ACCESS_TOKEN'] ?></label>
        <input type="text" id="access_token" name="access_token"
               value="<?= htmlspecialchars($settings['bold']['access_token'] ?? '') ?>"
               placeholder="Bearer-Token">
        <p class="hint"><?= $L['SETTINGS.ACCESS_TOKEN_HELP'] ?></p>
    </div>

    <div class="ui-field-contain">
        <label for="refresh_token"><?= $L['SETTINGS.REFRESH_TOKEN'] ?></label>
        <input type="text" id="refresh_token" name="refresh_token"
               value="<?= htmlspecialchars($settings['bold']['refresh_token'] ?? '') ?>">
    </div>

    <?php if ($devices): ?>
        <div class="ui-field-contain">
            <label for="device_pick"><?= $L['SETTINGS.DEVICE'] ?></label>
            <select id="device_pick">
                <option value=""><?= $L['SETTINGS.DEVICE_HELP'] ?></option>
                <?php foreach ($devices as $d): ?>
                    <option value="<?= htmlspecialchars((string)$d['id']) ?>|<?= htmlspecialchars((string)$d['gatewayId']) ?>"
                        <?= ((string)($settings['bold']['device_id'] ?? '') === (string)$d['id']) ? 'selected' : '' ?>>
                        <?= htmlspecialchars((string)$d['name']) ?> (id <?= htmlspecialchars((string)$d['id']) ?>)
                    </option>
                <?php endforeach; ?>
            </select>
        </div>
    <?php else: ?>
        <p class="hint"><?= $L['SETTINGS.DISCOVER_ERROR'] ?> (<?= $L['SETTINGS.DEVICE_HELP'] ?>)</p>
    <?php endif; ?>

    <div class="ui-field-contain">
        <label for="device_id"><?= $L['SETTINGS.DEVICE_ID'] ?></label>
        <input type="number" id="device_id" name="device_id"
               value="<?= htmlspecialchars((string)($settings['bold']['device_id'] ?? 0)) ?>">
    </div>
    <div class="ui-field-contain">
        <label for="gateway_id"><?= $L['SETTINGS.GATEWAY_ID'] ?></label>
        <input type="number" id="gateway_id" name="gateway_id"
               value="<?= htmlspecialchars((string)($settings['bold']['gateway_id'] ?? 0)) ?>">
    </div>

    <h2><?= $L['SETTINGS.MS_SECTION'] ?></h2>

    <div class="ui-field-contain">
        <label for="trigger_secret"><?= $L['SETTINGS.SECRET'] ?></label>
        <input type="text" id="trigger_secret" name="trigger_secret"
               value="<?= htmlspecialchars($settings['trigger_secret'] ?? '') ?>">
        <button type="button" id="genSecret" class="ui-btn ui-btn-a ui-corner-all ui-btn-inline"><?= $L['COMMON.GENERATE'] ?></button>
        <p class="hint"><?= $L['SETTINGS.SECRET_HELP'] ?></p>
    </div>

    <div class="ui-field-contain">
        <label for="ms_ip"><?= $L['SETTINGS.MS_IP'] ?></label>
        <input type="text" id="ms_ip" name="ms_ip"
               value="<?= htmlspecialchars($settings['miniserver']['ip'] ?? '') ?>"
               placeholder="192.168.x.x">
    </div>
    <div class="ui-field-contain">
        <label for="udp_port"><?= $L['SETTINGS.UDP_PORT'] ?></label>
        <input type="number" id="udp_port" name="udp_port"
               value="<?= htmlspecialchars((string)($settings['miniserver']['udp_port'] ?? 4001)) ?>">
    </div>
    <div class="ui-field-contain">
        <label for="poll_interval"><?= $L['SETTINGS.POLL'] ?></label>
        <input type="number" id="poll_interval" name="poll_interval"
               value="<?= htmlspecialchars((string)($settings['poll_interval_seconds'] ?? 300)) ?>">
    </div>

    <button type="submit" class="ui-btn ui-btn-b ui-corner-all"><?= $L['COMMON.SAVE'] ?></button>
</form>

<script src='assets/index.js?v=1'></script>
<?php LBWeb::lbfooter(); ?>
