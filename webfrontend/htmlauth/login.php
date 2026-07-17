<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=2'>";

require_once "navigation.php";
$navbar[2]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");
?>

<div class="ui-content">
    <p><?= $L['LOGIN.INTRO'] ?></p>
    <p class="hint"><?= $L['LOGIN.NOTE'] ?></p>

    <!-- Schritt 1: Telefonnummer -->
    <div id="loginStep1" class="login-step">
        <h2><?= $L['LOGIN.STEP1'] ?></h2>
        <div class="ui-field-contain">
            <label for="login_phone"><?= $L['LOGIN.PHONE'] ?></label>
            <input type="tel" id="login_phone" placeholder="+49170…">
            <p class="hint"><?= $L['LOGIN.PHONE_HELP'] ?></p>
        </div>
        <div class="ui-field-contain">
            <label for="login_dest"><?= $L['LOGIN.DESTINATION'] ?></label>
            <select id="login_dest">
                <option value="Phone"><?= $L['LOGIN.DEST_SMS'] ?></option>
                <option value="Email"><?= $L['LOGIN.DEST_EMAIL'] ?></option>
            </select>
        </div>
        <button type="button" id="btnLoginRequest" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.REQUEST_BTN'] ?></button>
    </div>

    <!-- Schritt 2: Code -->
    <div id="loginStep2" class="login-step" style="display:none">
        <h2><?= $L['LOGIN.STEP2'] ?></h2>
        <div class="ui-field-contain">
            <label for="login_code"><?= $L['LOGIN.CODE'] ?></label>
            <input type="text" id="login_code" inputmode="numeric" autocomplete="one-time-code">
        </div>
        <button type="button" id="btnLoginVerify" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.VERIFY_BTN'] ?></button>
    </div>

    <!-- Schritt 3: Passwort -->
    <div id="loginStep3" class="login-step" style="display:none">
        <h2><?= $L['LOGIN.STEP3'] ?></h2>
        <div class="ui-field-contain">
            <label for="login_password"><?= $L['LOGIN.PASSWORD'] ?></label>
            <input type="password" id="login_password" autocomplete="current-password">
        </div>
        <button type="button" id="btnLoginAuth" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.AUTH_BTN'] ?></button>
    </div>

    <!-- Erfolg -->
    <div id="loginDone" class="login-step" style="display:none">
        <div class="diag-step ok"><span class="mark">✓</span><span class="detail"><?= $L['LOGIN.SUCCESS'] ?></span></div>
        <a href="settings.php" class="ui-btn ui-btn-b ui-corner-all ui-btn-inline"><?= $L['LOGIN.GOTO_SETTINGS'] ?></a>
    </div>

    <div id="loginError" class="diag-result"></div>
</div>

<script src='assets/login.js?v=1'></script>
<?php LBWeb::lbfooter(); ?>
