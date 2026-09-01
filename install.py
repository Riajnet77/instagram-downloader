import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# === MANIFEST ===
open("manifest.json", "w", encoding="utf-8").write('''{
  "manifest_version": 3,
  "name": "InstaSave Pro",
  "version": "2.0.0",
  "description": "Baixe reels e imagens do Instagram.",
  "permissions": ["downloads", "storage", "tabs", "webRequest"],
  "host_permissions": [
    "https://www.instagram.com/*",
    "https://*.instagram.com/*",
    "https://*.cdninstagram.com/*",
    "https://*.fbcdn.net/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["https://www.instagram.com/*"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_title": "InstaSave Pro",
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}''')
print("OK: manifest.json")

# === BACKGROUND ===
open("background.js", "w", encoding="utf-8").write('''"use strict";
var CAPTURED_KEY = "is_captured";
var HISTORY_KEY = "is_history";
var UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";

function storageGet(key) {
  return new Promise(function(resolve) {
    var store = chrome.storage.session || chrome.storage.local;
    store.get([key], function(data) { resolve(data[key] || null); });
  });
}

function storageSet(key, val) {
  var store = chrome.storage.session || chrome.storage.local;
  var obj = {};
  obj[key] = val;
  store.set(obj).catch(function() {});
}

var captured = new Set();

storageGet(CAPTURED_KEY).then(function(prev) {
  if (prev) prev.forEach(function(u) { captured.add(u); });
}).catch(function() {});

var persistTimer = null;
function persist() {
  if (persistTimer) return;
  persistTimer = setTimeout(function() {
    persistTimer = null;
    storageSet(CAPTURED_KEY, Array.from(captured).slice(-500));
  }, 2000);
}

function addCaptured(url) {
  var clean = url.split("#")[0];
  if (captured.has(clean)) return;
  captured.add(clean);
  persist();
}

chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    var u = details.url || "";
    if (/\\.mp4(\\?|$)/i.test(u) || /\\.m4v(\\?|$)/i.test(u)) addCaptured(u);
  },
  { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] }
);

chrome.webRequest.onHeadersReceived.addListener(
  function(details) {
    var headers = details.responseHeaders || [];
    var ct = null;
    for (var i = 0; i < headers.length; i++) {
      if ((headers[i].name || "").toLowerCase() === "content-type") {
        ct = headers[i];
        break;
      }
    }
    if (ct && /^video\\//i.test(ct.value || "")) addCaptured(details.url);
  },
  { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] },
  ["responseHeaders"]
);

async function fetchMedia(url) {
  var resp = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "*/*",
      Referer: "https://www.instagram.com/",
      "Sec-Fetch-Dest": "empty",
      "Sec-Fetch-Mode": "cors",
      "Sec-Fetch-Site": "cross-site",
      "User-Agent": UA
    }
  });
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  return resp.blob();
}

async function doDownload(url, filename, type) {
  var ext = (type === "image") ? "jpg" : "mp4";
  var fname = filename || ("instagram/media_" + Date.now() + "." + ext);
  try {
    var blob = await fetchMedia(url);
    var objUrl = URL.createObjectURL(blob);
    var id = await chrome.downloads.download({
      url: objUrl, filename: fname, saveAs: false, conflictAction: "uniquify"
    });
    setTimeout(function() { try { URL.revokeObjectURL(objUrl); } catch(e) {} }, 120000);
    var h = (await storageGet(HISTORY_KEY)) || [];
    h.unshift({ url: url, filename: fname, type: type || "video", timestamp: Date.now() });
    storageSet(HISTORY_KEY, h.slice(0, 200));
    return { ok: true, id: id };
  } catch(err) {
    try {
      var id2 = await chrome.downloads.download({
        url: url, filename: fname, saveAs: false, conflictAction: "uniquify"
      });
      var h2 = (await storageGet(HISTORY_KEY)) || [];
      h2.unshift({ url: url, filename: fname, type: type || "video", timestamp: Date.now() });
      storageSet(HISTORY_KEY, h2.slice(0, 200));
      return { ok: true, id: id2 };
    } catch(e2) {
      return { ok: false, error: e2.message || String(e2) };
    }
  }
}

chrome.runtime.onMessage.addListener(function(msg, sender, sendResponse) {
  if (!msg || !msg.type) return false;
  if (msg.type === "DOWNLOAD_MEDIA") {
    doDownload(msg.url, msg.filename, msg.mediaType).then(sendResponse);
    return true;
  }
  if (msg.type === "GET_MEDIA_URLS") {
    sendResponse({ urls: Array.from(captured) });
    return false;
  }
  if (msg.type === "GET_HISTORY") {
    storageGet(HISTORY_KEY).then(function(h) { sendResponse({ history: h || [] }); });
    return true;
  }
  if (msg.type === "CLEAR_HISTORY") {
    storageSet(HISTORY_KEY, []);
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === "GET_STATUS") {
    sendResponse({ ok: true, app: "instasave", version: "2.0.0", captured: captured.size });
    return false;
  }
  return false;
});
''')
print("OK: background.js")

# === CONTENT ===
open("content.js", "w", encoding="utf-8").write('''"use strict";
if (window.__IS2__) return;
window.__IS2__ = true;

var S = {
  shadow: null, curVid: null, curImg: null,
  curUrl: "", curType: "video", lastMedia: null,
  queue: [], queueBusy: false, toastT: null
};

function q(sel) { return S.shadow.querySelector(sel); }
function qa(sel) { return S.shadow.querySelectorAll(sel); }

function debounce(fn, ms) { var t; return function() { var a = arguments; clearTimeout(t); t = setTimeout(function() { fn.apply(null, a); }, ms); }; }
function throttle(fn, ms) { var l = 0; return function() { var a = arguments; var n = Date.now(); if (n - l >= ms) { l = n; fn.apply(null, a); } }; }

function fmtTime(s) {
  if (!isFinite(s) || s < 0) s = 0;
  var sec = Math.floor(s), h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), ss = String(sec % 60).padStart(2, "0");
  return h > 0 ? h + ":" + String(m).padStart(2, "0") + ":" + ss : m + ":" + ss;
}

function relTime(ts) {
  var d = Date.now() - ts, m = Math.floor(d / 60000), h = Math.floor(d / 3600000), dy = Math.floor(d / 86400000);
  if (m < 1) return "agora"; if (m < 60) return m + "min"; if (h < 24) return h + "h"; return dy + "d";
}

function makeFilename(url, type) {
  var p = function(n) { return String(n).padStart(2, "0"); };
  var d = new Date();
  var stamp = d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + "_" + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  var prefix = (type === "image") ? "img" : "reel";
  return "instagram/" + prefix + "_" + stamp + "." + ((type === "image") ? "jpg" : "mp4");
}

function findCurrentVideo() {
  var vids = document.querySelectorAll("video");
  var vh = window.innerHeight, best = null, bestScore = -1;
  for (var i = 0; i < vids.length; i++) {
    var v = vids[i];
    if (v.closest("#is2-root")) continue;
    var r = v.getBoundingClientRect();
    if (r.width < 40 || r.height < 40) continue;
    var vis = Math.min(r.bottom, vh) - Math.max(r.top, 0);
    if (vis <= 0) continue;
    var cd = Math.abs(r.top + r.height / 2 - vh / 2);
    var score = vis - cd;
    if (!v.paused && !v.ended) score += vh * 2;
    if (score > bestScore) { bestScore = score; best = v; }
  }
  return best;
}

function findCurrentImage() {
  var imgs = document.querySelectorAll("img");
  var vh = window.innerHeight, best = null, bestArea = 0;
  for (var i = 0; i < imgs.length; i++) {
    var img = imgs[i];
    if (img.closest("#is2-root")) continue;
    var src = img.src || "";
    if (src.indexOf("cdninstagram.com") === -1 && src.indexOf("fbcdn.net") === -1) continue;
    var r = img.getBoundingClientRect();
    if (r.width < 150 || r.height < 150) continue;
    var vis = Math.min(r.bottom, vh) - Math.max(r.top, 0);
    if (vis <= 0) continue;
    var area = r.width * r.height;
    if (area > bestArea) { bestArea = area; best = img; }
  }
  return best;
}

function upgradeImgUrl(url) {
  if (!url) return "";
  return url.replace(/\\/s\\d+x\\d+\\//, "/").replace(/&tp=\\d+/, "").replace(/\\/e\\d+\\//, "/e35/");
}

function getMetaVideoUrl() {
  var el = document.querySelector(\'meta[property="og:video:secure_url"]\') || document.querySelector(\'meta[property="og:image"]\');
  return el ? (el.getAttribute("content") || "") : "";
}

function getMetaImageUrl() {
  var el = document.querySelector(\'meta[property="og:image"]\');
  return el ? (el.getAttribute("content") || "") : "";
}

function resolveMediaUrl(el, type) {
  if (type === "image" && el) return upgradeImgUrl(el.currentSrc || el.src || "");
  if (type === "video" && el) {
    var d = el.currentSrc || el.src || "";
    if (d && d.indexOf("blob:") !== 0 && d.indexOf("data:") !== 0) return d;
  }
  if (type === "video") { var m = getMetaVideoUrl(); if (m) return m; }
  if (type === "image") { var m2 = getMetaImageUrl(); if (m2) return upgradeImgUrl(m2); }
  return "";
}

function toast(msg) {
  var el = q(".is-toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(S.toastT);
  S.toastT = setTimeout(function() { el.classList.remove("show"); }, 2800);
}

function queueAdd(url, filename, type) {
  S.queue.push({ url: url, filename: filename, type: type, status: "pending", error: null });
  renderQueue();
  processQueue();
}

function processQueue() {
  if (S.queueBusy) return;
  var item = null;
  for (var i = 0; i < S.queue.length; i++) {
    if (S.queue[i].status === "pending") { item = S.queue[i]; break; }
  }
  if (!item) { S.queueBusy = false; return; }
  S.queueBusy = true;
  item.status = "downloading";
  renderQueue();
  chrome.runtime.sendMessage({ type: "DOWNLOAD_MEDIA", url: item.url, filename: item.filename, mediaType: item.type }, function(res) {
    if (res && res.ok) { item.status = "done"; toast("Download concluido!"); }
    else { item.status = "error"; item.error = (res && res.error) || "Erro"; toast("Erro no download"); }
    renderQueue();
    updateBadge();
    S.queueBusy = false;
    processQueue();
  });
}

function renderQueue() {
  var box = q(".is-queue-list");
  if (!box) return;
  if (S.queue.length === 0) { box.innerHTML = "<div class=\\'is-empty\\'>Nenhum item na fila</div>"; return; }
  var html = "";
  for (var i = 0; i < S.queue.length; i++) {
    var item = S.queue[i];
    var ico = (item.type === "image") ? ICO.image : ICO.video;
    var stCls = item.status;
    var stHtml = "";
    if (item.status === "done") stHtml = "<span class=\\"is-st done\\">" + ICO.check + "</span>";
    else if (item.status === "downloading") stHtml = "<span class=\\"is-st loading\\"><span class=\\"is-spin\\"></span></span>";
    else if (item.status === "error") stHtml = "<span class=\\"is-st err\\">" + ICO.x + "</span>";
    else stHtml = "<span class=\\"is-st pend\\">" + (i + 1) + "</span>";
    var name = item.filename ? item.filename.split("/").pop() : "Midia";
    html += "<div class=\\"is-q-item " + stCls + "\\">" + stHtml + "<span class=\\"is-q-ico\\">" + ico + "</span><div class=\\"is-q-info\\"><span class=\\"is-q-name\\">" + name + "</span><span class=\\"is-q-type\\">" + (item.type === "image" ? "Imagem" : "Video") + (item.status === "error" ? " - " + (item.error || "") : "") + "</span></div></div>";
  }
  box.innerHTML = html;
}

function loadHistory() {
  chrome.runtime.sendMessage({ type: "GET_HISTORY" }, function(res) {
    if (res && res.history) renderHistory(res.history);
  });
}

function renderHistory(items) {
  var box = q(".is-hist-list");
  if (!box) return;
  if (!items || items.length === 0) { box.innerHTML = "<div class=\\'is-empty\\'>Nenhum download ainda</div>"; return; }
  var html = "";
  var limit = Math.min(items.length, 50);
  for (var i = 0; i < limit; i++) {
    var item = items[i];
    var ico = (item.type === "image") ? ICO.image : ICO.video;
    var name = item.filename ? item.filename.split("/").pop() : "Midia";
    var time = item.timestamp ? relTime(item.timestamp) : "";
    html += "<div class=\\"is-h-item\\" data-idx=\\"" + i + "\\"><span class=\\"is-h-ico\\">" + ico + "</span><div class=\\"is-h-info\\"><span class=\\"is-h-name\\">" + name + "</span><span class=\\"is-h-time\\">" + time + "</span></div><button class=\\"is-h-dl\\" title=\\"Baixar novamente\\">" + ICO.download + "</button></div>";
  }
  box.innerHTML = html;
  var btns = box.querySelectorAll(".is-h-dl");
  for (var j = 0; j < btns.length; j++) {
    (function(idx) {
      btns[idx].addEventListener("click", function() {
        var it = items[idx];
        if (it && it.url) queueAdd(it.url, makeFilename(it.url, it.type), it.type);
      });
    })(j);
  }
}

function updateBadge() {
  var badge = q(".is-badge");
  if (!badge) return;
  var n = 0;
  for (var i = 0; i < S.queue.length; i++) {
    if (S.queue[i].status === "pending" || S.queue[i].status === "downloading") n++;
  }
  badge.textContent = n;
  if (n > 0) badge.classList.add("show"); else badge.classList.remove("show");
}

async function loadMedia() {
  var video = S.curVid, image = S.curImg;
  var type = video ? "video" : (image ? "image" : null);
  var el = video || image;
  var stage = q(".is-stage"), info = q(".is-info"), controls = q(".is-controls"), timeRow = q(".is-time-row");
  var vid = q(".is-video"), img = q(".is-image"), typeBadge = q(".is-type-badge");

  if (!type || !el) {
    stage.style.display = "none"; controls.style.display = "none"; timeRow.style.display = "none";
    info.style.display = "flex"; info.textContent = "Nenhuma midia detectada. Role ate um reel ou imagem.";
    S.curUrl = ""; return;
  }

  var url = resolveMediaUrl(el, type);
  S.curType = type;

  if (!url) {
    stage.style.display = "none"; controls.style.display = "none"; timeRow.style.display = "none";
    info.style.display = "flex";
    info.textContent = (type === "video") ? "Video detectado, aguardando URL..." : "Imagem detectada, aguardando URL...";
    return;
  }

  S.curUrl = url;
  info.style.display = "none";

  if (type === "video") {
    stage.style.display = "flex"; controls.style.display = "flex"; timeRow.style.display = "block";
    img.style.display = "none"; vid.style.display = "block";
    typeBadge.innerHTML = ICO.video + " Video";
    typeBadge.style.display = "flex";
    if (vid.getAttribute("src") !== url) {
      vid.pause(); vid.setAttribute("src", url); vid.load();
      vid.play().catch(function() { q(".is-play-btn").innerHTML = ICO.play; });
    }
    q(".is-play-btn").innerHTML = ICO.pause;
  } else {
    stage.style.display = "flex"; controls.style.display = "none"; timeRow.style.display = "none";
    vid.style.display = "none"; img.style.display = "block";
    typeBadge.innerHTML = ICO.image + " Imagem";
    typeBadge.style.display = "flex";
    if (img.getAttribute("src") !== url) img.setAttribute("src", url);
  }
}

function openPanel() { q(".is-panel").classList.add("open"); loadMedia(); }
function closePanel() {
  q(".is-panel").classList.remove("open");
  var v = q(".is-video");
  if (v) { v.pause(); v.removeAttribute("src"); v.load(); }
}
function togglePanel() { q(".is-panel").classList.contains("open") ? closePanel() : openPanel(); }

function switchTab(name) {
  var btns = qa(".is-tab-btn");
  for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("active", btns[i].dataset.tab === name);
  q(".is-tab-player").style.display = (name === "player") ? "flex" : "none";
  q(".is-tab-queue").style.display = (name === "queue") ? "flex" : "none";
  q(".is-tab-history").style.display = (name === "history") ? "flex" : "none";
  if (name === "queue") renderQueue();
  if (name === "history") loadHistory();
}

function tick() {
  S.curVid = findCurrentVideo();
  S.curImg = S.curVid ? null : findCurrentImage();
  positionCapture();
  var media = S.curVid || S.curImg;
  if (media && media !== S.lastMedia) {
    S.lastMedia = media;
    if (q(".is-panel").classList.contains("open") && q(".is-tab-player").style.display !== "none") loadMedia();
  }
}

function positionCapture() {
  var btn = q(".is-capture"), el = S.curVid || S.curImg;
  if (!el || !btn) { if (btn) btn.style.display = "none"; return; }
  var r = el.getBoundingClientRect();
  if (r.width < 40 || r.height < 40) { btn.style.display = "none"; return; }
  btn.style.display = "flex";
  btn.style.left = Math.max(8, r.right - 46) + "px";
  btn.style.top = Math.max(8, r.top + 8) + "px";
}

var ICO = {
  download: "<svg viewBox=\\"0 0 24 24\\" width=\\"16\\" height=\\"16\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><path d=\\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\\"/><polyline points=\\"7 10 12 15 17 10\\"/><line x1=\\"12\\" y1=\\"15\\" x2=\\"12\\" y2=\\"3\\"/></svg>",
  downloadLg: "<svg viewBox=\\"0 0 24 24\\" width=\\"22\\" height=\\"22\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\" stroke-linejoin=\\"round\\"><path d=\\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\\"/><polyline points=\\"7 10 12 15 17 10\\"/><line x1=\\"12\\" y1=\\"15\\" x2=\\"12\\" y2=\\"3\\"/></svg>",
  play: "<svg viewBox=\\"0 0 24 24\\" width=\\"18\\" height=\\"18\\" fill=\\"currentColor\\"><path d=\\"M8 5v14l11-7z\\"/></svg>",
  pause: "<svg viewBox=\\"0 0 24 24\\" width=\\"18\\" height=\\"18\\" fill=\\"currentColor\\"><rect x=\\"6\\" y=\\"4\\" width=\\"4\\" height=\\"16\\" rx=\\"1\\"/><rect x=\\"14\\" y=\\"4\\" width=\\"4\\" height=\\"16\\" rx=\\"1\\"/></svg>",
  close: "<svg viewBox=\\"0 0 24 24\\" width=\\"18\\" height=\\"18\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2.5\\" stroke-linecap=\\"round\\"><line x1=\\"18\\" y1=\\"6\\" x2=\\"6\\" y2=\\"18\\"/><line x1=\\"6\\" y1=\\"6\\" x2=\\"18\\" y2=\\"18\\"/></svg>",
  gear: "<svg viewBox=\\"0 0 24 24\\" width=\\"17\\" height=\\"17\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"3\\"/><path d=\\"M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z\\"/></svg>",
  refresh: "<svg viewBox=\\"0 0 24 24\\" width=\\"17\\" height=\\"17\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><polyline points=\\"23 4 23 10 17 10\\"/><path d=\\"M20.49 15a9 9 0 1 1-2.12-9.36L23 10\\"/></svg>",
  image: "<svg viewBox=\\"0 0 24 24\\" width=\\"15\\" height=\\"15\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><rect x=\\"3\\" y=\\"3\\" width=\\"18\\" height=\\"18\\" rx=\\"2\\"/><circle cx=\\"8.5\\" cy=\\"8.5\\" r=\\"1.5\\"/><polyline points=\\"21 15 16 10 5 21\\"/></svg>",
  video: "<svg viewBox=\\"0 0 24 24\\" width=\\"15\\" height=\\"15\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><polygon points=\\"23 7 16 12 23 17 23 7\\"/><rect x=\\"1\\" y=\\"5\\" width=\\"15\\" height=\\"14\\" rx=\\"2\\"/></svg>",
  trash: "<svg viewBox=\\"0 0 24 24\\" width=\\"14\\" height=\\"14\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><polyline points=\\"3 6 5 6 21 6\\"/><path d=\\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\\"/></svg>",
  check: "<svg viewBox=\\"0 0 24 24\\" width=\\"14\\" height=\\"14\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2.5\\" stroke-linecap=\\"round\\"><polyline points=\\"20 6 9 17 4 12\\"/></svg>",
  x: "<svg viewBox=\\"0 0 24 24\\" width=\\"14\\" height=\\"14\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2.5\\" stroke-linecap=\\"round\\"><line x1=\\"18\\" y1=\\"6\\" x2=\\"6\\" y2=\\"18\\"/><line x1=\\"6\\" y1=\\"6\\" x2=\\"18\\" y2=\\"18\\"/></svg>",
  player: "<svg viewBox=\\"0 0 24 24\\" width=\\"15\\" height=\\"15\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><polygon points=\\"5 3 19 12 5 21 5 3\\"/></svg>",
  list: "<svg viewBox=\\"0 0 24 24\\" width=\\"15\\" height=\\"15\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><line x1=\\"8\\" y1=\\"6\\" x2=\\"21\\" y2=\\"6\\"/><line x1=\\"8\\" y1=\\"12\\" x2=\\"21\\" y2=\\"12\\"/><line x1=\\"8\\" y1=\\"18\\" x2=\\"21\\" y2=\\"18\\"/><circle cx=\\"4\\" cy=\\"6\\" r=\\"1\\" fill=\\"currentColor\\"/><circle cx=\\"4\\" cy=\\"12\\" r=\\"1\\" fill=\\"currentColor\\"/><circle cx=\\"4\\" cy=\\"18\\" r=\\"1\\" fill=\\"currentColor\\"/></svg>",
  clock: "<svg viewBox=\\"0 0 24 24\\" width=\\"15\\" height=\\"15\\" fill=\\"none\\" stroke=\\"currentColor\\" stroke-width=\\"2\\" stroke-linecap=\\"round\\"><circle cx=\\"12\\" cy=\\"12\\" r=\\"10\\"/><polyline points=\\"12 6 12 12 16 14\\"/></svg>",
  brand: "<svg viewBox=\\"0 0 24 24\\" width=\\"16\\" height=\\"16\\" fill=\\"currentColor\\"><path d=\\"M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z\\"/></svg>"
};

var CSS = ":host{all:initial}*{box-sizing:border-box;margin:0;padding:0}:root{--bg:#09090b;--surface:#111115;--elevated:#1a1a21;--hover:#24242e;--border:rgba(255,255,255,0.06);--border-a:rgba(255,255,255,0.12);--t1:#f0f0f5;--t2:#9898ad;--t3:#55556a;--accent:#dc2743;--ok:#22c55e;--err:#ef4444;--r-sm:8px;--r-md:12px;--ease:cubic-bezier(0.4,0,0.2,1);--spring:cubic-bezier(0.34,1.56,0.64,1)}.is-fab{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);box-shadow:0 4px 20px rgba(220,39,67,0.4);transition:transform 0.2s var(--spring),box-shadow 0.2s var(--ease)}.is-fab:hover{transform:translateY(-3px) scale(1.06);box-shadow:0 8px 30px rgba(220,39,67,0.5),0 0 0 6px rgba(220,39,67,0.1)}.is-fab:active{transform:scale(0.95)}.is-fab .is-badge{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;background:var(--err);color:#fff;font:700 10px system-ui;border-radius:99px;display:none;align-items:center;justify-content:center;padding:0 5px;border:2px solid var(--bg)}.is-fab .is-badge.show{display:flex}.is-capture{position:fixed;z-index:2147483002;width:38px;height:38px;border:none;border-radius:var(--r-sm);cursor:pointer;display:none;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);box-shadow:0 4px 14px rgba(0,0,0,0.5);transition:transform 0.15s var(--spring)}.is-capture:hover{transform:scale(1.12)}.is-panel{position:fixed;top:0;right:0;height:100vh;width:400px;max-width:100vw;z-index:2147483001;display:flex;flex-direction:column;background:var(--bg);color:var(--t1);border-left:1px solid var(--border);font:13px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;transform:translateX(105%);transition:transform 0.3s var(--ease);box-shadow:-20px 0 60px rgba(0,0,0,0.5)}.is-panel.open{transform:translateX(0)}.is-head{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-bottom:1px solid var(--border);flex:0 0 auto;background:var(--surface)}.is-logo{display:flex;align-items:center;gap:8px;font-weight:800;font-size:14px;color:#fff}.is-logo svg{color:var(--accent)}.is-ver{font-size:9.5px;font-weight:700;color:var(--t3);background:var(--elevated);padding:2px 6px;border-radius:6px}.is-head-r{display:flex;align-items:center;gap:2px}.is-head-r button{background:none;border:none;color:var(--t2);cursor:pointer;padding:6px;border-radius:var(--r-sm);display:flex;transition:all 0.15s var(--ease)}.is-head-r button:hover{background:var(--hover);color:#fff}.is-tabs{display:flex;gap:2px;padding:8px 16px 0;flex:0 0 auto;background:var(--surface);border-bottom:1px solid var(--border)}.is-tab-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;padding:10px 8px;border:none;background:none;cursor:pointer;color:var(--t3);font:600 12px system-ui;border-radius:var(--r-sm) var(--r-sm) 0 0;border-bottom:2px solid transparent;transition:all 0.2s var(--ease)}.is-tab-btn:hover{color:var(--t2);background:rgba(255,255,255,0.03)}.is-tab-btn.active{color:#fff;border-bottom-color:var(--accent);background:rgba(220,39,67,0.06)}.is-tab-player,.is-tab-queue,.is-tab-history{display:none;flex-direction:column;flex:1;min-height:0;overflow:hidden}.is-tab-player{display:flex}.is-settings{display:none;flex-direction:column;gap:6px;padding:10px 16px;background:var(--elevated);border-bottom:1px solid var(--border);font-size:12px;color:var(--t2)}.is-settings.open{display:flex}.is-settings label{display:flex;align-items:center;gap:8px;cursor:pointer;padding:4px 0}.is-settings input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px}.is-stage{position:relative;flex:1;min-height:0;background:#000;display:flex;align-items:center;justify-content:center;cursor:pointer;overflow:hidden}.is-video{width:100%;max-height:100%;outline:none;display:block}.is-image{max-width:100%;max-height:100%;object-fit:contain;display:none}.is-timer{position:absolute;top:12px;left:12px;display:flex;align-items:baseline;gap:5px;padding:6px 10px;border-radius:var(--r-sm);background:rgba(0,0,0,0.6);backdrop-filter:blur(6px);color:#fff;font-variant-numeric:tabular-nums}.is-t-cur{font-size:22px;font-weight:800}.is-t-sep{color:var(--t2);font-size:13px}.is-t-total{font-size:13px;color:var(--t2)}.is-type-badge{position:absolute;top:12px;right:12px;padding:4px 10px;border-radius:99px;font:700 10px system-ui;text-transform:uppercase;letter-spacing:0.05em;background:rgba(0,0,0,0.6);backdrop-filter:blur(6px);color:var(--t2);display:none;align-items:center;gap:5px}.is-info{display:none;align-items:center;justify-content:center;flex:1;padding:30px 20px;text-align:center;color:var(--t3);font-size:12.5px;line-height:1.7}.is-controls{display:flex;align-items:center;gap:10px;padding:12px 16px 6px;flex:0 0 auto}.is-play-btn{width:36px;height:36px;flex:0 0 auto;border:none;border-radius:50%;background:#fff;color:#111;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform 0.1s var(--ease)}.is-play-btn:hover{background:#e5e7eb;transform:scale(1.06)}.is-progress{flex:1;accent-color:var(--accent);cursor:pointer;height:4px}.is-speed{flex:0 0 auto;background:var(--elevated);color:#fff;border:1px solid var(--border-a);border-radius:var(--r-sm);padding:5px 6px;font:600 11.5px system-ui;cursor:pointer}.is-time-row{padding:0 16px 8px;color:var(--t3);font-size:11.5px;font-variant-numeric:tabular-nums;flex:0 0 auto}.is-foot{display:flex;align-items:center;gap:8px;padding:12px 16px;border-top:1px solid var(--border);flex:0 0 auto;background:var(--surface)}.is-dl-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:7px;border:none;cursor:pointer;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);color:#fff;padding:11px 14px;border-radius:var(--r-md);font:700 13px system-ui;transition:filter 0.15s var(--ease)}.is-dl-btn:hover{filter:brightness(1.15)}.is-dl-btn:active{transform:scale(0.97)}.is-ref-btn{width:42px;height:42px;border:none;border-radius:var(--r-md);background:var(--elevated);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.15s var(--ease)}.is-ref-btn:hover{background:var(--hover)}.is-queue-list,.is-hist-list{flex:1;overflow-y:auto;padding:8px;scrollbar-width:thin;scrollbar-color:var(--elevated) transparent}.is-queue-list::-webkit-scrollbar,.is-hist-list::-webkit-scrollbar{width:5px}.is-queue-list::-webkit-scrollbar-thumb,.is-hist-list::-webkit-scrollbar-thumb{background:var(--elevated);border-radius:99px}.is-q-item,.is-h-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:var(--r-sm);margin-bottom:4px;transition:background 0.12s var(--ease)}.is-q-item:hover,.is-h-item:hover{background:var(--hover)}.is-q-item.done{opacity:0.6}.is-q-item.error{opacity:0.8}.is-st{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex:0 0 auto}.is-st.pend{background:var(--elevated);color:var(--t2)}.is-st.done{background:rgba(34,197,94,0.15);color:var(--ok)}.is-st.err{background:rgba(239,68,68,0.15);color:var(--err)}.is-st.loading{background:var(--elevated)}.is-spin{width:14px;height:14px;border:2px solid var(--border-a);border-top-color:var(--accent);border-radius:50%;animation:isSpin 0.7s linear infinite}@keyframes isSpin{to{transform:rotate(360deg)}}.is-q-ico,.is-h-ico{flex:0 0 auto;color:var(--t3);display:flex}.is-q-info,.is-h-info{flex:1;min-width:0}.is-q-name,.is-h-name{display:block;font-size:12px;font-weight:600;color:var(--t1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.is-q-type,.is-h-time{display:block;font-size:11px;color:var(--t3);margin-top:1px}.is-h-dl{flex:0 0 auto;width:32px;height:32px;border:none;border-radius:var(--r-sm);background:var(--elevated);color:var(--t2);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s var(--ease);opacity:0}.is-h-item:hover .is-h-dl{opacity:1}.is-h-dl:hover{background:var(--accent);color:#fff}.is-empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--t3);font-size:12.5px}.is-clear-btn{display:flex;align-items:center;justify-content:center;gap:6px;width:calc(100% - 16px);margin:0 8px 8px;padding:9px;border:1px dashed var(--border-a);border-radius:var(--r-sm);background:none;color:var(--t3);cursor:pointer;font:600 11.5px system-ui;transition:all 0.15s var(--ease);flex:0 0 auto}.is-clear-btn:hover{background:var(--hover);color:var(--err);border-color:var(--err)}.is-toast{position:fixed;left:50%;bottom:30px;z-index:2147483003;transform:translateX(-50%) translateY(10px);background:var(--elevated);color:#fff;padding:10px 20px;border-radius:var(--r-md);font:600 13px system-ui;box-shadow:0 10px 40px rgba(0,0,0,0.6),0 0 0 1px var(--border);opacity:0;visibility:hidden;pointer-events:none;white-space:nowrap;transition:all 0.25s var(--ease)}.is-toast.show{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}";

function buildUI() {
  if (S.shadow) return;
  var host = document.createElement("div");
  host.id = "is2-root";
  S.shadow = host.attachShadow({ mode: "open" });

  S.shadow.innerHTML = \'<style>\' + CSS + \'</style>\' +
    \'<button class="is-fab" title="InstaSave Pro">\' + ICO.downloadLg + \'<span class="is-badge">0</span></button>\' +
    \'<button class="is-capture" title="Abrir no InstaSave">\' + ICO.download + \'</button>\' +
    \'<div class="is-panel">\' +
      \'<div class="is-head"><span class="is-logo">\' + ICO.brand + \' InstaSave <span class="is-ver">v2.0</span></span><div class="is-head-r"><button class="is-gear-btn" title="Config">\' + ICO.gear + \'</button><button class="is-close-btn" title="Fechar">\' + ICO.close + \'</button></div></div>\' +
      \'<div class="is-tabs"><button class="is-tab-btn active" data-tab="player">\' + ICO.player + \' Player</button><button class="is-tab-btn" data-tab="queue">\' + ICO.list + \' Fila</button><button class="is-tab-btn" data-tab="history">\' + ICO.clock + \' Historico</button></div>\' +
      \'<div class="is-settings"><label><input type="checkbox" class="is-opt-loop" /> Repetir (loop)</label><label><input type="checkbox" class="is-opt-mute" /> Sem som (mudo)</label></div>\' +
      \'<div class="is-tab-player"><div class="is-stage"><video class="is-video" playsinline></video><img class="is-image" alt="Preview" /><div class="is-timer"><span class="is-t-cur">0:00</span><span class="is-t-sep">/</span><span class="is-t-total">0:00</span></div><div class="is-type-badge"></div></div><div class="is-info">Nenhuma midia detectada. Role ate um reel ou imagem.</div><div class="is-controls"><button class="is-play-btn" title="Play/Pause">\' + ICO.play + \'</button><input class="is-progress" type="range" min="0" max="0" value="0" step="0.1" /><select class="is-speed" title="Velocidade"><option value="0.5">0.5x</option><option value="0.75">0.75x</option><option value="1" selected>1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="1.75">1.75x</option><option value="2">2x</option></select></div><div class="is-time-row">0:00 / 0:00</div><div class="is-foot"><button class="is-dl-btn" title="Baixar">\' + ICO.download + \' Baixar</button><button class="is-ref-btn" title="Atualizar">\' + ICO.refresh + \'</button></div></div>\' +
      \'<div class="is-tab-queue"><div class="is-queue-list"><div class="is-empty">Nenhum item na fila</div></div><button class="is-clear-btn" data-clear="queue">\' + ICO.trash + \' Limpar concluidos</button></div>\' +
      \'<div class="is-tab-history"><div class="is-hist-list"><div class="is-empty">Nenhum download ainda</div></div><button class="is-clear-btn" data-clear="history">\' + ICO.trash + \' Limpar historico</button></div>\' +
    \'</div>\' +
    \'<div class="is-toast"></div>\';

  document.documentElement.appendChild(host);

  var vid = q(".is-video"), img = q(".is-image");

  q(".is-fab").addEventListener("click", togglePanel);
  q(".is-capture").addEventListener("click", openPanel);
  q(".is-close-btn").addEventListener("click", closePanel);
  q(".is-gear-btn").addEventListener("click", function() { q(".is-settings").classList.toggle("open"); });

  var tabBtns = qa(".is-tab-btn");
  for (var i = 0; i < tabBtns.length; i++) {
    (function(btn) {
      btn.addEventListener("click", function() { switchTab(btn.dataset.tab); });
    })(tabBtns[i]);
  }

  q(".is-opt-loop").addEventListener("change", function(e) { vid.loop = e.target.checked; });
  q(".is-opt-mute").addEventListener("change", function(e) { vid.muted = e.target.checked; });

  var playBtn = q(".is-play-btn"), bar = q(".is-progress"), timeEl = q(".is-time-row"), speedSel = q(".is-speed");

  function syncVideo() {
    var dur = isFinite(vid.duration) ? vid.duration : 0, cur = vid.currentTime || 0;
    q(".is-t-cur").textContent = fmtTime(cur);
    q(".is-t-total").textContent = fmtTime(dur);
    timeEl.textContent = fmtTime(cur) + " / " + fmtTime(dur);
    if (dur) { bar.max = dur; bar.value = cur; }
  }

  vid.addEventListener("loadedmetadata", syncVideo);
  vid.addEventListener("timeupdate", syncVideo);
  vid.addEventListener("play", function() { playBtn.innerHTML = ICO.pause; });
  vid.addEventListener("pause", function() { playBtn.innerHTML = ICO.play; });
  vid.addEventListener("ended", function() { playBtn.innerHTML = ICO.play; syncVideo(); });

  playBtn.addEventListener("click", function() { vid.paused ? vid.play().catch(function(){}) : vid.pause(); });
  bar.addEventListener("input", function() { if (isFinite(vid.duration)) vid.currentTime = +bar.value; });
  speedSel.addEventListener("change", function() { vid.playbackRate = +speedSel.value; });
  q(".is-stage").addEventListener("click", function() { vid.paused ? vid.play().catch(function(){}) : vid.pause(); });

  q(".is-dl-btn").addEventListener("click", function() {
    if (!S.curUrl) { toast("Nenhuma midia para baixar"); return; }
    queueAdd(S.curUrl, makeFilename(S.curUrl, S.curType), S.curType);
    switchTab("queue");
  });
  q(".is-ref-btn").addEventListener("click", function() { loadMedia(); });

  var clearBtns = qa(".is-clear-btn");
  for (var j = 0; j < clearBtns.length; j++) {
    (function(btn) {
      btn.addEventListener("click", function() {
        if (btn.dataset.clear === "queue") {
          S.queue = S.queue.filter(function(it) { return it.status !== "done" && it.status !== "error"; });
          renderQueue();
        } else {
          chrome.runtime.sendMessage({ type: "CLEAR_HISTORY" });
          renderHistory([]);
        }
      });
    })(clearBtns[j]);
  }
}

chrome.runtime.onMessage.addListener(function(msg) {
  if (!msg) return;
  if (msg.type === "OPEN_PANEL") { if (!S.shadow) buildUI(); openPanel(); tick(); }
  if (msg.type === "FORCE_SCAN") { if (!S.shadow) buildUI(); tick(); openPanel(); }
  if (msg.type === "GET_COUNTS") {
    var vids = document.querySelectorAll("video");
    var imgs = document.querySelectorAll("img");
    var imgCount = 0;
    for (var i = 0; i < imgs.length; i++) {
      var src = imgs[i].src || "";
      if (src.indexOf("cdninstagram.com") !== -1 || src.indexOf("fbcdn.net") !== -1) imgCount++;
    }
    if (msg._sender) msg._sender({ videos: vids.length, images: imgCount });
  }
});

function init() {
  if (!document.body) { requestAnimationFrame(init); return; }
  buildUI();
  tick();
  updateBadge();
  setInterval(updateBadge, 800);

  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && q(".is-panel").classList.contains("open")) closePanel();
  });

  window.addEventListener("scroll", throttle(function() { tick(); positionCapture(); }, 120), { passive: true });
  setInterval(tick, 1200);
  new MutationObserver(debounce(tick, 600)).observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
''')
print("OK: content.js")

# === POPUP HTML ===
open("popup.html", "w", encoding="utf-8").write('''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:340px;font:13px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#09090b;color:#f0f0f5;padding:0;overflow:hidden}
.head{display:flex;align-items:center;gap:10px;padding:16px 18px 12px;background:linear-gradient(135deg,rgba(220,39,67,0.12) 0%,rgba(188,24,136,0.08) 100%);border-bottom:1px solid rgba(255,255,255,0.06)}
.head-icon{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);display:flex;align-items:center;justify-content:center;color:#fff;flex:0 0 auto}
.head-text h1{font-size:15px;font-weight:800;color:#fff}
.head-text span{font-size:10px;color:#9898ad;font-weight:600}
.status{display:flex;align-items:center;gap:8px;padding:10px 18px;font-size:12px;color:#9898ad;border-bottom:1px solid rgba(255,255,255,0.04)}
.dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto;background:#55556a}
.dot.ok{background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,0.5)}
.dot.warn{background:#f59e0b;box-shadow:0 0 8px rgba(245,158,11,0.5)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px 18px}
.stat-card{background:#111115;border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:10px 12px;display:flex;align-items:center;gap:10px}
.stat-ico{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex:0 0 auto}
.stat-ico.vid{background:rgba(220,39,67,0.12);color:#dc2743}
.stat-ico.img{background:rgba(59,130,246,0.12);color:#3b82f6}
.stat-val{font-size:18px;font-weight:800;color:#fff;line-height:1}
.stat-label{font-size:10px;color:#55556a;font-weight:600}
.actions{padding:4px 18px 12px;display:flex;flex-direction:column;gap:8px}
.btn{width:100%;display:flex;align-items:center;justify-content:center;gap:8px;border:none;cursor:pointer;padding:11px 14px;border-radius:10px;font:700 13px system-ui;transition:all 0.15s ease}
.btn:active{transform:scale(0.97)}
.btn-primary{background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);color:#fff}
.btn-primary:hover{filter:brightness(1.12)}
.btn-primary:disabled{opacity:0.4;cursor:not-allowed;filter:none;transform:none}
.btn-ghost{background:rgba(255,255,255,0.06);color:#fff;border:1px solid rgba(255,255,255,0.1)}
.btn-ghost:hover{background:rgba(255,255,255,0.1)}
.btn-ghost:disabled{opacity:0.4;cursor:not-allowed;transform:none}
.history-section{border-top:1px solid rgba(255,255,255,0.05);padding:12px 18px 6px}
.history-title{font-size:11px;font-weight:700;color:#55556a;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px}
.history-list{max-height:160px;overflow-y:auto}
.history-list::-webkit-scrollbar{width:4px}
.history-list::-webkit-scrollbar-thumb{background:#1a1a21;border-radius:99px}
.h-item{display:flex;align-items:center;gap:10px;padding:7px 8px;border-radius:8px;transition:background 0.12s ease}
.h-item:hover{background:rgba(255,255,255,0.04)}
.h-ico{flex:0 0 auto;color:#55556a;display:flex}
.h-info{flex:1;min-width:0}
.h-name{display:block;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.h-time{display:block;font-size:10.5px;color:#55556a}
.h-empty{text-align:center;color:#55556a;font-size:12px;padding:16px 0}
.foot{padding:10px 18px;text-align:center;color:#3a3a4a;font-size:10.5px;border-top:1px solid rgba(255,255,255,0.04)}
</style>
</head>
<body>
<div class="head">
<div class="head-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg></div>
<div class="head-text"><h1>InstaSave Pro</h1><span>v2.0.0</span></div>
</div>
<div class="status"><span class="dot" id="dot"></span><span id="statusText">Verificando...</span></div>
<div class="stats">
<div class="stat-card"><div class="stat-ico vid"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg></div><div><div class="stat-val" id="videoCount">-</div><div class="stat-label">Videos capturados</div></div></div>
<div class="stat-card"><div class="stat-ico img"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div><div><div class="stat-val" id="imageCount">-</div><div class="stat-label">Imagens na pagina</div></div></div>
</div>
<div class="actions">
<button class="btn btn-primary" id="btnOpen" disabled>Abrir Player</button>
<button class="btn btn-ghost" id="btnScan" disabled>Escanear Midia</button>
</div>
<div class="history-section">
<div class="history-title">Ultimos Downloads</div>
<div class="history-list" id="historyList"><div class="h-empty">Carregando...</div></div>
</div>
<div class="foot">InstaSave Pro v2.0.0</div>
<script src="popup.js"></script>
</body>
</html>''')
print("OK: popup.html")

# === POPUP JS ===
open("popup.js", "w", encoding="utf-8").write('''"use strict";
var dot = document.getElementById("dot");
var statusText = document.getElementById("statusText");
var btnOpen = document.getElementById("btnOpen");
var btnScan = document.getElementById("btnScan");
var videoCount = document.getElementById("videoCount");
var imageCount = document.getElementById("imageCount");
var historyList = document.getElementById("historyList");

function activeTab(cb) {
  chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
    if (tabs && tabs[0]) cb(tabs[0]);
    else { statusText.textContent = "Nenhuma aba ativa."; dot.className = "dot warn"; }
  });
}

function send(tab, type) {
  try {
    chrome.tabs.sendMessage(tab.id, { type: type }, function() {
      if (chrome.runtime.lastError) {
        statusText.textContent = "Recarregue o Instagram e tente novamente.";
        dot.className = "dot warn";
      } else { window.close(); }
    });
  } catch(e) {
    statusText.textContent = "Erro ao se comunicar com a pagina.";
    dot.className = "dot warn";
  }
}

function relTime(ts) {
  var d = Date.now() - ts, m = Math.floor(d / 60000), h = Math.floor(d / 3600000), dy = Math.floor(d / 86400000);
  if (m < 1) return "agora"; if (m < 60) return m + "min atras"; if (h < 24) return h + "h atras"; return dy + "d atras";
}

var vidIco = \'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>\';
var imgIco = \'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>\';

function renderHistory(items) {
  if (!items || items.length === 0) { historyList.innerHTML = "<div class=\\"h-empty\\">Nenhum download ainda</div>"; return; }
  var html = "";
  var limit = Math.min(items.length, 8);
  for (var i = 0; i < limit; i++) {
    var item = items[i];
    var ico = (item.type === "image") ? imgIco : vidIco;
    var name = item.filename ? item.filename.split("/").pop() : "Midia";
    var time = item.timestamp ? relTime(item.timestamp) : "";
    html += "<div class=\\"h-item\\"><span class=\\"h-ico\\">" + ico + "</span><div class=\\"h-info\\"><span class=\\"h-name\\">" + name + "</span><span class=\\"h-time\\">" + time + "</span></div></div>";
  }
  historyList.innerHTML = html;
}

activeTab(function(tab) {
  var isIG = /instagram\\.com/.test(tab.url || "");
  if (!isIG) {
    statusText.textContent = "Abra uma pagina do Instagram.";
    dot.className = "dot warn";
    btnOpen.disabled = true;
    btnScan.disabled = true;
    videoCount.textContent = "0";
    imageCount.textContent = "0";
    return;
  }
  statusText.textContent = "Ativo nesta pagina";
  dot.className = "dot ok";
  btnOpen.disabled = false;
  btnScan.disabled = false;

  chrome.tabs.sendMessage(tab.id, { type: "GET_COUNTS" }, function(res) {
    if (chrome.runtime.lastError || !res) { videoCount.textContent = "-"; imageCount.textContent = "-"; return; }
    videoCount.textContent = res.videos || "0";
    imageCount.textContent = res.images || "0";
  });

  chrome.runtime.sendMessage({ type: "GET_HISTORY" }, function(res) {
    if (res && res.history) renderHistory(res.history);
    else historyList.innerHTML = "<div class=\\"h-empty\\">Nenhum download ainda</div>";
  });

  chrome.runtime.sendMessage({ type: "GET_STATUS" }, function(res) {
    if (res && res.captured != null) videoCount.textContent = res.captured;
  });
});

btnOpen.addEventListener("click", function() { activeTab(function(tab) { send(tab, "OPEN_PANEL"); }); });
btnScan.addEventListener("click", function() { activeTab(function(tab) { send(tab, "FORCE_SCAN"); }); });
''')
print("OK: popup.js")

print("")
print("=== TODOS OS ARQUIVOS CRIADOS COM SUCESSO ===")
print("Agora va em chrome://extensions/ e recarregue a extensao.")