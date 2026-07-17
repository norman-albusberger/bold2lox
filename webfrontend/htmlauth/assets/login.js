// bold2lox – Bootstrap-Login (OAuth2 Authorization Code): Code -> Tokens
(function () {
    "use strict";

    function showError(detail) {
        document.getElementById("loginError").innerHTML =
            "<div class='diag-step bad'><span class='mark'>✗</span>" +
            "<span class='detail'>" + (detail || "Fehler") + "</span></div>";
    }

    function busy(btn, on) {
        if (!btn) return;
        btn.disabled = on;
        btn.style.opacity = on ? "0.6" : "";
    }

    var btn = document.getElementById("btnLoginExchange");
    if (btn) btn.addEventListener("click", function () {
        document.getElementById("loginError").innerHTML = "";
        var code = document.getElementById("login_code").value.trim();
        if (!code) { showError("Bitte den Code (oder die boldsmartlock://-URL) einfügen."); return; }
        busy(btn, true);
        fetch("login_api.php?step=exchange", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ code: code }).toString()
        }).then(function (r) { return r.json(); })
          .then(function (d) {
              busy(btn, false);
              if (d.ok) {
                  document.getElementById("loginDone").style.display = "";
                  btn.style.display = "none";
              } else {
                  showError(d.detail || ("Status " + (d.status || "?")));
              }
          })
          .catch(function (e) { busy(btn, false); showError(String(e)); });
    });
})();
