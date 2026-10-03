/* rights.js - the rights and complaint navigator.
 *
 * A plain directory of official complaint channels, in order, with the
 * published time limits. Nothing here is generated: no model, no guessing.
 *
 * It never asks for personal data, never stores an answer anywhere, and
 * never sends anything to a server. The only request it makes is to read
 * this project's own static list of official links.
 */

(function () {
  "use strict";

  var T = {
    en: {
      title: "If something goes wrong",
      subtitle: "Where to complain, and in what order. Official channels only.",
      pick: "What happened?",
      open: "Show me where to go",
      openLink: "Open the official page",
      keep: "Keep these ready before you complain",
      privacy: "",
      disclaimer: "",
      read: "Read this aloud",
      stop: "Stop reading",
      checked: "Links last checked on"
    },
    hi: {
      title: "कुछ गड़बड़ हो जाए तो",
      subtitle: "कहाँ और किस क्रम में शिकायत करें। केवल आधिकारिक माध्यम।",
      pick: "क्या हुआ?",
      open: "दिखाएँ कहाँ जाना है",
      openLink: "आधिकारिक पेज खोलें",
      keep: "शिकायत से पहले यह तैयार रखें",
      privacy: "",
      disclaimer: "",
      read: "यह सुनाएँ",
      stop: "सुनना बंद करें",
      checked: "लिंक की अंतिम जाँच"
    },
    ta: {
      title: "ஏதாவது பிழை நிகழ்ந்தால்",
      subtitle: "எங்கே, எந்த வரிசையில் புகார் அளியுங்கள். அதிகாரப்பூர்வ முறைகள் மட்டும்.",
      pick: "என்ன நடந்தது?",
      open: "எங்கே செல்வது என்பதைக் காட்டு",
      openLink: "அதிகாரப்பூர்வ பக்கத்தைத் திற",
      keep: "புகார் அளிக்க முன் இவற்றைத் தயார் செய்யுங்கள்",
      privacy: "",
      disclaimer: "",
      read: "இதைப் படிக்கவும்",
      stop: "படிப்பதை நிறுத்து",
      checked: "இணைப்புகள் சரிபார்க்கப்பட்ட நாள்"
    }
  };

  function L() { return T[state.lang] || T.en; }

  var state = { lang: "en", data: null, situation: null, speaking: false };

  function el(tag, text, style) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (style) node.style.cssText = style;
    return node;
  }

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function button(text) {
    var node = el("button", text,
      "background:#0f766e;color:#ffffff;border:0;border-radius:12px;" +
      "padding:11px 18px;font-size:16px;cursor:pointer;");
    node.type = "button";
    return node;
  }

  function card() {
    return el("section", null,
      "background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;" +
      "padding:18px 20px;margin:16px 0;");
  }

  function build(root) {
    var wrap = card();
    var head = el("h2", L().title, "font-size:22px;margin:0 0 4px;color:#0f172a;");
    var sub = el("p", L().subtitle, "margin:0 0 10px;color:#475569;");
    wrap.appendChild(head);
    wrap.appendChild(sub);

    var urgent = el("div", "", null);
    wrap.appendChild(urgent);

    var pick = el("p", L().pick, "font-size:17px;color:#0f172a;margin:14px 0 8px;");
    wrap.appendChild(pick);

    var list = el("div", null, "");
    wrap.appendChild(list);

    var result = el("div", null, "");
    wrap.appendChild(result);

    var keepBox = el("div", null, "");
    wrap.appendChild(keepBox);

    var foot = el("div", null, "");
    wrap.appendChild(foot);

    var readButton = button(L().read);
    readButton.addEventListener("click", function () { speak(root); });

    root.appendChild(wrap);

    function speak(scope) {
      if (state.speaking) {
        if (window.speechSynthesis) { try { window.speechSynthesis.cancel(); } catch (e) {} }
        state.speaking = false;
        setText(readButton, L().read);
        return;
      }
      if (!window.speechSynthesis) return;
      var pick = document.getElementById("voicelang");
      var tag = (pick && pick.value === "hi") ? "hi-IN" : (pick && pick.value === "ta") ? "ta-IN" : "en-IN";
      var voices = window.speechSynthesis.getVoices() || [];
      var match = null;
      for (var i = 0; i < voices.length; i++) {
        if ((voices[i].lang || "").replace("_", "-").toLowerCase().indexOf(tag.toLowerCase()) === 0) {
          match = voices[i]; break;
        }
      }
      if (!match) {
        var fb = null;
        for (var j = 0; j < voices.length; j++) {
          if ((voices[j].lang || "").toLowerCase().indexOf("en") === 0) { fb = voices[j]; break; }
        }
        match = fb;
      }
      if (!match) return;
      var utterance = new SpeechSynthesisUtterance(scope.innerText);
      utterance.voice = match;
      utterance.lang = match.lang;
      utterance.rate = 0.95;
      utterance.onend = function () {
        state.speaking = false;
        setText(readButton, L().read);
      };
      state.speaking = true;
      setText(readButton, L().stop);
      window.speechSynthesis.speak(utterance);
    }

    function paint() {
      setText(head, L().title);
      setText(sub, L().subtitle);
      setText(pick, L().pick);
      setText(readButton, state.speaking ? L().stop : L().read);

      urgent.innerHTML = "";
      urgent.appendChild(el("div", state.data.urgent,
        "background:#fef2f2;border:1px solid #fecaca;color:#991b1b;border-radius:12px;" +
        "padding:12px 14px;font-size:16px;"));

      list.innerHTML = "";
      state.data.situations.forEach(function (item) {
        var b = button(item.label);
        b.style.cssText = "display:block;width:100%;text-align:left;margin:0 0 8px;" +
          "background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;font-size:16px;";
        b.addEventListener("click", function () {
          state.situation = item.id;
          fetch("/api/rights/" + item.id + "?language=" + encodeURIComponent(state.lang))
            .then(function (r) { return r.json(); })
            .then(function (data) { showLadder(result, data); })
            .catch(function () {
              result.innerHTML = "";
              result.appendChild(el("p", "Could not load. Is the server running?",
                "color:#9a3412;"));
            });
        });
        list.appendChild(b);
      });

      keepBox.innerHTML = "";
      keepBox.appendChild(el("h3", L().keep, "font-size:18px;margin:18px 0 6px;color:#0f172a;"));
      var ul = el("ul", null, "margin:0 0 6px;padding-left:20px;color:#0f172a;");
      (state.data.keep_ready || []).forEach(function (item) {
        ul.appendChild(el("li", item, "font-size:16px;margin:4px 0;"));
      });
      keepBox.appendChild(ul);

      foot.innerHTML = "";
      foot.appendChild(el("p", state.data.privacy,
        "font-size:14px;color:#166534;background:#f0fdf4;border:1px solid #bbf7d0;" +
        "border-radius:10px;padding:10px 12px;margin:10px 0;"));
      foot.appendChild(el("p", state.data.disclaimer,
        "font-size:14px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:10px;"));
      foot.appendChild(el("p", L().checked + " " + state.data.last_checked,
        "font-size:13px;color:#94a3b8;"));
      foot.appendChild(readButton);
    }

    function showLadder(host, data) {
      host.innerHTML = "";
      if (!data.steps || !data.steps.length) {
        host.appendChild(el("p", "We could not identify the right channel yet. " +
          "Use the consumer helpline below and they will point you to the right body.",
          "font-size:16px;color:#334155;"));
        return;
      }
      data.steps.forEach(function (step) {
        var box = el("div", null,
          "border:1px solid #e2e8f0;border-left:4px solid #0f766e;border-radius:12px;" +
          "padding:12px 14px;margin:10px 0;");
        box.appendChild(el("strong", "Step " + step.step + ": " + step.who,
          "display:block;font-size:17px;color:#0f172a;margin-bottom:4px;"));
        box.appendChild(el("p", step.detail, "margin:0 0 6px;font-size:16px;color:#0f172a;"));
        box.appendChild(el("p", step.days, "margin:0;font-size:15px;color:#b45309;"));
        if (step.url) {
          var a = el("a", L().openLink, null);
          a.href = step.url;
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.style.cssText = "display:inline-block;margin-top:8px;font-size:15px;" +
            "color:#0f766e;text-decoration:underline;";
          box.appendChild(a);
          box.appendChild(el("p", step.url.replace(/^https?:\/\//, ""),
            "margin:4px 0 0;font-size:13px;color:#94a3b8;"));
        }
        host.appendChild(box);
      });
    }

    fetch("/api/rights?language=" + encodeURIComponent(state.lang))
      .then(function (r) { return r.json(); })
      .then(function (data) { state.data = data; paint(); })
      .catch(function () {
        wrap.appendChild(el("p", "Could not load the directory. Is the server running?",
          "color:#9a3412;"));
      });
  }

  function install() {
    var results = document.getElementById("results");
    if (!results) { window.setTimeout(install, 400); return; }
    var root = document.getElementById("rightspanel");
    if (root) return;
    root = el("div", null, "");
    root.id = "rightspanel";
    results.parentNode.insertBefore(root, results.nextSibling);
    build(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})();
