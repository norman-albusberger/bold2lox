<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=3'>";

require_once "navigation.php";
$navbar[2]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");

// Authorize-URL der Bold-App (OAuth2 Authorization Code, feste BoldApp-Werte).
$authorizeUrl = "https://auth.boldsmartlock.com/?client_id=BoldApp"
    . "&redirect_uri=" . rawurlencode("boldsmartlock://auth")
    . "&response_type=code";
?>

<div class="ui-content">
    <p><?= $L['LOGIN.INTRO'] ?></p>

    <h2><?= $L['LOGIN.STEP1'] ?></h2>
    <p><a href="<?= htmlspecialchars($authorizeUrl) ?>" target="_blank" rel="noopener"
          class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.OPEN_BTN'] ?></a></p>
    <p class="hint"><?= $L['LOGIN.STEP1_HELP'] ?></p>

    <h2><?= $L['LOGIN.STEP2'] ?></h2>
    <p class="hint"><?= $L['LOGIN.STEP2_HELP'] ?></p>
    <div class="ui-field-contain">
        <label for="login_code"><?= $L['LOGIN.CODE'] ?></label>
        <input type="text" id="login_code" placeholder="boldsmartlock://auth?code=…">
    </div>
    <button type="button" id="btnLoginExchange" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.EXCHANGE_BTN'] ?></button>

    <!-- Erfolg -->
    <div id="loginDone" class="login-step" style="display:none">
        <div class="diag-step ok"><span class="mark">✓</span><span class="detail"><?= $L['LOGIN.SUCCESS'] ?></span></div>
        <a href="settings.php" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.GOTO_SETTINGS'] ?></a>
    </div>

    <div id="loginError" class="diag-result"></div>
</div>

<script src='assets/login.js?v=2'></script>
<?php LBWeb::lbfooter(); ?>
