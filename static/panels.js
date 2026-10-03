/* panels.js - the two extra checks, added to the page without touching it.
 *
 *   Clauses to review  - the document's own clauses that a first-time reader
 *                        should read twice, each with the exact line, a plain
 *                        explanation and a "check the full terms" prompt.
 *   Will this suit me? - 3 short questions. Each answer is placed next to what
 *                        the document itself says. It never decides for you.
 */

(function () {
  "use strict";

  var T = {
    en: {
      clauses: "Clauses to review",
      clausesBtn: "Show the clauses to review",
      fit: "Will this suit me?",
      fitBtn: "Compare with the document",
      running: "Reading the document again. This takes up to a minute.",
      show: "Show the exact line",
      hide: "Hide the exact line",
      tapToAnswer: "Tap one answer for each question. There is no wrong answer here.",
      noAnswers: "Choose an answer for at least one question first.",
      quota: "The AI's free quota was already used by the explanation above, so "
           + "only the exact lines are shown. Wait a minute and press again for "
           + "the plain-language explanation.",
      youSaid: "You said",
      docSays: "The document says",
      inGeneral: "In general - not stated in your document, so it may not apply",
      none: "No clause from the review list was found in this text."
    },
    hi: {
      clauses: "दो बार पढ़ने योग्य शर्तें",
      clausesBtn: "शर्तें दिखाएँ",
      fit: "क्या यह आपके लिए उपयुक्त है?",
      fitBtn: "दस्तावेज़ से मिलाएँ",
      running: "दस्तावेज़ दोबारा पढ़ा जा रहा है। इसमें एक मिनट लग सकता है।",
      show: "सही लाइन दिखाएँ",
      hide: "लाइन छिपाएँ",
      tapToAnswer: "हर सवाल का एक उत्तर चुनें। यहाँ कोई गलत उत्तर नहीं है।",
      noAnswers: "पहले कम से कम एक सवाल का उत्तर चुनें।",
      quota: "AI की मुफ़्त सीमा ऊपर के explanation में ही खत्म हो गई, इसलिए केवल सही "
           + "लाइनें दिखाई जा रही हैं। एक मिनट बाद दोबारा दबाएँ।",
      youSaid: "आपने कहा",
      docSays: "दस्तावेज़ कहता है",
      inGeneral: "सामान्य रूप से - आपके दस्तावेज़ में यह नहीं लिखा है, इसलिए शायद लागू न हो",
      none: "इस पाठ में समीक्षा सूची की कोई शर्त नहीं मिली।"
    },
    ta: {
      clauses: "இரண்டு தடவை படிக்க வேண்டிய கூற்றுகள்",
      clausesBtn: "கூற்றுகளைக் காட்டு",
      fit: "இது உங்களுக்குப் பொருந்துமா?",
      fitBtn: "ஆவணத்துடன் ஒப்பிடு",
      running: "ஆவணம் மீண்டும் படிக்கப்படுகிறது. இதற்கு ஒரு நிமிடம் ஆகலாம்.",
      show: "சரியான வரியைக் காட்டு",
      hide: "வரியை மறை",
      tapToAnswer: "ஒவ்வொரு கேள்விக்கும் ஒரு பதிலைத் தேர்ந்தெடுக்கவும். இங்கு தவறான பதில் இல்லை.",
      noAnswers: "குறைந்தது ஒரு கேள்விக்கு பதில் தேர்ந்தெடுக்கவும்.",
      quota: "மேலே உள்ள விளக்கத்திற்கே AI இலவச எLimits தீர்ந்தது, எனவே சரியான வரிகள் "
           + "மட்டுமே காட்டப்படுகின்றன. ஒரு நிமிடம் கழித்து மீண்டும் அழுத்துங்கள்.",
      youSaid: "நீங்கள் கூறியது",
      docSays: "ஆவணம் கூறுவது",
      inGeneral: "பொதுவாக - உங்கள் ஆவணத்தில் இது இல்லை, எனவே பொருந்தாமல் இருக்கலாம்",
      none: "இந்த உரையில் பட்டியல் பிரிவு கூற்றுகள் எதுவும் கிடைக்கவில்லை."
    }
  };

  function L() { return T[state.lang] || T.en; }

  var state = { lang: "en" };
  var lastText = "";

  var QUESTIONS = [
    {
      id: "money_soon",
      en: "Might you need this money within the next 1 to 2 years?",
      hi: "क्या आपको अगले 1 से 2 वर्षों में यह पैसा चाहिए पड़ सकता है?",
      ta: "அடுத்த 1 முதல் 2 ஆண்டுகளில் இந்தப் பணம் தேவைப்படலாமா?"
    },
    {
      id: "miss_payment",
      en: "If a payment is missed for a couple of months, could you manage?",
      hi: "क्या आप एक-दो महीने भुगतान छूटने की स्थिति संभाल सकते हैं?",
      ta: "ஒரு சில மாதங்கள் கட்டணம் தவறினால் அதைச் சமாள முடியுமா?"
    },
    {
      id: "emergency_money",
      en: "Is this the money you would need in an emergency?",
      hi: "क्या यह वह पैसा है जो आपको आपातकाल में चाहिए?",
      ta: "இது அவசரத்தில் தேவையான பணமா?"
    },
    {
      id: "other_commitments",
      en: "Do you already repay another loan, EMI or card bill?",
      hi: "क्या आप पहले से कोई और ऋण, EMI या कार्ड बिल चुकाते हैं?",
      ta: "ஏற்கனவே வேறு கடன், EMI அல்லது அட்டைக் கட்டணம் செலுத்துகிறீர்களா?"
    }
  ];

  function el(tag, text, style) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (style) node.style.cssText = style;
    return node;
  }

  function currentLanguage() {
    var select = document.querySelector("select");
    var value = select ? String(select.value || "").toLowerCase() : "";
    if (value === "en" || value === "hi" || value === "ta") state.lang = value;
    return state.lang;
  }

  function aiOn() {
    var box = document.querySelector('input[type="checkbox"]');
    return !box || box.checked;
  }

  function yesNo(lang) {
    if (lang === "hi") return { yes: "हाँ", no: "नहीं" };
    if (lang === "ta") return { yes: "ஆம்", no: "இல்லை" };
    return { yes: "Yes", no: "No" };
  }

  function button(text, style) {
    var node = el("button", text, style ||
      "background:#0f766e;color:#ffffff;border:0;border-radius:12px;" +
      "padding:12px 20px;font-size:17px;cursor:pointer;");
    node.type = "button";
    return node;
  }

  function panel(title) {
    var wrap = el("section", null,
      "background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;" +
      "padding:18px 20px;margin:16px 0;");
    wrap.appendChild(el("h2", title, "font-size:22px;margin:0 0 6px;color:#0f172a;"));
    var status = el("div", "", "color:#475569;font-size:15px;margin:6px 0;");
    wrap.appendChild(status);
    var body = el("div", null, "");
    wrap.appendChild(body);
    return { wrap: wrap, status: status, body: body };
  }

  function ensureRoot() {
    var results = document.getElementById("results");
    if (!results) return null;
    var root = document.getElementById("eyepanels");
    if (!root) {
      root = el("div", null, "");
      root.id = "eyepanels";
      results.parentNode.insertBefore(root, results.nextSibling);
    }
    return root;
  }

  function post(path, payload) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    });
  }

  /* ------------------------------------------------------- clauses panel */

  function buildClauses(root) {
    var p = panel(L().clauses);
    var run = button(L().clausesBtn);
    p.wrap.insertBefore(run, p.status.nextSibling);
    run.addEventListener("click", function () {
      if (!lastText) { p.status.textContent = L().running; return; }
      run.disabled = true;
      run.textContent = L().running;
      p.status.textContent = L().running;
      post("/api/flags", {
        text: lastText, language: currentLanguage(), use_model: aiOn()
      })
        .then(function (data) { renderFlags(p, data); })
        .catch(function () {
          p.status.textContent = "Could not load. Is the server still running?";
        })
        .then(function () {
          run.disabled = false;
          run.textContent = L().clausesBtn;
        });
    });
    root.appendChild(p.wrap);
  }

  function renderFlags(p, data) {
    p.body.innerHTML = "";
    var items = data.items || [];
    if (!items.length) {
      p.status.textContent = data.notice || "";
      p.body.appendChild(el("p", L().none, "color:#475569;"));
      return;
    }
    var bare = items.filter(function (i) { return !i.explanation; }).length;
    p.status.textContent = (data.notice || "") ||
      (bare === items.length ? L().quota : (data.intro || ""));

    items.forEach(function (item, index) {
      var box = el("div", null,
        "border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;margin:10px 0;");
      box.appendChild(el("strong", (index + 1) + ". " + item.title,
        "display:block;font-size:17px;color:#0f172a;margin-bottom:6px;"));
      box.appendChild(el("p",
        item.explanation || (data.read_it_yourself || ""),
        "margin:0 0 8px;font-size:16px;color:" + (item.explanation ? "#0f172a" : "#475569") + ";"));

      var quote = el("blockquote", item.quote,
        "display:none;margin:8px 0 0;padding:10px 12px;border-left:4px solid #14b8a6;" +
        "background:#f8fafc;color:#334155;font-size:15px;");
      var toggle = el("button", L().show,
        "background:#ffffff;color:#0f172a;border:1px solid #94a3b8;border-radius:10px;" +
        "padding:8px 14px;font-size:15px;cursor:pointer;");
      toggle.type = "button";
      toggle.addEventListener("click", function () {
        var shown = quote.style.display === "block";
        quote.style.display = shown ? "none" : "block";
        toggle.textContent = shown ? L().show : L().hide;
      });
      box.appendChild(toggle);
      box.appendChild(quote);
      box.appendChild(el("p", item.verify_prompt,
        "margin:8px 0 0;font-size:14px;color:#64748b;"));
      p.body.appendChild(box);
    });
  }

  /* ---------------------------------------------------------- fit panel */

  function buildFit(root) {
    var p = panel(L().fit);
    var lang = currentLanguage();
    var labels = yesNo(lang);
    var answers = {};

    p.status.textContent = L().tapToAnswer;

    QUESTIONS.forEach(function (question) {
      var box = el("div", null,
        "border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;margin:10px 0;");
      box.appendChild(el("p", question[lang] || question.en,
        "margin:0 0 10px;font-size:17px;color:#0f172a;"));

      var row = el("div", null, "display:flex;gap:10px;flex-wrap:wrap;");
      ["yes", "no"].forEach(function (key) {
        var option = button(labels[key],
          "background:#ffffff;color:#0f172a;border:2px solid #cbd5e1;border-radius:12px;" +
          "padding:10px 26px;font-size:17px;cursor:pointer;");
        option.addEventListener("click", function () {
          answers[question.id] = key;
          var all = row.querySelectorAll("button");
          for (var i = 0; i < all.length; i++) {
            all[i].style.borderColor = "#cbd5e1";
            all[i].style.background = "#ffffff";
          }
          option.style.borderColor = "#0f766e";
          option.style.background = "#ccfbf1";
        });
        row.appendChild(option);
      });
      box.appendChild(row);
      p.wrap.insertBefore(box, p.body);
    });

    var go = button(L().fitBtn);
    go.addEventListener("click", function () {
      var chosen = {};
      QUESTIONS.forEach(function (q) {
        if (answers[q.id]) chosen[q.id] = answers[q.id];
      });
      if (!Object.keys(chosen).length) {
        p.status.textContent = L().noAnswers;
        return;
      }
      if (!lastText) { p.status.textContent = L().running; return; }
      go.disabled = true;
      p.status.textContent = L().running;
      post("/api/fit", {
        text: lastText, language: currentLanguage(),
        answers: chosen, use_model: aiOn()
      })
        .then(function (data) { renderFit(p, data); })
        .catch(function () {
          p.status.textContent = "Could not load. Is the server still running?";
        })
        .then(function () { go.disabled = false; });
    });
    p.wrap.insertBefore(go, p.body);
    root.appendChild(p.wrap);
  }

  function renderFit(p, data) {
    p.body.innerHTML = "";
    p.status.textContent = data.disclaimer ? "" : (data.intro || "");

    (data.comparisons || []).forEach(function (item) {
      var box = el("div", null,
        "border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;margin:10px 0;");
      box.appendChild(el("p", item.question,
        "margin:0 0 8px;font-size:17px;color:#0f172a;font-weight:600;"));
      box.appendChild(el("p", L().youSaid + ": " + item.you_said,
        "margin:0 0 6px;font-size:16px;color:#334155;"));

      if (item.status === "matched") {
        box.appendChild(el("p", L().docSays + ": " + item.document_says,
          "margin:0 0 6px;font-size:16px;color:#0f172a;"));
        box.appendChild(el("blockquote", item.quote,
          "margin:0;padding:10px 12px;border-left:4px solid #14b8a6;background:#f8fafc;" +
          "color:#334155;font-size:15px;"));
      } else if (item.status === "general") {
        box.appendChild(el("p", L().inGeneral + ": " + item.general_note,
          "margin:0;font-size:16px;color:#0f172a;"));
      } else {
        box.appendChild(el("p", item.not_found_note, "margin:0;font-size:16px;color:#475569;"));
      }
      p.body.appendChild(box);
    });

    if (data.disclaimer) {
      p.body.appendChild(el("p", data.disclaimer,
        "margin:14px 0 0;font-size:14px;border-top:1px solid #e2e8f0;" +
        "padding-top:10px;color:#64748b;"));
    }
  }

  /* ------------------------------------------------------------- wiring */

  function captureDocument() {
    var area = document.querySelector("textarea");
    if (area && area.value && area.value.trim().length > 40) lastText = area.value;
  }

  function install() {
    var results = document.getElementById("results");
    if (!results) { window.setTimeout(install, 400); return; }
    var root = ensureRoot();
    if (!root) return;

    if (!document.getElementById("eyebuilt")) {
      var holder = el("div", null, "");
      holder.id = "eyebuilt";
      root.appendChild(holder);
      buildClauses(holder);
      buildFit(holder);
    }

    captureDocument();
    try {
      var observer = new MutationObserver(function () { captureDocument(); });
      observer.observe(results, { childList: true });
    } catch (e) {}

    var area = document.querySelector("textarea");
    if (area) area.addEventListener("input", function () { lastText = area.value; });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})();
