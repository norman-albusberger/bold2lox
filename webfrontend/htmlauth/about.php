<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";

$L = LBSystem::readlanguage("language.ini");
$htmlhead = "<link rel='stylesheet' type='text/css' href='assets/styles.css?v=5'>";

require_once "navigation.php";
$navbar[4]['active'] = true;
LBWeb::lbheader($L['COMMON.TITLE'], "https://github.com/norman-albusberger/bold2lox", "help.html");
?>

<div class="ui-content">
    <h2><?= $L['COMMON.ABOUT'] ?></h2>
    <p><?= $L['ABOUT.TEXT'] ?></p>
    <p><a href="https://github.com/norman-albusberger/bold2lox" target="_blank" rel="noopener">github.com/norman-albusberger/bold2lox</a></p>
</div>

<?php LBWeb::lbfooter(); ?>
