/* voice.js - the voice layer for the document reader.
 *
 * Adds, without touching the rest of the app:
 *   - a start screen: choose language, choose Listen or Read
 *   - a toolbar: check voice, previous part, play/pause, stop, next part,
 *     repeat, voice on/off, guidance on/off, a language picker, a Voices
 *     report
 *   - a "Listen to this part" button on every part
 *   - a microphone button on every question box
 *   - a live status line
 *
 * Three things this file gets right that the earlier version did not:
 *   1. After dictation it clicks the real Ask button, never the mic button.
 *   2. Dictation keeps listening while you speak (continuous), shows the
 *      words live, and sends about a second after you stop.
 *   3. The chosen language is never silently swapped. If that language has no
 *      voice installed, the app says so and names the fix.
 *
 * Stability rules:
 *   - No MutationObserver; parts are found on a timer.
 *   - A button's label is written only when the text actually changes.
 *   - A re-entrancy guard on the scan.
 *
 * Privacy: audio is handled by your browser's own speech recognition only
 * after you press the microphone button. Some browsers send that audio to
 * their provider. This app never records, stores or uploads audio.
 */

(function () {
  "use strict";

  /* ------------------------------------------------------------- language */

  var LANG_TAG = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };
  var LANG_NAME = { en: "English", hi: "Hindi", ta: "Tamil" };
  var LANG_MENU = [["en", "English"], ["hi", "हिन्दी"], ["ta", "தமிழ்"]];
  var MAX_PART_CHARS = 1200;

  var STRINGS = {
    en: {
      startTitle: "Choose how you want to read",
      startLang: "Language",
      listen: "Listen",
      read: "Read it myself",
      welcome: "Welcome. Paste any financial document in the box, then press the button to explain it. Every part has a Listen button, and every part has a box where you can ask about any word or line.",
      saved: "Your choice is saved. Change it any time with the buttons below.",
      test: "Check voice",
      voices: "Voices",
      prev: "Previous part",
      play: "Play",
      pause: "Pause",
      stop: "Stop",
      next: "Next part",
      repeat: "Repeat this part",
      voiceOn: "Voice on",
      voiceOff: "Voice off",
      guideOn: "Guidance on",
      guideOff: "Guidance off",
      listenPart: "Listen to this part",
      mic: "Ask by voice",
      micStart: "Listening",
      micSend: "Sending your question...",
      micNo: "This browser has no voice typing. Please type your question instead.",
      micErr: "Voice typing could not start. Click the lock icon in the address bar, allow the microphone, then reload.",
      micHeard: "Heard",
      none: "Nothing to read yet. Explain a document first.",
      ready: "Ready.",
      partOf: "Part",
      of: "of",
      guideEnd: "That is the end of this part. Press next part to continue, or ask a question in the box below.",
      noVoice: "No voice is installed on this computer for the language you chose. Press the Voices button to see what is installed, or switch to English or Read mode.",
      voiceOk: "Voice is working."
    },
    hi: {
      startTitle: "चुनें कि आप कैसे पढ़ना चाहते हैं",
      startLang: "भाषा",
      listen: "सुनना है",
      read: "खुद पढ़ूँगा",
      welcome: "स्वागत है। बॉक्स में कोई भी वित्तीय दस्तावेज़ पेस्ट करें, फिर समझाने का बटन दबाएँ। हर हिस्से पर सुनने का बटन है, और हर हिस्से में एक बॉक्स है जहाँ कोई भी शब्द या लाइन पूछ सकते हैं।",
      saved: "आपकी पसंद सहेज ली गई है। नीचे के बटन से कभी भी बदलें।",
      test: "आवाज़ जाँचें",
      voices: "आवाज़ें",
      prev: "पिछला हिस्सा",
      play: "चलाएँ",
      pause: "रोकें",
      stop: "बंद",
      next: "अगला हिस्सा",
      repeat: "यह हिस्सा दोहराएँ",
      voiceOn: "आवाज़ चालू",
      voiceOff: "आवाज़ बंद",
      guideOn: "मार्गदर्शन चालू",
      guideOff: "मार्गदर्शन बंद",
      listenPart: "यह हिस्सा सुनें",
      mic: "बोलकर पूछें",
      micStart: "सुन रहे हैं",
      micSend: "आपका प्रश्न भेजा जा रहा है...",
      micNo: "इस ब्राउज़र में बोलकर लिखने की सुविधा नहीं है। कृपया प्रश्न लिखें।",
      micErr: "बोलकर लिखना शुरू नहीं हुआ। पते में ताला आइकन दबाएँ, माइक की अनुमति दें, फिर पेज दोबारा खोलें।",
      micHeard: "सुना",
      none: "अभी पढ़ने के लिए कुछ नहीं है। पहले दस्तावेज़ समझाएँ।",
      ready: "तैयार है।",
      partOf: "हिस्सा",
      of: "में से",
      guideEnd: "यह हिस्सा यहाँ समाप्त। अगले हिस्से के लिए अगला बटन दबाएँ, या नीचे के बॉक्स में प्रश्न पूछें।",
      noVoice: "आपने चुनी भाषा की आवाज़ इस कंप्यूटर पर इंस्टॉल नहीं है। कौन सी आवाज़ें इंस्टॉल हैं यह देखने के लिए आवाज़ें बटन दबाएँ, या अंग्रेज़ी या रीड मोड चुनें।",
      voiceOk: "आवाज़ ठीक से चल रही है।"
    },
    ta: {
      startTitle: "எப்படிப் படிக்க விரும்புகிறீர்கள் என்று தேர்வு செய்யுங்கள்",
      startLang: "மொழி",
      listen: "கேட்க விரும்புகிறேன்",
      read: "நானே படிப்பேன்",
      welcome: "வரவேற்பு. பெட்டியில் எந்த நிதி ஆவணத்தையும் ஒட்டி, பின்னர் விளக்கு பொத்தானை அழுத்துங்கள். ஒவ்வொரு பகுதியிலும் கேட்கும் பொத்தான் உள்ளது, மேலும் ஒவ்வொரு பகுதியிலும் ஏதேனும் சொல் அல்லது வரியைக் கேட்கும் பெட்டி உள்ளது.",
      saved: "உங்கள் தேர்வு சேமிக்கப்பட்டது. கீழே உள்ள பொத்தான்களால் மாற்றலாம்.",
      test: "குரலைச் சரிபார்",
      voices: "குரல்கள்",
      prev: "முந்தைய பகுதி",
      play: "இயக்கு",
      pause: "நிறுத்து",
      stop: "முடி",
      next: "அடுத்த பகுதி",
      repeat: "இந்தப் பகுதியை மீண்டும்",
      voiceOn: "குரல் இயக்கம்",
      voiceOff: "குரல் அணை",
      guideOn: "வழிகாட்டல் இயக்கம்",
      guideOff: "வழிகாட்டல் அணை",
      listenPart: "இந்தப் பகுதியைக் கேட்க",
      mic: "பேசி கேளுங்கள்",
      micStart: "கேட்கிறது",
      micSend: "உங்கள் கேள்வி அனுப்பப்படுகிறது...",
      micNo: "இந்த உலாவியில் பேசி எழுதும் வசதி இல்லை. கேள்வியைத் தட்டச்சு செய்யுங்கள்.",
      micErr: "பேசி எழுதத் தொடங்க முடியவில்லை. பதிவுப் பட்டியில் பூட்டு சின்னத்தை அழுத்தி, மைக்ரோஃபோனை அனுமதித்து, பக்கத்தை மீண்டும் ஏற்றவும்.",
      micHeard: "கேட்டது",
      none: "படிக்க ஒன்றும் இல்லை. முதலில் ஆவணத்தை விளக்கவும்.",
      ready: "தயார்.",
      partOf: "பகுதி",
      of: "இல்",
      guideEnd: "இந்தப் பகுதி முடிந்தது. அடுத்த பகுதிக்கு அடுத்து என்ற பொத்தானை அழுத்தவும், அல்லது கீழே உள்ள பெட்டியில் கேள்வி கேளுங்கள்.",
      noVoice: "நீங்கள் தேர்வு செய்த மொழிக்கான குரல் இந்தக் கணினியில் நிறுவப்படவில்லை. எந்த குரல்கள் உள்ளன என்பதைக் காண குரல்கள் பொத்தானை அழுத்தவும், அல்லது ஆங்கிலம் அல்லது வாசிக்கும் முறையைத் தேர்வு செய்யுங்கள்.",
      voiceOk: "குரல் சரியாக இயங்குகிறது."
    }
  };

  function S() {
    return STRINGS[state.lang] || STRINGS.en;
  }

  var state = {
    lang: "en",
    mode: "read",
    voiceOn: true,
    guideOn: true,
    repeat: false,
    index: 0,
    parts: [],
    speaking: false,
    paused: false,
    userStarted: false
  };

  try {
    var savedRaw = window.localStorage.getItem("sangyan.voice");
    if (savedRaw) {
      var parsed = JSON.parse(savedRaw);
      if (parsed) {
        if (parsed.lang) state.lang = parsed.lang;
        if (parsed.mode) state.mode = parsed.mode;
        if (parsed.voiceOn === false) state.voiceOn = false;
        if (parsed.guideOn === false) state.guideOn = false;
        state.userStarted = !!parsed.started;
      }
    }
  } catch (e) { /* storage may be blocked */ }

  function persist() {
    try {
      window.localStorage.setItem("sangyan.voice", JSON.stringify({
        lang: state.lang, mode: state.mode,
        voiceOn: state.voiceOn, guideOn: state.guideOn,
        started: state.userStarted
      }));
    } catch (e) { /* ignore */ }
  }

  function clean(text) {
    return String(text || "").replace(/\s+/g, " ").trim();
  }

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  /* --------------------------------------------------------------- status */

  function ensureStatus() {
    var node = document.getElementById("voicestatus");
    if (node) return node;
    node = document.createElement("div");
    node.id = "voicestatus";
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    node.style.cssText =
      "margin:10px 0 0;font-size:15px;line-height:1.5;padding:10px 12px;" +
      "border-radius:10px;background:#f1f5f9;color:#334155;border:1px solid #e2e8f0;";
    var bar = document.getElementById("voicebar");
    if (bar && bar.parentNode) bar.parentNode.insertBefore(node, bar.nextSibling);
    else document.body.insertBefore(node, document.body.firstChild);
    return node;
  }

  function setStatus(text, kind) {
    var node = ensureStatus();
    setText(node, text || "");
    node.style.background = kind === "warn" ? "#fff7ed" : kind === "ok" ? "#f0fdf4" : "#f1f5f9";
    node.style.color = kind === "warn" ? "#9a3412" : kind === "ok" ? "#166534" : "#334155";
    node.style.borderColor = kind === "warn" ? "#fed7aa" : kind === "ok" ? "#bbf7d0" : "#e2e8f0";
  }

  /* -------------------------------------------------------------- toolbar */

  var barButtons = {};

  function makeButton(id, label, onClick) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.style.cssText =
      "background:#ffffff;color:#0f172a;border:1px solid #94a3b8;border-radius:12px;" +
      "padding:10px 16px;font-size:16px;cursor:pointer;margin:4px 6px 4px 0;";
    button.addEventListener("click", onClick);
    barButtons[id] = button;
    return button;
  }

  function buildBar() {
    var bar = document.getElementById("voicebar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "voicebar";
      var host = document.querySelector(".panel") || document.body.firstElementChild;
      if (host && host.parentNode) host.parentNode.insertBefore(bar, host);
      else document.body.insertBefore(bar, document.body.firstChild);
    }
    while (bar.firstChild) bar.removeChild(bar.firstChild);
    bar.style.cssText = "display:block;margin:0 0 6px;";

    bar.appendChild(makeButton("test", S().test, function () { testVoice(); }));
    bar.appendChild(makeButton("voices", S().voices, function () { reportVoices(); }));
    bar.appendChild(makeButton("prev", S().prev, function () { jump(-1); }));
    bar.appendChild(makeButton("play", S().play, function () { togglePlay(); }));
    bar.appendChild(makeButton("stop", S().stop, function () { stopAll(); }));
    bar.appendChild(makeButton("next", S().next, function () { jump(1); }));
    bar.appendChild(makeButton("repeat", S().repeat, function () { toggleRepeat(); }));
    bar.appendChild(makeButton("voice", S().voiceOn, function () { toggleVoice(); }));
    bar.appendChild(makeButton("guide", S().guideOn, function () { toggleGuide(); }));

    var picker = document.createElement("select");
    picker.id = "voicelang";
    picker.style.cssText = "font-size:16px;padding:9px 10px;border-radius:10px;" +
      "border:1px solid #cbd5e1;background:#ffffff;margin:4px 6px 4px 0;";
    for (var i = 0; i < LANG_MENU.length; i++) {
      var option = document.createElement("option");
      option.value = LANG_MENU[i][0];
      option.textContent = LANG_MENU[i][1];
      picker.appendChild(option);
    }
    picker.value = state.lang;
    picker.addEventListener("change", function () {
      state.lang = picker.value;
      persist();
      buildBar();
      scan();
      setStatus(voiceName()
        ? (LANG_NAME[state.lang] + " voice in use: " + voiceName())
        : S().noVoice, voiceName() ? "ok" : "warn");
    });
    bar.appendChild(picker);

    ensureStatus();
    paintBar();
  }

  function paintBar() {
    if (barButtons.play) {
      setText(barButtons.play, (state.speaking && !state.paused) ? S().pause : S().play);
    }
    if (barButtons.voice) setText(barButtons.voice, state.voiceOn ? S().voiceOn : S().voiceOff);
    if (barButtons.guide) setText(barButtons.guide, state.guideOn ? S().guideOn : S().guideOff);
    if (barButtons.repeat) {
      setText(barButtons.repeat, state.repeat ? (S().repeat + " ✓") : S().repeat);
      barButtons.repeat.style.background = state.repeat ? "#ccfbf1" : "#ffffff";
    }
  }

  /* --------------------------------------------------------------- speech */

  function speechReady() {
    return typeof window.speechSynthesis !== "undefined" &&
           typeof window.SpeechSynthesisUtterance !== "undefined";
  }

  function pickVoice() {
    if (!speechReady()) return null;
    var voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;
    var tag = (LANG_TAG[state.lang] || "en-IN").toLowerCase();
    var base = state.lang.toLowerCase();
    var exact = [];
    var loose = [];
    for (var i = 0; i < voices.length; i++) {
      var lang = (voices[i].lang || "").replace("_", "-").toLowerCase();
      if (lang.indexOf(tag) === 0) exact.push(voices[i]);
      else if (lang.indexOf(base) === 0) loose.push(voices[i]);
    }
    if (exact.length) return exact[0];
    if (loose.length) return loose[0];
    if (state.lang === "en") {
      for (var j = 0; j < voices.length; j++) {
        if ((voices[j].lang || "").toLowerCase().indexOf("en") === 0) return voices[j];
      }
    }
    return null;
  }

  function voiceName() {
    var voice = pickVoice();
    if (!voice) return null;
    return (voice.name || "voice") + " (" + (voice.lang || "?") + ")";
  }

  function reportVoices() {
    if (!speechReady()) {
      setStatus("This browser has no speech engine. Please use Chrome or Edge.", "warn");
      return;
    }
    var voices = window.speechSynthesis.getVoices() || [];
    var base = state.lang.toLowerCase();
    var mine = [];
    for (var i = 0; i < voices.length; i++) {
      var lang = (voices[i].lang || "").replace("_", "-").toLowerCase();
      if (lang.indexOf(base) === 0) {
        mine.push((voices[i].name || "?") + " (" + lang + ")");
      }
    }
    if (!mine.length) {
      setStatus("No " + LANG_NAME[state.lang] + " voice is installed on this computer. " +
        "There are " + voices.length + " other voices installed. On Windows: Settings, " +
        "Time and language, Speech, then add a voice for " + LANG_NAME[state.lang] + ". " +
        "Until then choose English, or use Read mode.", "warn");
      return;
    }
    setStatus(LANG_NAME[state.lang] + " voices found: " + mine.join(" · ") +
              ". Now using: " + voiceName(), "ok");
    speakText(S().voiceOk, null);
  }

  function chunk(text, size) {
    var pieces = String(text || "").match(/[^.!?।॥\n]+[.!?।॥\n]*/g);
    if (!pieces) pieces = [String(text || "")];
    var out = [];
    var buffer = "";
    for (var i = 0; i < pieces.length; i++) {
      var piece = pieces[i].trim();
      if (!piece) continue;
      if ((buffer + " " + piece).trim().length > size && buffer) {
        out.push(buffer);
        buffer = piece;
      } else {
        buffer = (buffer + " " + piece).trim();
      }
    }
    if (buffer) out.push(buffer);
    return out;
  }

  function speakText(text, onDone) {
    if (!speechReady() || !pickVoice()) {
      setStatus(S().noVoice, "warn");
      if (onDone) onDone();
      return;
    }
    var pieces = chunk(text, 200);
    var i = 0;
    function next() {
      if (i >= pieces.length) {
        if (onDone) onDone();
        return;
      }
      var utterance = new SpeechSynthesisUtterance(pieces[i++]);
      var voice = pickVoice();
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      } else {
        utterance.lang = LANG_TAG[state.lang] || "en-IN";
      }
      utterance.rate = 0.92;
      utterance.pitch = 1;
      utterance.onend = next;
      utterance.onerror = next;
      try {
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        next();
      }
    }
    next();
  }

  function stopAll() {
    if (speechReady()) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    state.speaking = false;
    state.paused = false;
    paintBar();
    setPartButtons();
  }

  function testVoice() {
    if (!state.voiceOn) toggleVoice();
    var name = voiceName();
    if (!name) {
      setStatus(S().noVoice, "warn");
      return;
    }
    setStatus(LANG_NAME[state.lang] + " voice: " + name, "ok");
    speakText(S().voiceOk + " " + S().welcome, null);
  }

  /* ---------------------------------------------------------------- parts */

  function collectParts() {
    var results = document.getElementById("results");
    var parts = [];
    if (!results) return parts;
    var children = results.children;
    for (var i = 0; i < children.length; i++) {
      var card = children[i];
      if (!card || card.nodeType !== 1) continue;
      var title = card.__voiceTitle;
      var text = card.__voiceText;
      if (title === undefined || text === undefined) {
        var head = card.querySelector("h1,h2,h3,h4");
        title = head ? clean(head.innerText) : ("Part " + (i + 1));
        text = clean(card.innerText);
        card.__voiceTitle = title;
        card.__voiceText = text;
      }
      if (!text) continue;
      parts.push({
        el: card,
        title: String(title).slice(0, 140),
        text: String(text).slice(0, MAX_PART_CHARS)
      });
    }
    return parts;
  }

  function refreshParts() {
    state.parts = collectParts();
    if (state.index >= state.parts.length) {
      state.index = state.parts.length ? state.parts.length - 1 : 0;
    }
    return state.parts;
  }

  function highlightPart() {
    for (var i = 0; i < state.parts.length; i++) {
      state.parts[i].el.style.boxShadow = "";
    }
    var current = state.parts[state.index];
    if (current) {
      current.el.style.boxShadow = "0 0 0 3px #14b8a6";
      try {
        current.el.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch (e) { /* older browser */ }
    }
  }

  function speakPart(index, onDone) {
    if (!state.voiceOn) { if (onDone) onDone(); return; }
    if (!state.parts.length) {
      setStatus(S().none, "warn");
      if (onDone) onDone();
      return;
    }
    if (index < 0) index = 0;
    if (index >= state.parts.length) index = 0;
    state.index = index;

    var part = state.parts[index];
    state.speaking = true;
    state.paused = false;
    paintBar();
    setPartButtons();
    highlightPart();
    setStatus(S().partOf + " " + (index + 1) + " " + S().of + " " +
              state.parts.length + " · " + part.title, "ok");

    speakText(part.title + ". " + part.text, function () {
      if (state.repeat) {
        window.setTimeout(function () { speakPart(index, onDone); }, 400);
        return;
      }
      state.speaking = false;
      state.paused = false;
      paintBar();
      setPartButtons();
      if (state.guideOn && state.mode === "listen") speakText(S().guideEnd, null);
      if (onDone) onDone();
    });
  }

  function togglePlay() {
    refreshParts();
    if (!state.parts.length) { setStatus(S().none, "warn"); return; }
    if (state.speaking && !state.paused) {
      if (speechReady()) { try { window.speechSynthesis.pause(); } catch (e) {} }
      state.paused = true;
      paintBar();
      setPartButtons();
      setStatus(S().pause, "ok");
      return;
    }
    if (state.speaking && state.paused) {
      if (speechReady()) { try { window.speechSynthesis.resume(); } catch (e) {} }
      state.paused = false;
      paintBar();
      setPartButtons();
      return;
    }
    if (state.mode === "read") { setMode("listen"); return; }
    speakPart(state.index, null);
  }

  function jump(step) {
    refreshParts();
    if (!state.parts.length) { setStatus(S().none, "warn"); return; }
    var target = state.index + step;
    if (target < 0) target = 0;
    if (target >= state.parts.length) target = state.parts.length - 1;
    if (state.speaking || step > 0) {
      stopAll();
      speakPart(target, null);
    } else {
      state.index = target;
      highlightPart();
      setStatus(S().partOf + " " + (target + 1) + " " + S().of + " " +
                state.parts.length, "ok");
    }
  }

  function toggleRepeat() {
    state.repeat = !state.repeat;
    paintBar();
  }

  function toggleVoice() {
    state.voiceOn = !state.voiceOn;
    if (!state.voiceOn) stopAll();
    persist();
    paintBar();
    if (state.voiceOn) testVoice();
    else setStatus(S().voiceOff, "ok");
  }

  function toggleGuide() {
    state.guideOn = !state.guideOn;
    persist();
    paintBar();
    if (state.guideOn) speakText(S().guideEnd, null);
    else setStatus("", null);
  }

  function setMode(mode) {
    state.mode = mode;
    if (mode === "read") stopAll();
    persist();
    document.body.setAttribute("data-voice-mode", mode);
  }

  /* ------------------------------------------------------------------ mic */

  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognition = null;
  var listening = false;
  var heard = "";
  var micTimer = null;
  var submitted = false;

  /* The Ask button is the OTHER button in the input's own row.
     Our own buttons are always skipped, so we can never click ourselves. */
  function findAskButton(card, input) {
    if (input && input.parentNode) {
      var row = input.parentNode.querySelectorAll("button");
      for (var i = 0; i < row.length; i++) {
        if (isOurs(row[i])) continue;
        return row[i];
      }
    }
    var nodes = card.querySelectorAll("button");
    for (var j = 0; j < nodes.length; j++) {
      if (isOurs(nodes[j])) continue;
      if (clean(nodes[j].textContent).toLowerCase() === "ask") return nodes[j];
    }
    return null;
  }

  function isOurs(node) {
    if (!node.classList) return false;
    return node.classList.contains("voice-mic") || node.classList.contains("voice-listen");
  }

  function paintMic() {
    var nodes = document.querySelectorAll(".voice-mic");
    var label = listening ? S().micStart : S().mic;
    for (var i = 0; i < nodes.length; i++) {
      setText(nodes[i], label);
      nodes[i].style.background = listening ? "#fee2e2" : "#ffffff";
      nodes[i].style.color = listening ? "#b91c1c" : "#0f172a";
    }
  }

  function stopMic() {
    if (micTimer) { window.clearTimeout(micTimer); micTimer = null; }
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
    }
    listening = false;
    paintMic();
  }

  function submitHeard(input, card) {
    if (submitted) return;
    var text = clean(heard);
    if (!text) { setStatus(S().micErr + " (nothing was heard)", "warn"); return; }
    submitted = true;
    input.value = text;
    try { input.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
    setStatus(S().micHeard + ": " + text, "ok");
    var ask = findAskButton(card, input);
    if (!ask) { setStatus(S().micHeard + ": " + text, "ok"); return; }
    setStatus(S().micSend, "ok");
    window.setTimeout(function () { ask.click(); }, 400);
  }

  function startMic(input, card) {
    if (listening) { stopMic(); return; }
    if (!Recognition) { setStatus(S().micNo, "warn"); return; }
    if (!state.voiceOn) toggleVoice();
    heard = "";
    submitted = false;
    try {
      recognition = new Recognition();
      recognition.lang = LANG_TAG[state.lang] || "en-IN";
      recognition.interimResults = true;
      recognition.continuous = true;
      recognition.maxAlternatives = 1;

      recognition.onresult = function (event) {
        var finals = "";
        for (var i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) finals += event.results[i][0].transcript + " ";
        }
        if (finals) {
          heard = clean(heard + " " + finals);
          if (micTimer) window.clearTimeout(micTimer);
          micTimer = window.setTimeout(function () { stopMic(); submitHeard(input, card); }, 1300);
        }
        input.value = heard;
        try { input.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
        setStatus(S().micStart + ": " + heard, "ok");
      };

      recognition.onerror = function (event) {
        listening = false;
        paintMic();
        setStatus(S().micErr + " (" + ((event && event.error) || "error") + ")", "warn");
      };

      recognition.onend = function () {
        listening = false;
        paintMic();
        if (micTimer) { window.clearTimeout(micTimer); micTimer = null; }
        submitHeard(input, card);
      };

      recognition.start();
      listening = true;
      paintMic();
      setStatus(S().micStart + " - " + LANG_NAME[state.lang], "ok");
    } catch (e) {
      listening = false;
      paintMic();
      setStatus(S().micErr, "warn");
    }
  }

  /* ------------------------------------------------------ part decoration */

  function setPartButtons() {
    var nodes = document.querySelectorAll(".voice-listen");
    for (var i = 0; i < nodes.length; i++) {
      var card = nodes[i].parentNode;
      var isCurrent = state.parts[state.index] && state.parts[state.index].el === card;
      setText(nodes[i], (state.speaking && isCurrent) ? S().pause : S().listenPart);
    }
  }

  function decorate(card) {
    if (!card || card.nodeType !== 1) return;
    if (card.getAttribute("data-voice-ready") === "1") return;
    card.setAttribute("data-voice-ready", "1");

    var head = card.querySelector("h1,h2,h3,h4");
    card.__voiceTitle = head ? clean(head.innerText) : "";
    card.__voiceText = clean(card.innerText);

    var inputs = card.querySelectorAll("input");
    for (var i = 0; i < inputs.length; i++) {
      var input = inputs[i];
      if (input.type === "hidden") continue;
      if (input.getAttribute("data-voice-mic") === "1") continue;
      input.setAttribute("data-voice-mic", "1");
      var mic = document.createElement("button");
      mic.type = "button";
      mic.className = "voice-mic";
      mic.textContent = S().mic;
      mic.title = S().mic;
      mic.style.cssText =
        "background:#ffffff;color:#0f172a;border:1px solid #94a3b8;border-radius:10px;" +
        "padding:10px 12px;font-size:15px;cursor:pointer;margin-right:6px;white-space:nowrap;";
      input.parentNode.insertBefore(mic, input);
      (function (targetInput, targetCard) {
        mic.addEventListener("click", function () { startMic(targetInput, targetCard); });
      })(input, card);
    }

    if (!card.querySelector(".voice-listen")) {
      var listen = document.createElement("button");
      listen.type = "button";
      listen.className = "voice-listen";
      listen.textContent = S().listenPart;
      listen.style.cssText =
        "display:block;margin-top:10px;background:#0f172a;color:#ffffff;border:0;" +
        "border-radius:10px;padding:10px 16px;font-size:15px;cursor:pointer;";
      card.appendChild(listen);
      (function (targetCard) {
        listen.addEventListener("click", function () {
          refreshParts();
          var position = -1;
          for (var k = 0; k < state.parts.length; k++) {
            if (state.parts[k].el === targetCard) { position = k; break; }
          }
          if (position < 0) { setStatus(S().none, "warn"); return; }
          if (state.speaking && state.index === position) { togglePlay(); return; }
          stopAll();
          if (state.mode === "read") setMode("listen");
          speakPart(position, null);
        });
      })(card);
    }
  }

  var scanning = false;
  var scanTimer = null;

  function scan() {
    if (scanning) return;
    scanning = true;
    try {
      var results = document.getElementById("results");
      if (!results) return;
      var children = results.children;
      for (var i = 0; i < children.length; i++) decorate(children[i]);
      setPartButtons();
    } finally {
      scanning = false;
    }
  }

  function watch() {
    if (scanTimer !== null) return;
    scanTimer = window.setInterval(function () {
      if (!document.getElementById("results")) return;
      scan();
    }, 700);
    scan();
  }

  /* --------------------------------------------------------- start screen */

  function bigButton(background, foreground) {
    return "flex:1;min-width:150px;background:" + background + ";color:" + foreground +
           ";border:1px solid #cbd5e1;border-radius:12px;padding:14px;" +
           "font-size:18px;cursor:pointer;";
  }

  function buildStartScreen() {
    var existing = document.getElementById("voicestart");
    if (existing) existing.parentNode.removeChild(existing);

    var overlay = document.createElement("div");
    overlay.id = "voicestart";
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,0.72);" +
      "display:flex;align-items:center;justify-content:center;padding:20px;";

    var panel = document.createElement("div");
    panel.style.cssText =
      "background:#ffffff;border-radius:20px;max-width:520px;width:100%;padding:26px;" +
      "box-shadow:0 20px 45px rgba(0,0,0,0.3);";
    panel.innerHTML =
      '<h2 style="margin:0 0 6px;font-size:24px;color:#0f172a;"></h2>' +
      '<p style="margin:0 0 16px;color:#475569;font-size:16px;"></p>' +
      '<label style="display:block;font-size:16px;margin-bottom:6px;color:#0f172a;"></label>' +
      '<select style="font-size:17px;padding:10px;border-radius:10px;' +
      'border:1px solid #cbd5e1;width:100%;">' +
      '<option value="en">English</option>' +
      '<option value="hi">हिन्दी</option>' +
      '<option value="ta">தமிழ்</option>' +
      '</select>' +
      '<div id="voicestartactions" style="display:flex;gap:10px;margin-top:18px;' +
      'flex-wrap:wrap;"></div>';

    var title = panel.querySelector("h2");
    var sub = panel.querySelector("p");
    var label = panel.querySelector("label");
    var select = panel.querySelector("select");
    var actions = panel.querySelector("#voicestartactions");

    function paint() {
      setText(title, S().startTitle);
      setText(sub, S().welcome);
      setText(label, S().startLang);
      select.value = state.lang;
      while (actions.firstChild) actions.removeChild(actions.firstChild);

      var listen = document.createElement("button");
      listen.type = "button";
      listen.textContent = S().listen;
      listen.style.cssText = bigButton("#0f766e", "#ffffff");
      listen.addEventListener("click", function () { finish("listen"); });

      var read = document.createElement("button");
      read.type = "button";
      read.textContent = S().read;
      read.style.cssText = bigButton("#ffffff", "#0f172a");
      read.addEventListener("click", function () { finish("read"); });

      actions.appendChild(listen);
      actions.appendChild(read);
    }

    function finish(mode) {
      state.lang = select.value;
      setMode(mode);
      state.userStarted = true;
      persist();
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      buildBar();
      var name = voiceName();
      if (mode === "listen") {
        setStatus(name
          ? (LANG_NAME[state.lang] + " voice: " + name)
          : S().noVoice, name ? "ok" : "warn");
        if (name) speakText(S().welcome, null);
      } else {
        setStatus(S().saved, "ok");
      }
    }

    select.addEventListener("change", function () {
      state.lang = select.value;
      paint();
    });

    paint();
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
  }

  /* ------------------------------------------------------------------ init */

  function start() {
    document.body.setAttribute("data-voice-mode", state.mode);
    buildBar();
    watch();

    if (speechReady()) {
      window.speechSynthesis.onvoiceschanged = function () { paintBar(); };
      try { window.speechSynthesis.getVoices(); } catch (e) {}
    }
    if (!speechReady()) {
      setStatus("This browser has no speech engine. Please use Chrome or Edge.", "warn");
    } else if (!pickVoice()) {
      setStatus(S().noVoice, "warn");
    }

    if (!state.userStarted) buildStartScreen();

    var selects = document.querySelectorAll("select");
    for (var i = 0; i < selects.length; i++) {
      if (selects[i].id === "voicelang") continue;
      (function (select) {
        select.addEventListener("change", function () {
          var value = String(select.value || "").toLowerCase();
          if (value === "en" || value === "hi" || value === "ta") {
            state.lang = value;
            persist();
            buildBar();
            scan();
            var name = voiceName();
            setStatus(name
              ? (LANG_NAME[state.lang] + " voice: " + name)
              : S().noVoice, name ? "ok" : "warn");
          }
        });
      })(selects[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
