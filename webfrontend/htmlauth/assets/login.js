// bold2lox – Bootstrap-Login-Wizard (3 Schritte gegen login_api.php)
(function () {
    "use strict";

    var state = { phone: "", mfaToken: "" };

    function showError(detail) {
        var box = document.getElementById("loginError");
        box.innerHTML = "<div class='diag-step bad'><span class='mark'>✗</span>" +
            "<span class='detail'>" + (detail || "Fehler") + "</span></div>";
    }

    function clearError() {
        document.getElementById("loginError").innerHTML = "";
    }

    function post(step, params) {
        var body = new URLSearchParams(params);
        return fetch("login_api.php?step=" + step, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString()
        }).then(function (r) { return r.json(); });
    }

    function busy(btn, on) {
        if (!btn) return;
        btn.disabled = on;
        btn.style.opacity = on ? "0.6" : "";
    }

    function show(id) {
        ["loginStep1", "loginStep2", "loginStep3", "loginDone"].forEach(function (s) {
            var el = document.getElementById(s);
            if (el) el.style.display = (s === id) ? "" : "none";
        });
    }

    var b1 = document.getElementById("btnLoginRequest");
    if (b1) b1.addEventListener("click", function () {
        clearError();
        state.phone = document.getElementById("login_phone").value.trim();
        if (!state.phone) { showError("Bitte Telefonnummer eingeben."); return; }
        busy(b1, true);
        post("request", {
            phone: state.phone,
            destination: document.getElementById("login_dest").value
        }).then(function (d) {
            busy(b1, false);
            if (d.ok) { show("loginStep2"); } else { showError(d.detail); }
        }).catch(function (e) { busy(b1, false); showError(String(e)); });
    });

    var b2 = document.getElementById("btnLoginVerify");
    if (b2) b2.addEventListener("click", function () {
        clearError();
        var code = document.getElementById("login_code").value.trim();
        if (!code) { showError("Bitte Code eingeben."); return; }
        busy(b2, true);
        post("verify", { phone: state.phone, code: code }).then(function (d) {
            busy(b2, false);
            if (d.ok) { state.mfaToken = d.verificationToken || ""; show("loginStep3"); }
            else { showError(d.detail); }
        }).catch(function (e) { busy(b2, false); showError(String(e)); });
    });

    var b3 = document.getElementById("btnLoginAuth");
    if (b3) b3.addEventListener("click", function () {
        clearError();
        var pw = document.getElementById("login_password").value;
        if (!pw) { showError("Bitte Passwort eingeben."); return; }
        busy(b3, true);
        post("auth", {
            phone: state.phone,
            password: pw,
            mfa_token: state.mfaToken
        }).then(function (d) {
            busy(b3, false);
            if (d.ok) { show("loginDone"); } else { showError(d.detail); }
        }).catch(function (e) { busy(b3, false); showError(String(e)); });
    });
})();
