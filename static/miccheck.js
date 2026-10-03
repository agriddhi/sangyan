/* miccheck.js - a one-click microphone diagnostic.
 *
 * Tests each layer on its own, in order, and writes the result on screen:
 *   1. Is this a secure context (HTTPS or localhost)?
 *   2. Does the browser have a speech recogniser at all?
 *   3. Will the browser give the page the microphone?  <- permission prompt
 *   4. Does speech recognition actually return any words?
 *
 * Privacy: step 3 opens the microphone, and step 4 sends audio to the
 * browser's own speech service. Nothing is recorded, stored or uploaded by
 * this app.
 */

(function () {
  "use strict";

  var report = null;
  var running = false;

  function box() {
    if (report) return report;
    var node = document.createElement("div");
    node.id = "micreport";
    node.style.cssText =
      "margin:10px 0 0;padding:12px 14px;border-radius:12px;background:#0f172a;" +
      "color:#e2e8f0;font-family:Consolas,Menlo,monospace;font-size:14px;" +
      "line-height:1.7;white-space:pre-wrap;word-break:break-word;";
    var bar = document.getElementById("voicebar");
    if (bar && bar.parentNode) bar.parentNode.insertBefore(node, bar.nextSibling);
    else document.body.appendChild(node);
    report = node;
    return node;
  }

  function say(text) {
    box().textContent = text;
  }

  function stamp(step, ok, detail) {
    var mark = ok === null ? "  .." : (ok ? " OK" : "FAIL");
    return step + " [" + mark + "] " + (detail || "") + "\n";
  }

  function addButton() {
    var bar = document.getElementById("voicebar");
    if (!bar) { window.setTimeout(addButton, 400); return; }
    if (document.getElementById("miccheckbtn")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.id = "miccheckbtn";
    button.textContent = "Check microphone";
    button.style.cssText =
      "background:#ffffff;color:#0f172a;border:1px solid #94a3b8;border-radius:12px;" +
      "padding:10px 16px;font-size:16px;cursor:pointer;margin:4px 6px 4px 0;";
    button.addEventListener("click", run);
    bar.appendChild(button);
  }

  function run() {
    if (running) return;
    running = true;
    var out = "MICROPHONE CHECK\n----------------\n";
    say(out + "\nrunning...");

    /* 1. secure context */
    var secure = window.isSecureContext !== false;
    out += stamp("1. secure context (needs https or localhost)", secure,
                 window.location.href);

    /* 2. recogniser present */
    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    out += stamp("2. speech recogniser in this browser", !!Recognition,
                 Recognition ? "found" : "this browser has none");
    say(out);

    if (!secure || !Recognition) {
      out += "\nRESULT: the browser cannot do voice input here.\n";
      say(out);
      running = false;
      return;
    }

    /* 3. microphone permission */
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      out += stamp("3. microphone access", false, "getUserMedia is unavailable");
      out += "\nRESULT: the page cannot open the microphone.\n";
      say(out);
      running = false;
      return;
    }

    out += stamp("3. microphone access", null, "waiting for your permission...");
    say(out);

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var tracks = stream.getTracks();
      var label = tracks.length ? (tracks[0].label || "microphone") : "microphone";
      stream.getTracks().forEach(function (t) { t.stop(); });
      out += stamp("3. microphone access", true, label);
      out += "\n4. listening for 8 seconds - say anything...\n";
      say(out);
      listen(Recognition, out);
    }).catch(function (error) {
      out += stamp("3. microphone access", false,
                   (error && error.name ? error.name : "error") +
                   " - " + (error && error.message ? error.message : ""));
      out += "\nRESULT: the microphone is blocked for this page.\n" +
             "Fix: click the lock / tune icon left of the address bar, set\n" +
             "Microphone to Allow, then reload this page.\n";
      say(out);
      running = false;
    });
  }

  function listen(Recognition, out) {
    var recogniser;
    try {
      recogniser = new Recognition();
    } catch (e) {
      out += stamp("4. speech recognition", false, "could not start: " + e.message);
      say(out);
      running = false;
      return;
    }

    var text = "";
    var finished = false;
    var timer = null;

    function finish(ok, detail) {
      if (finished) return;
      finished = true;
      if (timer) window.clearTimeout(timer);
      try { recogniser.abort(); } catch (e) {}
      out += stamp("4. speech recognition", ok, detail);
      out += "\nRESULT: " + (ok
        ? "voice input works. The mic button on each part will work."
        : "voice input is blocked in Chrome for this page.") + "\n";
      say(out);
      running = false;
    }

    recogniser.lang = "en-IN";
    recogniser.continuous = true;
    recogniser.interimResults = true;
    recogniser.maxAlternatives = 1;

    recogniser.onresult = function (event) {
      for (var i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          text += event.results[i][0].transcript + " ";
          out += "\n   heard: " + text.trim();
          say(out);
        }
      }
      if (text.trim()) {
        timer = window.setTimeout(function () { finish(true, '"' + text.trim() + '"'); }, 1200);
      }
    };
    recogniser.onerror = function (event) {
      var code = (event && event.error) ? event.error : "unknown";
      var meaning = {
        "not-allowed": "microphone permission was denied",
        "service-not-allowed": "Chrome blocked the speech service for this site",
        "audio-capture": "no microphone was found",
        "network": "Chrome's speech service could not be reached (internet or firewall)",
        "no-speech": "nothing was picked up, try again closer to the mic",
        "aborted": "stopped"
      }[code] || "";
      finish(false, code + (meaning ? " - " + meaning : ""));
    };
    recogniser.onend = function () {
      finish(!!text.trim(), text.trim() ? '"' + text.trim() + '"' : "no words came back");
    };

    try {
      recogniser.start();
    } catch (e) {
      finish(false, "start failed: " + e.message);
      return;
    }
    timer = window.setTimeout(function () {
      finish(!!text.trim(), text.trim() ? '"' + text.trim() + '"' : "nothing heard in 8 seconds");
    }, 8000);
  }

  function boot() {
    addButton();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
