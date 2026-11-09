(function () {
  var configNode = document.getElementById("chat-config");
  if (!configNode) return;
  var config = JSON.parse(configNode.textContent);
  var root = document.querySelector("[data-chat]");
  if (!root) return;

  if (/^#[0-9a-fA-F]{6}$/.test(config.accent || "")) {
    document.documentElement.style.setProperty("--accent", config.accent);
  }

  var titleNode = root.querySelector("[data-title]");
  var subtitleNode = root.querySelector("[data-subtitle]");
  var log = root.querySelector("[data-log]");
  var form = root.querySelector("[data-form]");
  var input = root.querySelector("[data-input]");
  var submit = form.querySelector("button");
  if (titleNode) titleNode.textContent = config.title || "Ask Hassan";
  if (subtitleNode) subtitleNode.textContent = config.subtitle || "Questions about my work";
  input.placeholder = config.placeholder || "Ask about a role, a stack, or a project";

  function endpoint(path) {
    var base = (config.apiBase || "").replace(/\/$/, "");
    return base + path;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function inline(value) {
    return escapeHtml(value).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }

  function isBullet(line) {
    return /^\s*(?:[-*]|[0-9]+\.)\s+/.test(line);
  }

  function bulletText(line) {
    return line.replace(/^\s*(?:[-*]|[0-9]+\.)\s+/, "");
  }

  function renderRich(text) {
    var blocks = String(text || "").split(/\n{2,}/);
    return blocks.map(function (block) {
      var lines = block.split("\n");
      var bullets = lines.filter(isBullet);
      var prose = lines.filter(function (line) { return line.trim() && !isBullet(line); });
      var html = prose.map(function (line) { return "<p>" + inline(line) + "</p>"; }).join("");
      if (bullets.length) {
        var ordered = bullets.every(function (line) { return /^\s*[0-9]+\./.test(line); });
        var tag = ordered ? "ol" : "ul";
        html += "<" + tag + ">" + bullets.map(function (line) {
          return "<li>" + inline(bulletText(line)) + "</li>";
        }).join("") + "</" + tag + ">";
      }
      return html || "<p></p>";
    }).join("");
  }

  function scrollDown() {
    log.scrollTop = log.scrollHeight;
  }

  var suggestRow = document.createElement("div");
  suggestRow.className = "suggest";
  log.appendChild(suggestRow);

  var sending = false;

  function ask(question) {
    var text = question.trim();
    if (!text || sending) return;
    sending = true;
    suggestRow.remove();
    appendUser(text);
    input.value = "";
    input.style.height = "auto";
    send(text);
  }

  function appendUser(text) {
    var msg = document.createElement("article");
    msg.className = "msg user";
    var who = document.createElement("p");
    who.className = "who";
    who.textContent = "You";
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    msg.append(who, bubble);
    log.appendChild(msg);
    scrollDown();
  }

  function startAssistant() {
    var msg = document.createElement("article");
    msg.className = "msg assistant";
    var who = document.createElement("p");
    who.className = "who";
    who.textContent = "Hassan";
    var bubble = document.createElement("div");
    bubble.className = "bubble pending";
    bubble.textContent = "Looking through the portfolio record…";
    msg.append(who, bubble);
    log.appendChild(msg);
    scrollDown();
    return bubble;
  }

  function showCitations(items) {
    if (!items || !items.length) return;
    var row = document.createElement("div");
    row.className = "citations";
    var label = document.createElement("span");
    label.textContent = "From the record";
    row.appendChild(label);
    items.slice(0, 4).forEach(function (item) {
      var link = document.createElement("a");
      link.textContent = item.title;
      if (/^https?:\/\//.test(item.anchor || "")) {
        link.href = item.anchor;
        link.target = "_blank";
        link.rel = "noreferrer";
      }
      row.appendChild(link);
    });
    log.appendChild(row);
  }

  function showFollowups(items) {
    if (!items || !items.length) return;
    var row = document.createElement("div");
    row.className = "follow";
    var label = document.createElement("p");
    label.textContent = "Ask next";
    row.appendChild(label);
    items.slice(0, 3).forEach(function (item) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = item;
      button.addEventListener("click", function () { ask(item); });
      row.appendChild(button);
    });
    log.appendChild(row);
    scrollDown();
  }

  function safeDetail(value) {
    if (typeof value !== "string") return "The assistant could not answer just now.";
    if (value.length > 180 || /postgres|password|secret|api[_ ]?key|postgresql:\/\//i.test(value)) {
      return "The assistant could not answer just now.";
    }
    return value;
  }

  async function send(question) {
    submit.disabled = true;
    var bubble = startAssistant();
    var answer = "";
    var meta = {};
    try {
      var response = await fetch(endpoint("/v1/chat/stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
        body: JSON.stringify({ question: question })
      });
      if (!response.ok || !response.body) {
        var failed = {};
        try { failed = await response.json(); } catch (err) { failed = {}; }
        throw new Error(safeDetail(failed.detail));
      }
      await readStream(response.body, function (event, data) {
        if (event === "meta") meta = data;
        if (event === "token" && data.t) {
          answer += data.t;
          bubble.classList.remove("pending");
          bubble.innerHTML = renderRich(answer);
          scrollDown();
        }
        if (event === "error") throw new Error(safeDetail(data.detail));
      });
      if (!answer.trim()) {
        bubble.textContent = "I could not form an answer from the record.";
      }
      showCitations(meta.citations);
      showFollowups(meta.suggested_followups);
    } catch (error) {
      bubble.classList.remove("pending");
      bubble.textContent = error && error.message ? error.message : "The assistant could not answer just now.";
    } finally {
      sending = false;
      submit.disabled = false;
      input.focus();
    }
  }

  async function readStream(stream, onEvent) {
    var reader = stream.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    while (true) {
      var chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      var splitAt;
      while ((splitAt = buffer.indexOf("\n\n")) >= 0) {
        var raw = buffer.slice(0, splitAt);
        buffer = buffer.slice(splitAt + 2);
        var eventName = "message";
        var dataLine = "";
        raw.split("\n").forEach(function (line) {
          if (line.indexOf("event:") === 0) eventName = line.slice(6).trim();
          if (line.indexOf("data:") === 0) dataLine += line.slice(5).trim();
        });
        if (!dataLine) continue;
        onEvent(eventName, JSON.parse(dataLine));
      }
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    ask(input.value);
  });

  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  });

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  fetch(endpoint("/v1/suggestions"))
    .then(function (response) { return response.ok ? response.json() : { suggestions: [] }; })
    .then(function (body) {
      (body.suggestions || []).forEach(function (item) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "chip";
        button.textContent = item;
        button.addEventListener("click", function () { ask(item); });
        suggestRow.appendChild(button);
      });
    })
    .catch(function () {});
})();
