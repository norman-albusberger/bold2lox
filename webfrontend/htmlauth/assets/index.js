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

    // Test / Diagnose auf der Einstellungsseite
    function renderResult(box, data) {
        box.innerHTML = "";
        if (data && Array.isArray(data.steps)) {
            data.steps.forEach(function (s) {
                var row = document.createElement("div");
                row.className = "diag-step " + (s.ok ? "ok" : "bad");
                row.innerHTML = "<span class='mark'>" + (s.ok ? "✓" : "✗") +
                    "</span><strong>" + s.name + "</strong><span class='detail'>" +
                    (s.detail || "") + "</span>";
                box.appendChild(row);
            });
        } else if (data) {
            // activate-Antwort: {http, ok, errorCode}
            var ok = data.ok === 1 || data.ok === true;
            var row = document.createElement("div");
            row.className = "diag-step " + (ok ? "ok" : "bad");
            row.innerHTML = "<span class='mark'>" + (ok ? "✓" : "✗") +
                "</span><strong>Schloss ausgeloest</strong><span class='detail'>" +
                JSON.stringify(data) + "</span>";
            box.appendChild(row);
        }
    }

    // Speichert die aktuellen Formularwerte, damit der Test nicht gegen einen
    // veralteten gespeicherten Stand laeuft.
    function saveForm() {
        var form = document.querySelector("form");
        if (!form) return Promise.resolve();
        return fetch("save.php", { method: "POST", body: new FormData(form) })
            .then(function (r) { return r.json(); });
    }

    function runTest(what) {
        var box = document.getElementById("diagResult");
        box.innerHTML = "<div class='diag-step'>… (speichere &amp; teste)</div>";
        saveForm()
            .then(function () { return fetch("test.php?what=" + encodeURIComponent(what)); })
            .then(function (r) { return r.json(); })
            .then(function (d) { renderResult(box, d); })
            .catch(function (e) {
                box.innerHTML = "<div class='diag-step bad'><span class='mark'>✗</span>" +
                    "<span class='detail'>Fehler: " + e + "</span></div>";
            });
    }

    var btnDiag = document.getElementById("btnDiagnose");
    if (btnDiag) btnDiag.addEventListener("click", function () { runTest("diagnose"); });

    var btnAct = document.getElementById("btnActivateTest");
    if (btnAct) btnAct.addEventListener("click", function () {
        if (window.confirm("Das Schloss wird jetzt testweise ausgeloest. Fortfahren?")) {
            runTest("activate");
        }
    });

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
