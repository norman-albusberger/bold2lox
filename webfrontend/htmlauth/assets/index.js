// bold2lox – web UI helpers (jQuery Mobile is provided by LoxBerry)
(function () {
    "use strict";

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        // Fallback for older browsers
        var ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta);
        return Promise.resolve();
    }

    // Copy a URL to the clipboard
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

    // "Test: activate now" button on the Overview page
    var testBtn = document.getElementById("testOpen");
    if (testBtn) {
        testBtn.addEventListener("click", function () {
            var out = document.getElementById("testResult");
            out.textContent = "…";
            fetch(testBtn.getAttribute("data-url"))
                .then(function (r) { return r.text(); })
                .then(function (t) { out.textContent = t; })
                .catch(function (e) { out.textContent = "Error: " + e; });
        });
    }

    // Generate a random trigger secret
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

    // Render diagnose / activate results on the Settings page
    function renderResult(box, data) {
        box.innerHTML = "";
        if (data && Array.isArray(data.steps)) {
            data.steps.forEach(function (s) {
                // "skipped" = optional check that could not run - neutral, not a fault.
                var cls = s.skipped ? "skip" : (s.ok ? "ok" : "bad");
                var mark = s.skipped ? "–" : (s.ok ? "✓" : "✗");
                var row = document.createElement("div");
                row.className = "diag-step " + cls;
                row.innerHTML = "<span class='mark'>" + mark +
                    "</span><strong>" + s.name + "</strong><span class='detail'>" +
                    (s.detail || "") + "</span>";
                box.appendChild(row);
            });
        } else if (data) {
            // activate response: {http, ok, errorCode}
            var ok = data.ok === 1 || data.ok === true;
            var row = document.createElement("div");
            row.className = "diag-step " + (ok ? "ok" : "bad");
            row.innerHTML = "<span class='mark'>" + (ok ? "✓" : "✗") +
                "</span><strong>Lock activated</strong><span class='detail'>" +
                JSON.stringify(data) + "</span>";
            box.appendChild(row);
        }
    }

    // Save the current form values so the test runs against the latest config,
    // not a stale saved state.
    function saveForm() {
        var form = document.querySelector("form");
        if (!form) return Promise.resolve();
        return fetch("save.php", { method: "POST", body: new FormData(form) })
            .then(function (r) { return r.json(); });
    }

    function runTest(what) {
        var box = document.getElementById("diagResult");
        box.innerHTML = "<div class='diag-step'>… (saving &amp; testing)</div>";
        saveForm()
            .then(function () { return fetch("test.php?what=" + encodeURIComponent(what)); })
            .then(function (r) { return r.json(); })
            .then(function (d) { renderResult(box, d); })
            .catch(function (e) {
                box.innerHTML = "<div class='diag-step bad'><span class='mark'>✗</span>" +
                    "<span class='detail'>Error: " + e + "</span></div>";
            });
    }

    var btnDiag = document.getElementById("btnDiagnose");
    if (btnDiag) btnDiag.addEventListener("click", function () { runTest("diagnose"); });

    var btnAct = document.getElementById("btnActivateTest");
    if (btnAct) btnAct.addEventListener("click", function () {
        if (window.confirm("The lock will be activated now as a test. Continue?")) {
            runTest("activate");
        }
    });

    // Lock dropdown -> fill device_id / gateway_id
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
