<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";
require_once "Bold.php";

error_reporting(E_ALL);
ini_set('display_errors', 1);

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=6'>";

$bold = new Bold();

require_once "navigation.php";
$navbar[3]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");

$successMessage = "";
$errorMessage = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Tokens are not part of the form - only the engine writes them.
    $saved = $bold->saveSettings([
        'bold' => [
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
    if (!$saved) {
        $errorMessage = $L['SETTINGS.SAVE_ERROR'];
    } else {
        $successMessage = $L['COMMON.SAVED'];

        $result = $bold->restartService();
        if ($result['success']) {
            $successMessage .= "<br>" . $L['SETTINGS.RESTART_OK'];
        } else {
            $errorMessage = $L['SETTINGS.RESTART_ERROR'] . "<br>" . implode("<br>", $result['output']);
        }
    }
}

$settings = $bold->readSettings();
$connected = !empty($settings['bold']['refresh_token']);
// Set by the engine when Bold rejected the refresh token (invalid_grant).
$relogin = $connected && !empty($settings['bold']['relogin_required']);

// Load the device list from Bold once the account is connected (pointless with a
// rejected token - it would only add another failed refresh to the log).
$devices = ($connected && !$relogin) ? $bold->discover() : [];

$val = fn($key, $default = '') => htmlspecialchars((string)($settings['bold'][$key] ?? $default));
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

    <!-- Bold account -->
    <h2><?= $L['SETTINGS.BOLD_SECTION'] ?></h2>
    <?php $accountOk = $connected && !$relogin; ?>
    <div class="diag-step <?= $accountOk ? 'ok' : 'bad' ?>">
        <span class="mark"><?= $accountOk ? '✓' : '✗' ?></span>
        <span class="detail"><?= $relogin ? $L['SETTINGS.ACCOUNT_RELOGIN']
            : ($connected ? $L['SETTINGS.ACCOUNT_CONNECTED'] : $L['SETTINGS.ACCOUNT_DISCONNECTED']) ?></span>
    </div>
    <p><a href="login.php" class="ui-btn ui-btn-<?= $accountOk ? 'a' : 'b' ?> ui-corner-all ui-btn-inline">
        <?= $connected ? $L['SETTINGS.RELOGIN_BTN'] : $L['SETTINGS.LOGIN_BTN'] ?>
    </a></p>

    <!-- Lock -->
    <h2><?= $L['SETTINGS.DEVICE'] ?></h2>
    <?php if ($devices): ?>
        <div class="ui-field-contain">
            <label for="device_pick"><?= $L['SETTINGS.DEVICE_HELP'] ?></label>
            <select id="device_pick">
                <option value="">–</option>
                <?php foreach ($devices as $d): ?>
                    <option value="<?= htmlspecialchars((string)$d['id']) ?>|<?= htmlspecialchars((string)$d['gatewayId']) ?>"
                        <?= ((string)($settings['bold']['device_id'] ?? '') === (string)$d['id']) ? 'selected' : '' ?>>
                        <?= htmlspecialchars((string)$d['name']) ?> (id <?= htmlspecialchars((string)$d['id']) ?>)
                    </option>
                <?php endforeach; ?>
            </select>
        </div>
    <?php elseif ($connected): ?>
        <p class="hint"><?= $L['SETTINGS.DISCOVER_ERROR'] ?></p>
    <?php else: ?>
        <p class="hint"><?= $L['SETTINGS.DEVICE_HELP'] ?></p>
    <?php endif; ?>
    <div class="ui-field-contain">
        <label for="device_id"><?= $L['SETTINGS.DEVICE_ID'] ?></label>
        <input type="number" id="device_id" name="device_id" value="<?= $val('device_id', 0) ?>">
    </div>
    <div class="ui-field-contain">
        <label for="gateway_id"><?= $L['SETTINGS.GATEWAY_ID'] ?></label>
        <input type="number" id="gateway_id" name="gateway_id" value="<?= $val('gateway_id', 0) ?>">
    </div>
    <p class="hint"><?= $L['SETTINGS.DEVICE_IDS_HELP'] ?></p>

    <!-- Test connection -->
    <h2><?= $L['SETTINGS.TEST_SECTION'] ?></h2>
    <p class="hint"><?= $L['SETTINGS.TEST_HINT'] ?></p>
    <button type="button" id="btnDiagnose" class="ui-btn ui-btn-a ui-corner-all ui-btn-inline"><?= $L['SETTINGS.DIAGNOSE_BTN'] ?></button>
    <button type="button" id="btnActivateTest" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['SETTINGS.ACTIVATE_BTN'] ?></button>
    <div id="diagResult" class="diag-result"></div>

    <?php $authLog = $bold->authLog(30); ?>
    <div data-role="collapsible" data-collapsed="true" data-inset="true">
        <h3><?= $L['SETTINGS.AUTH_LOG'] ?></h3>
        <p class="hint"><?= $L['SETTINGS.AUTH_LOG_HELP'] ?></p>
        <?php if ($authLog): ?>
            <pre class="auth-log"><?= htmlspecialchars(implode("\n", $authLog)) ?></pre>
        <?php else: ?>
            <p class="hint"><?= $L['SETTINGS.AUTH_LOG_EMPTY'] ?></p>
        <?php endif; ?>
    </div>

    <!-- Miniserver / trigger -->
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
               value="<?= htmlspecialchars($settings['miniserver']['ip'] ?? '') ?>" placeholder="192.168.x.x">
    </div>
    <div class="ui-field-contain">
        <label for="udp_port"><?= $L['SETTINGS.UDP_PORT'] ?></label>
        <input type="number" id="udp_port" name="udp_port"
               value="<?= htmlspecialchars((string)($settings['miniserver']['udp_port'] ?? 4001)) ?>">
    </div>

    <!-- Advanced -->
    <div data-role="collapsible" data-collapsed="true" data-inset="true">
        <h3><?= $L['SETTINGS.ADVANCED'] ?></h3>
        <p class="hint"><?= $L['SETTINGS.ADVANCED_HELP'] ?></p>
        <div class="ui-field-contain">
            <label for="poll_interval"><?= $L['SETTINGS.POLL'] ?></label>
            <input type="number" id="poll_interval" name="poll_interval"
                   value="<?= htmlspecialchars((string)($settings['poll_interval_seconds'] ?? 300)) ?>">
        </div>
        <div class="ui-field-contain">
            <label for="auth_user_agent"><?= $L['SETTINGS.USER_AGENT'] ?></label>
            <input type="text" id="auth_user_agent" name="auth_user_agent"
                   value="<?= htmlspecialchars($settings['auth_user_agent'] ?? '') ?>">
            <p class="hint"><?= $L['SETTINGS.USER_AGENT_HELP'] ?></p>
        </div>
    </div>

    <button type="submit" class="ui-btn ui-btn-b ui-corner-all"><?= $L['COMMON.SAVE'] ?></button>
</form>

<script src='assets/index.js?v=5'></script>
<?php LBWeb::lbfooter(); ?>
