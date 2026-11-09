(function () {
  var script = document.currentScript;
  if (!script) {
    var found = document.getElementsByTagName("script");
    script = found[found.length - 1];
  }

  var FALLBACK = "https://chat-with-me.fastapicloud.dev";

  function originOf(value) {
    try {
      var url = new URL(value, window.location.href);
      if (url.protocol !== "http:" && url.protocol !== "https:") return "";
      if (url.username || url.password) return "";
      return url.origin;
    } catch (err) {
      return "";
    }
  }

  function clip(value, limit) {
    return String(value || "").replace(/[\u0000-\u001f<>]/g, "").trim().slice(0, limit);
  }

  var configured = typeof PORTFOLIO_API_BASE === "string" ? PORTFOLIO_API_BASE : "";
  // data-api overrides the default FastAPI Cloud origin.
  var api = originOf(script.dataset.api || configured || FALLBACK) || FALLBACK;
  var scriptOrigin = originOf(script.src) || api;
  var accent = /^#[0-9a-fA-F]{6}$/.test(script.dataset.accent || "")
    ? script.dataset.accent
    : "#0f5c45";
  var title = clip(script.dataset.title || "Ask Hassan", 48) || "Ask Hassan";
  var subtitle = clip(script.dataset.subtitle || "", 80);
  var placeholder = clip(script.dataset.placeholder || "", 80);
  var position = script.dataset.position === "left" ? "left" : "right";

  var params = new URLSearchParams();
  params.set("title", title);
  params.set("accent", accent);
  params.set("api", api);
  if (subtitle) params.set("subtitle", subtitle);
  if (placeholder) params.set("placeholder", placeholder);

  var root = document.createElement("div");
  root.id = "hassan-portfolio-chat";
  root.setAttribute("data-position", position);

  var style = document.createElement("style");
  style.textContent = [
    "#hassan-portfolio-chat{position:fixed;z-index:2147483000;",
    position === "left" ? "left:20px;" : "right:20px;",
    "bottom:20px;font-family:Georgia,'Iowan Old Style',serif;color:#1c1916;}",
    "#hassan-portfolio-chat *{box-sizing:border-box;}",
    "#hassan-portfolio-chat .launcher{display:flex;align-items:center;gap:10px;",
    "border:0;border-radius:999px;padding:10px 14px 10px 10px;cursor:pointer;",
    "background:" + accent + ";color:#f6f1e7;box-shadow:0 10px 30px rgba(28,25,22,.18);}",
    "#hassan-portfolio-chat .mark{display:grid;place-items:center;width:28px;height:28px;",
    "border-radius:8px;background:rgba(255,255,255,.14);font-size:12px;}",
    "#hassan-portfolio-chat .label{font-family:'Segoe UI',sans-serif;font-size:14px;font-weight:600;}",
    "#hassan-portfolio-chat .panel{position:absolute;bottom:62px;",
    position === "left" ? "left:0;" : "right:0;",
    "width:min(420px,calc(100vw - 32px));height:min(840px,calc(100vh - 88px));",
    "border-radius:18px;overflow:hidden;background:#f4efe6;",
    "box-shadow:0 24px 60px rgba(48,36,18,.22);border:1px solid #e4d8c6;}",
    "#hassan-portfolio-chat .panel[hidden]{display:none;}",
    "#hassan-portfolio-chat iframe{width:100%;height:100%;border:0;background:#f4efe6;}",
    "#hassan-portfolio-chat .launcher:focus-visible{outline:2px solid #1c1916;outline-offset:3px;}"
  ].join("");

  var panel = document.createElement("div");
  panel.className = "panel";
  panel.hidden = true;
  var frame = document.createElement("iframe");
  frame.title = title;
  frame.src = scriptOrigin + "/embed?" + params.toString();
  panel.appendChild(frame);

  var button = document.createElement("button");
  button.type = "button";
  button.className = "launcher";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-controls", "hassan-portfolio-chat-panel");
  panel.id = "hassan-portfolio-chat-panel";
  var mark = document.createElement("span");
  mark.className = "mark";
  mark.textContent = "HA";
  var label = document.createElement("span");
  label.className = "label";
  label.textContent = title;
  button.append(mark, label);

  function setOpen(open) {
    panel.hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    label.textContent = open ? "Close" : title;
  }

  button.addEventListener("click", function () {
    setOpen(panel.hidden);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") setOpen(false);
  });

  root.append(style, panel, button);
  document.body.appendChild(root);
  if (script.dataset.open === "true") setOpen(true);
})();
