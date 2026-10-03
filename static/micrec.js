/* micrec.js - records the microphone in the page and sends the clip to our
 * own /api/transcribe endpoint, because the browser's built-in recogniser is
 * blocked on many networks.
 *
 * It takes over the mic buttons that voice.js adds, so voice.js itself is
 * left untouched.
 *
 * Privacy: recording starts only when the user presses the mic button, the
 * clip lives in memory, and it is discarded as soon as the words come back.
 * Nothing is recorded to disk and nothing is stored.
 */

(function () {
  "use strict";

  var MAX_MS = 15000;
  var recorder = null;
  var chunks = [];
  var stream = null;
  var stopTimer = null;
  var current = null;          /* { input, card } */
  var busy = false;

  var T = {
    en: { listen: "Listening...", send: "Transcribing your words...",
          heard: "Heard", err: "Could not hear anything. Try again, closer to the mic.",
          denied: "The microphone is blocked for this page. Click the lock icon in the address bar and allow it.",
          noInput: "No microphone was found on this computer.",
          short: "Too short. Speak for a second or two." },
    hi: { listen: "सुन रहे हैं...", send: "आपकी बात लिखी जा रही है...",
          heard: "सुना", err: "कुछ सुनाई नहीं दिया। माइक के पास बोलकर फिर कोशिश करें।",
          denied: "इस पेज के लिए माइक बंद है। पते में ताला आइकन से अनुमति दें।",
          noInput: "इस कंप्यूटर में कोई माइक नहीं मिला।",
          short: "बहुत छोटा। एक-दो सेकंड बोलें।" },
    ta: { listen: "கேட்கிறது...", send: "உங்கள் பேச்சு எழுதப்படுகிறது...",
          heard: "கேட்டது", err: "எதுவும் கேட்க முடியவில்லை. மிக நெருக்கி மீண்டும் பேசுங்கள்.",
          denied: "இந்தப் பக்கத்திற்கு மைக்ரோஃபோன் அனுமதிக்கப்படவில்லை. பூட்டு சின்னத்திலிருந்து அனுமதிக்கவும்.",
          noInput: "இந்தக் கணினியில் மைக்ரோஃபோன் கிடைக்கவில்லை.",
          short: "மிகவும் குறைவு. ஒரு இரண்டு வினாடி பேசுங்கள்." }
  };

  function L() { return T[currentLang()] || T.en; }

  function currentLang() {
    var select = document.getElementById("voicelang");
    var value = select ? String(select.value || "").toLowerCase() : "";
    if (value === "en" || value === "hi" || value === "ta") return value;
    var any = document.querySelector("select");
    value = any ? String(any.value || "").toLowerCase() : "";
    return (value === "en" || value === "hi" || value === "ta") ? value : "en";
  }

  function say(text, kind) {
    var node = document.getElementById("voicestatus");
    if (!node) return;
    node.textContent = text || "";
    node.style.background = kind === "warn" ? "#fff7ed" : kind === "ok" ? "#f0fdf4" : "#f1f5f9";
    node.style.color = kind === "warn" ? "#9a3412" : kind === "ok" ? "#166534" : "#334155";
  }

  function isOurs(node) {
    if (!node.classList) return false;
    return node.classList.contains("voice-mic") || node.classList.contains("voice-listen");
  }

  function findAskButton(card, input) {
    if (input && input.parentNode) {
      var row = input.parentNode.querySelectorAll("button");
      for (var i = 0; i < row.length; i++) {
        if (!isOurs(row[i])) return row[i];
      }
    }
    var nodes = card.querySelectorAll("button");
    for (var j = 0; j < nodes.length; j++) {
      if (!isOurs(nodes[j]) &&
          nodes[j].textContent.trim().toLowerCase() === "ask") return nodes[j];
    }
    return null;
  }

  function paint() {
    var nodes = document.querySelectorAll(".voice-mic");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = busy ? L().listen : (current ? L().micLabel || "Ask by voice" : "Ask by voice");
      nodes[i].style.background = busy ? "#fee2e2" : "#ffffff";
      nodes[i].style.color = busy ? "#b91c1c" : "#0f172a";
    }
  }

  function stopEverything() {
    if (stopTimer) { window.clearTimeout(stopTimer); stopTimer = null; }
    if (recorder && recorder.state !== "inactive") {
      try { recorder.stop(); } catch (e) {}
    }
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
    }
    recorder = null;
    busy = false;
    paint();
  }

  function upload(blob, target) {
    if (!blob || blob.size < 1800) {
      say(L().short, "warn");
      return;
    }
    say(L().send, "ok");
    var form = new FormData();
    form.append("file", blob, "clip.webm");
    form.append("language", currentLang());

    fetch("/api/transcribe", { method: "POST", body: form })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var text = String((data && data.text) || "").trim();
        if (data && data.notice) { say(data.notice, "warn"); return; }
        if (!text) { say(L().err, "warn"); return; }
        target.input.value = text;
        try {
          target.input.dispatchEvent(new Event("input", { bubbles: true }));
        } catch (e) {}
        say(L().heard + ": " + text, "ok");
        var ask = findAskButton(target.card, target.input);
        if (ask) window.setTimeout(function () { ask.click(); }, 400);
      })
      .catch(function () {
        say("Could not reach the server. Is it still running?", "warn");
      });
  }

  function record(input, card) {
    if (busy) { stopEverything(); say("Stopped.", "ok"); return; }
    current = { input: input, card: card };

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      say(L().noInput, "warn");
      return;
    }

    say(L().listen, "ok");
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (media) {
      stream = media;
      chunks = [];
      var options = { mimeType: "audio/webm" };
      try {
        recorder = new MediaRecorder(media, options);
      } catch (e) {
        recorder = new MediaRecorder(media);
      }
      recorder.ondataavailable = function (event) {
        if (event.data && event.data.size) chunks.push(event.data);
      };
      recorder.onstop = function () {
        var blob = new Blob(chunks, { type: "audio/webm" });
        stopEverything();
        if (current) upload(blob, current);
      };
      recorder.start();
      busy = true;
      paint();
      stopTimer = window.setTimeout(function () { stopEverything(); }, MAX_MS);
    }).catch(function (error) {
      stopEverything();
      say(error && error.name === "NotAllowedError" ? L().denied : L().noInput, "warn");
    });
  }

  /* Take over every mic button before voice.js can react to it. */
  function intercept(event) {
    var node = event.target;
    while (node && node !== document.body) {
      if (node.classList && node.classList.contains("voice-mic")) break;
      node = node.parentNode;
    }
    if (!node || node === document.body) return;
    event.preventDefault();
    event.stopPropagation();
    var card = node.parentNode;
    while (card && card.id !== "results" && !card.getAttribute) break;
    card = node.closest("#results > *") || node.parentNode;
    var input = null;
    var row = node.parentNode.querySelectorAll("input");
    if (row.length) input = row[0];
    if (input) record(input, card);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      document.addEventListener("click", intercept, true);
    });
  } else {
    document.addEventListener("click", intercept, true);
  }
})();
