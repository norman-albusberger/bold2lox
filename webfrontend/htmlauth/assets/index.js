// bold2lox – Web-UI-Helfer (jQuery Mobile ist von LoxBerry vorhanden)
(function () {
    "use strict";

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        // Fallback
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta);
        return Promise.resolve();
    }

    // URL kopieren
    document.querySelectorAll(".copy-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var el = document.getElementById(btn.getAttribute("data-target"));
            if (!el) return;
            copyText(el.textContent.trim()).then(function () {
                var old = btn.textContent;
                btn.textContent = "✓";
                setTimeout(function () { btn.textContent = old; }, 1200);
            });
        });
    });

    // Test-Ausloesung
    var testBtn = document.getElementById("testOpen");
    if (testBtn) {
        testBtn.addEventListener("click", function () {
            var out = document.getElementById("testResult");
            out.textContent = "…";
            fetch(testBtn.getAttribute("data-url"))
                .then(function (r) { return r.text(); })
                .then(function (t) { out.textContent = t; })
                .catch(function (e) { out.textContent = "Fehler: " + e; });
        });
    }

    // Zufalls-Secret erzeugen
    var gen = document.getElementById("genSecret");
    if (gen) {
        gen.addEventListener("click", function () {
            var arr = new Uint8Array(24);
            (window.crypto || window.msCrypto).getRandomValues(arr);
            var s = Array.from(arr).map(function (b) {
                return ("0" + b.toString(16)).slice(-2);
            }).join("");
            document.getElementById("trigger_secret").value = s;
        });
    }

    // Geraete-Dropdown -> device_id / gateway_id fuellen
    var pick = document.getElementById("device_pick");
    if (pick) {
        pick.addEventListener("change", function () {
            var parts = pick.value.split("|");
            if (parts.length === 2) {
                document.getElementById("device_id").value = parts[0];
                document.getElementById("gateway_id").value = parts[1];
            }
        });
    }
})();
