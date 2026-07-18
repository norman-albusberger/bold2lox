// bold2lox – bootstrap login (OAuth2 authorization code): code -> tokens
(function () {
    "use strict";

    var strings = window.bold2loxLogin || {};
    var input = document.getElementById("login_code");
    var btn = document.getElementById("btnLoginExchange");
    var errorBox = document.getElementById("loginError");

    function showError(detail) {
        errorBox.innerHTML =
            "<div class='diag-step bad'><span class='mark'>✗</span>" +
            "<span class='detail'>" + (detail || "Error") + "</span></div>";
    }

    function clearError() {
        errorBox.innerHTML = "";
    }

    function busy(on) {
        if (!btn) return;
        btn.disabled = on;
        btn.style.opacity = on ? "0.6" : "";
    }

    function looksLikeCode(value) {
        // Accept the full boldsmartlock://…code=… URL or a bare token.
        return value.indexOf("code=") !== -1 || /^[0-9a-fA-F-]{8,}$/.test(value);
    }

    function submit() {
        clearError();
        var code = (input.value || "").trim();
        if (!code) { showError(strings.invalid); input.focus(); return; }
        if (!looksLikeCode(code)) { showError(strings.invalid); input.focus(); return; }
        busy(true);
        fetch("login_api.php?step=exchange", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ code: code }).toString()
        }).then(function (r) { return r.json(); })
          .then(function (d) {
              busy(false);
              if (d.ok) {
                  document.getElementById("loginDone").style.display = "";
                  btn.style.display = "none";
                  input.disabled = true;
              } else {
                  showError(d.detail || ("Status " + (d.status || "?")));
              }
          })
          .catch(function (e) { busy(false); showError(String(e)); });
    }

    if (btn) btn.addEventListener("click", submit);
    if (input) {
        input.focus();
        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); submit(); }
        });
    }
})();
