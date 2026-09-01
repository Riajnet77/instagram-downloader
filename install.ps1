 $dir = Split-Path -Parent $MyInvocation.MyCommand.Path
 $utf8 = [System.Text.UTF8Encoding]::new($false)

@'
{
  "manifest_version": 3,
  "name": "InstaSave Pro",
  "version": "2.0.0",
  "description": "Baixe reels do Instagram com player e cronometro.",
  "permissions": ["downloads","storage","tabs","webRequest"],
  "host_permissions": [
    "https://www.instagram.com/*",
    "https://*.instagram.com/*",
    "https://*.cdninstagram.com/*",
    "https://*.fbcdn.net/*"
  ],
  "background": { "service_worker": "background.js" },
  "content_scripts": [{
    "matches": ["https://www.instagram.com/*"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }],
  "action": {
    "default_title": "InstaSave Pro",
    "default_popup": "popup.html",
    "default_icon": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" }
  },
  "icons": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" }
}
'@ | Set-Content -Path "$dir\manifest.json" -Encoding UTF8
Write-Host "OK manifest.json"

@'
"use strict";
var CAP_KEY = "is_cap";
var UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";
var captured = new Set();
function sGet(k) { return new Promise(function(r) { var s = chrome.storage.session || chrome.storage.local; s.get([k], function(d) { r(d[k] || null); }); }); }
function sSet(k, v) { var s = chrome.storage.session || chrome.storage.local; var o = {}; o[k] = v; s.set(o).catch(function() {}); }
sGet(CAP_KEY).then(function(p) { if (p) p.forEach(function(u) { captured.add(u); }); }).catch(function() {});
var pt = null;
function persist() { if (pt) return; pt = setTimeout(function() { pt = null; sSet(CAP_KEY, Array.from(captured).slice(-500)); }, 2000); }
function addCap(url) { var c = url.split("#")[0]; if (captured.has(c)) return; captured.add(c); persist(); }
chrome.webRequest.onBeforeRequest.addListener(function(d) { var u = d.url || ""; if (/\.mp4(\?|$)/i.test(u) || /\.m4v(\?|$)/i.test(u)) addCap(u); }, { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] });
chrome.webRequest.onHeadersReceived.addListener(function(d) { var hs = d.responseHeaders || []; for (var i = 0; i < hs.length; i++) { if ((hs[i].name || "").toLowerCase() === "content-type" && /^video\//i.test(hs[i].value || "")) { addCap(d.url); break; } } }, { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] }, ["responseHeaders"]);
async function fetchMedia(url) { var r = await fetch(url, { method: "GET", credentials: "include", headers: { Accept: "*/*", Referer: "https://www.instagram.com/", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "cross-site", "User-Agent": UA } }); if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); }
async function doDL(url, filename) { try { var blob = await fetchMedia(url); var obj = URL.createObjectURL(blob); var id = await chrome.downloads.download({ url: obj, filename: filename, saveAs: false, conflictAction: "uniquify" }); setTimeout(function() { try { URL.revokeObjectURL(obj); } catch(e) {} }, 120000); return { ok: true, id: id }; } catch(e) { try { var id2 = await chrome.downloads.download({ url: url, filename: filename, saveAs: false, conflictAction: "uniquify" }); return { ok: true, id: id2 }; } catch(e2) { return { ok: false, error: e2.message }; } } }
chrome.runtime.onMessage.addListener(function(msg, sender, send) { if (!msg || !msg.type) return false; if (msg.type === "DOWNLOAD_MEDIA") { doDL(msg.url, msg.filename).then(send); return true; } if (msg.type === "GET_MEDIA_URLS") { send({ urls: Array.from(captured) }); return false; } if (msg.type === "GET_STATUS") { send({ ok: true, version: "2.0.0" }); return false; } return false; });
'@ | Set-Content -Path "$dir\background.js" -Encoding UTF8
Write-Host "OK background.js"

@'
(() => {
  "use strict";
  if (window.__INSTASAVE_LOADED__) return;
  window.__INSTASAVE_LOADED__ = true;

  let shadow = null, fab = null, captureBtn = null, panel = null, panelVideo = null;
  let currentEl = null, lastEl = null, currentUrl = "", toastEl = null, toastTimer = null;

  const $ = (sel) => shadow.querySelector(sel);
  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
  function throttle(fn, ms) { let last = 0; return (...a) => { const now = Date.now(); if (now - last >= ms) { last = now; fn(...a); } }; }
  function formatTime(sec) { if (!isFinite(sec) || sec < 0) sec = 0; const s = Math.floor(sec); const m = Math.floor((s % 3600) / 60); const ss = String(s % 60).padStart(2, "0"); return m + ":" + ss; }

  function directVideoSrc(v) {
    let src = v.currentSrc || v.src || "";
    if (!src && v.querySelector) { const s = v.querySelector("source[src]"); if (s) src = s.src || ""; }
    if (!src) src = v.getAttribute("src") || "";
    if (!src || src.startsWith("blob:") || src.startsWith("data:")) return "";
    return src;
  }

  function getMetaVideoUrl() {
    const secure = document.querySelector('meta[property="og:video:secure_url"]');
    if (secure && secure.getAttribute("content")) return secure.getAttribute("content");
    const plain = document.querySelector('meta[property="og:video"]');
    if (plain && plain.getAttribute("content")) return plain.getAttribute("content");
    return "";
  }

  async function getLatestCapturedUrl() {
    try {
      const res = await chrome.runtime.sendMessage({ type: "GET_MEDIA_URLS" });
      if (res && res.urls && res.urls.length) return res.urls[res.urls.length - 1];
    } catch (e) {}
    return "";
  }

  async function resolveVideoUrl(el) {
    if (el) { const direct = directVideoSrc(el); if (direct) return direct; }
    const meta = getMetaVideoUrl(); if (meta) return meta;
    return await getLatestCapturedUrl();
  }

  function extFor(url) { const m = url.split("?")[0].match(/\.([a-z0-9]{3,4})$/i); if (m && /^(mp4|m4v)$/i.test(m[1])) return m[1].toLowerCase(); return "mp4"; }
  function buildFilename(url) {
    const d = new Date(); const p = (n) => String(n).padStart(2, "0");
    const stamp = d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + "_" + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
    return "instagram/reel_" + stamp + "." + extFor(url);
  }

  async function download(url) {
    if (!url) { toast("Aguardando URL do video..."); return; }
    const filename = buildFilename(url);
    try {
      const res = await chrome.runtime.sendMessage({ type: "DOWNLOAD_MEDIA", url, filename });
      toast(res && res.ok ? "Download iniciado!" : (res && res.error) || "Erro ao baixar");
    } catch (e) { toast("Nao foi possivel iniciar o download"); }
  }

  function findCurrentVideo() {
    const vids = document.querySelectorAll("video");
    const vh = window.innerHeight;
    let best = null, bestScore = -1;
    vids.forEach((v) => {
      if (v.closest("#instasave-root")) return;
      const r = v.getBoundingClientRect();
      if (r.width < 20 || r.height < 20) return;
      const visible = Math.min(r.bottom, vh) - Math.max(r.top, 0);
      if (visible <= 0) return;
      const centerDist = Math.abs(r.top + r.height / 2 - vh / 2);
      let score = visible - centerDist;
      if (!v.paused && !v.ended) score += vh * 2;
      if (score > bestScore) { bestScore = score; best = v; }
    });
    return best;
  }

  function positionCaptureBtn() {
    if (!captureBtn || !currentEl) { if (captureBtn) captureBtn.style.display = "none"; return; }
    const r = currentEl.getBoundingClientRect();
    if (r.width < 20 || r.height < 20) { captureBtn.style.display = "none"; return; }
    captureBtn.style.display = "flex";
    captureBtn.style.left = Math.max(8, r.right - 44) + "px";
    captureBtn.style.top = Math.max(8, r.top + 8) + "px";
  }

  function tick() {
    currentEl = findCurrentVideo();
    positionCaptureBtn();
    if (currentEl && currentEl !== lastEl) {
      lastEl = currentEl;
      if (panel.classList.contains("open")) loadPanel(currentEl);
    }
  }

  async function loadPanel(el) {
    const mediaBox = $(".is-panel-media");
    const infoEl = $(".is-panel-info");
    const url = await resolveVideoUrl(el);
    if (!url) {
      mediaBox.style.display = "none";
      $(".is-controls").style.display = "none";
      $(".is-time").style.display = "none";
      infoEl.style.display = "block";
      infoEl.textContent = "Nenhum video encontrado ainda. Role ate um reel e aguarde ele tocar.";
      currentUrl = "";
      resetTimerUI();
      return;
    }
    currentUrl = url;
    infoEl.style.display = "none";
    mediaBox.style.display = "flex";
    $(".is-controls").style.display = "flex";
    $(".is-time").style.display = "block";
    const v = $(".is-panel-video");
    if (v.getAttribute("src") !== url) {
      v.pause(); v.setAttribute("src", url); v.load();
      v.play().catch(() => { $(".is-play").innerHTML = ICONS.play; });
    }
    $(".is-play").innerHTML = ICONS.pause;
  }

  function resetTimerUI() {
    $(".is-timer-cur").textContent = "0:00";
    $(".is-timer-total").textContent = "0:00";
    $(".is-time").textContent = "0:00 / 0:00";
    const bar = $(".is-progress"); bar.value = 0; bar.max = 0;
  }

  function openPanel() { panel.classList.add("open"); loadPanel(currentEl || null); }
  function closePanel() { panel.classList.remove("open"); const v = $(".is-panel-video"); if (v) { v.pause(); v.removeAttribute("src"); v.load(); } }
  function togglePanel() { panel.classList.contains("open") ? closePanel() : openPanel(); }

  function toast(msg) {
    if (!toastEl) return; toastEl.textContent = msg; toastEl.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }

  const ICONS = {
    download: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M11 2h2v10.17l3.59-3.58L18 10l-6 6-6-6 1.41-1.41L11 12.17V2zM4 20h16v2H4v-2z"/></svg>',
    downloadBig: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M11 2h2v10.17l3.59-3.58L18 10l-6 6-6-6 1.41-1.41L11 12.17V2zM4 20h16v2H4v-2z"/></svg>',
    play: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M6 19h4V5H6v14zM14 5v14h4V5h-4z"/></svg>',
    close: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M17.65 6.35A7.95 7.95 0 0012 4a8 8 0 108 8h-2a6 6 0 11-1.76-4.24L13 11h7V4l-2.35 2.35z"/></svg>',
    brand: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm4.2 8.5l-5.5 3.2c-.3.2-.7 0-.7-.4V7.2c0-.4.4-.6.7-.4l5.5 3.2c.3.2.3.7 0 .9z"/></svg>'
  };

  const STYLES = `
    :host { all: initial; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    .is-capture { position: fixed; z-index: 2147483002; width: 36px; height: 36px; border: none; border-radius: 10px; cursor: pointer; display: none; align-items: center; justify-content: center; color: #fff; background: linear-gradient(45deg, #dc2743, #bc1888); box-shadow: 0 4px 16px rgba(0,0,0,.45); transition: transform .12s ease; }
    .is-capture:hover { transform: scale(1.08); }
    .is-fab { position: fixed; right: 18px; bottom: 18px; z-index: 2147483000; width: 54px; height: 54px; border-radius: 50%; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #fff; background: linear-gradient(45deg, #f09433, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888); box-shadow: 0 6px 20px rgba(220,39,67,.45); transition: transform .15s ease, box-shadow .15s ease; }
    .is-fab:hover { transform: translateY(-2px) scale(1.04); box-shadow: 0 10px 26px rgba(220,39,67,.55); }
    .is-panel { position: fixed; top: 0; right: 0; height: 100vh; width: 400px; max-width: 100vw; z-index: 2147483001; display: flex; flex-direction: column; background: #101216; color: #e7e9ee; border-left: 1px solid rgba(255,255,255,.1); font: 13px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif; transform: translateX(105%); transition: transform .22s ease; box-shadow: -18px 0 50px rgba(0,0,0,.5); user-select: none; }
    .is-panel.open { transform: translateX(0); }
    .is-panel-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,.08); flex: 0 0 auto; cursor: grab; }
    .is-panel-head:active { cursor: grabbing; }
    .is-logo { display: inline-flex; align-items: center; gap: 7px; font-weight: 700; font-size: 14px; color: #fff; }
    .is-logo svg { color: #dc2743; }
    .is-ver { font-size: 10px; font-weight: 600; color: #8a919c; background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 5px; }
    .is-head-actions { display: flex; align-items: center; gap: 4px; }
    .is-head-actions button { background: none; border: none; color: #8a919c; cursor: pointer; display: inline-flex; padding: 5px; border-radius: 7px; }
    .is-head-actions button:hover { background: rgba(255,255,255,.08); color: #fff; }
    .is-panel-media { position: relative; flex: 1; min-height: 0; background: #000; display: flex; align-items: center; justify-content: center; cursor: pointer; }
    .is-panel-video { width: 100%; max-height: 100%; outline: none; }
    .is-timer { position: absolute; top: 10px; left: 10px; display: flex; align-items: baseline; gap: 6px; padding: 6px 10px; border-radius: 8px; background: rgba(0,0,0,.55); color: #fff; font-variant-numeric: tabular-nums; backdrop-filter: blur(3px); }
    .is-timer-cur { font-size: 22px; font-weight: 800; letter-spacing: .03em; }
    .is-timer-sep { color: #9aa1ab; font-size: 14px; }
    .is-timer-total { font-size: 14px; color: #c6cbd3; }
    .is-panel-info { display: none; padding: 22px 16px; text-align: center; color: #6b7280; font-size: 12.5px; line-height: 1.6; }
    .is-controls { display: flex; align-items: center; gap: 10px; padding: 10px 14px 4px; flex: 0 0 auto; }
    .is-play { width: 34px; height: 34px; flex: 0 0 auto; border: none; border-radius: 50%; background: #fff; color: #111; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    .is-play:hover { background: #e5e7eb; }
    .is-progress { flex: 1; accent-color: #dc2743; cursor: pointer; }
    .is-speed { flex: 0 0 auto; background: rgba(255,255,255,.08); color: #fff; border: 1px solid rgba(255,255,255,.15); border-radius: 7px; padding: 5px 6px; font: 600 12px system-ui; cursor: pointer; }
    .is-time { padding: 0 14px 8px; color: #9aa1ab; font-size: 12px; font-variant-numeric: tabular-nums; flex: 0 0 auto; }
    .is-panel-foot { display: flex; align-items: center; gap: 8px; padding: 12px 14px; border-top: 1px solid rgba(255,255,255,.08); flex: 0 0 auto; }
    .is-download { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: none; cursor: pointer; background: linear-gradient(45deg, #dc2743, #bc1888); color: #fff; padding: 11px 14px; border-radius: 10px; font: 700 13px system-ui; }
    .is-download:hover { filter: brightness(1.12); }
    .is-refresh { width: 42px; height: 42px; border: none; border-radius: 10px; background: rgba(255,255,255,.08); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; }
    .is-refresh:hover { background: rgba(255,255,255,.14); }
    .is-toast { position: fixed; left: 50%; bottom: 28px; z-index: 2147483003; transform: translateX(-50%); background: #111; color: #fff; padding: 10px 18px; border-radius: 10px; font: 600 13px system-ui; box-shadow: 0 10px 30px rgba(0,0,0,.5); opacity: 0; visibility: hidden; transition: opacity .2s ease, transform .2s ease, visibility .2s; pointer-events: none; white-space: nowrap; }
    .is-toast.show { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(-4px); }
  `;

  function initRoot() {
    if (shadow) return;
    const host = document.createElement("div");
    host.id = "instasave-root";
    shadow = host.attachShadow({ mode: "open" });

    shadow.innerHTML = `<style>${STYLES}</style>
      <button class="is-capture" title="Abrir este reel no InstaSave">${ICONS.download}</button>
      <button class="is-fab" title="InstaSave - abrir player do reel atual">${ICONS.downloadBig}</button>
      <div class="is-panel">
        <div class="is-panel-head">
          <span class="is-logo">${ICONS.brand} InstaSave <span class="is-ver">v2.0</span></span>
          <div class="is-head-actions">
            <button class="is-panel-close" title="Fechar">${ICONS.close}</button>
          </div>
        </div>
        <div class="is-panel-media">
          <video class="is-panel-video" playsinline></video>
          <div class="is-timer">
            <span class="is-timer-cur">0:00</span>
            <span class="is-timer-sep">/</span>
            <span class="is-timer-total">0:00</span>
          </div>
        </div>
        <div class="is-panel-info">Nenhum video detectado. Role ate um reel e aguarde ele tocar.</div>
        <div class="is-controls">
          <button class="is-play" title="Play / Pause">${ICONS.play}</button>
          <input class="is-progress" type="range" min="0" max="0" value="0" step="0.1" />
          <select class="is-speed" title="Velocidade de reproducao">
            <option value="0.5">0.5x</option>
            <option value="0.75">0.75x</option>
            <option value="1" selected>1x</option>
            <option value="1.25">1.25x</option>
            <option value="1.5">1.5x</option>
            <option value="2">2x</option>
          </select>
        </div>
        <div class="is-time">0:00 / 0:00</div>
        <div class="is-panel-foot">
          <button class="is-download" title="Baixar video">${ICONS.download} Baixar video</button>
          <button class="is-refresh" title="Atualizar para o reel atual">${ICONS.refresh}</button>
        </div>
      </div>
      <div class="is-toast"></div>`;

    document.documentElement.appendChild(host);
    fab = $(".is-fab");
    captureBtn = $(".is-capture");
    panel = $(".is-panel");
    panelVideo = $(".is-panel-video");
    toastEl = $(".is-toast");

    fab.addEventListener("click", togglePanel);
    captureBtn.addEventListener("click", () => openPanel());
    $(".is-panel-close").addEventListener("click", closePanel);

    const v = panelVideo;
    const playBtn = $(".is-play");
    const bar = $(".is-progress");
    const timeEl = $(".is-time");
    const speedSel = $(".is-speed");

    const sync = () => {
      const dur = isFinite(v.duration) ? v.duration : 0;
      const cur = v.currentTime || 0;
      $(".is-timer-cur").textContent = formatTime(cur);
      $(".is-timer-total").textContent = formatTime(dur);
      timeEl.textContent = formatTime(cur) + " / " + formatTime(dur);
      if (dur) { bar.max = dur; bar.value = cur; }
    };

    v.addEventListener("loadedmetadata", sync);
    v.addEventListener("timeupdate", sync);
    v.addEventListener("play", () => playBtn.innerHTML = ICONS.pause);
    v.addEventListener("pause", () => playBtn.innerHTML = ICONS.play);
    v.addEventListener("ended", () => { playBtn.innerHTML = ICONS.play; sync(); });

    playBtn.addEventListener("click", () => { v.paused ? v.play().catch(() => {}) : v.pause(); });
    bar.addEventListener("input", () => { if (isFinite(v.duration)) v.currentTime = Number(bar.value); });
    speedSel.addEventListener("change", () => { v.playbackRate = parseFloat(speedSel.value); });
    $(".is-download").addEventListener("click", () => download(currentUrl));
    $(".is-refresh").addEventListener("click", () => loadPanel(currentEl || null));

    const stage = $(".is-panel-media");
    stage.addEventListener("click", () => { v.paused ? v.play().catch(() => {}) : v.pause(); });

    // DRAG
    const head = $(".is-panel-head");
    let dragging = false, startX, startY, startLeft, startTop;
    head.addEventListener("mousedown", (e) => {
      dragging = true; startX = e.clientX; startY = e.clientY;
      const rect = panel.getBoundingClientRect();
      startLeft = rect.left; startTop = rect.top;
      panel.style.transition = "none";
      panel.style.right = "auto";
      panel.style.left = startLeft + "px";
      panel.style.top = startTop + "px";
      e.preventDefault();
    });
    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      panel.style.left = (startLeft + e.clientX - startX) + "px";
      panel.style.top = (startTop + e.clientY - startY) + "px";
    });
    document.addEventListener("mouseup", () => {
      if (dragging) { dragging = false; panel.style.transition = ""; }
    });
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg) return;
    if (msg.type === "OPEN_PANEL") { if (!shadow) initRoot(); openPanel(); tick(); }
    if (msg.type === "FORCE_SCAN") { if (!shadow) initRoot(); tick(); openPanel(); }
  });

  function start() {
    if (!document.body) { requestAnimationFrame(start); return; }
    initRoot(); tick();
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && panel.classList.contains("open")) closePanel(); });
    window.addEventListener("scroll", throttle(() => { tick(); positionCaptureBtn(); }, 120), { passive: true });
    setInterval(tick, 1200);
    new MutationObserver(debounce(tick, 600)).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
'@ | Set-Content -Path "$dir\content.js" -Encoding UTF8
Write-Host "OK content.js"

@'
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:300px;font:13px/1.5 system-ui,sans-serif;background:#14161a;color:#e7e9ee;padding:16px}
header{display:flex;align-items:center;gap:8px;margin-bottom:10px}
header svg{color:#dc2743}
header h1{font-size:15px;font-weight:800;color:#fff}
p{color:#9aa1ab;margin-bottom:14px}
button{width:100%;display:block;border:none;cursor:pointer;padding:10px 12px;border-radius:10px;font:700 13px system-ui;margin-bottom:8px}
.primary{background:linear-gradient(45deg,#dc2743,#bc1888);color:#fff}
.primary:hover{filter:brightness(1.12)}
.ghost{background:rgba(255,255,255,.08);color:#fff;border:1px solid rgba(255,255,255,.14)}
.ghost:hover{background:rgba(255,255,255,.14)}
.primary:disabled,.ghost:disabled{opacity:.35;cursor:not-allowed;filter:none}
footer{margin-top:12px;color:#6b7280;font-size:11.5px;border-top:1px solid rgba(255,255,255,.08);padding-top:10px}
.ok{color:#34d399;font-weight:700}
.warn{color:#fbbf24;font-weight:700}
</style></head>
<body>
<header>
<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm4.2 8.5l-5.5 3.2c-.3.2-.7 0-.7-.4V7.2c0-.4.4-.6.7-.4l5.5 3.2c.3.2.3.7 0 .9z"/></svg>
<h1>InstaSave</h1>
</header>
<p id="status">Verificando a pagina atual...</p>
<button class="primary" id="openPanel" disabled>Abrir player do reel</button>
<button class="ghost" id="scan" disabled>Atualizar para o reel atual</button>
<footer>Arraste o painel pela barra de titulo superior.</footer>
<script src="popup.js"></script>
</body></html>
'@ | Set-Content -Path "$dir\popup.html" -Encoding UTF8
Write-Host "OK popup.html"

@'
"use strict";
const statusEl = document.getElementById("status");
function activeTab(cb) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs[0]) cb(tabs[0]);
    else { statusEl.textContent = "Nenhuma aba ativa encontrada."; statusEl.className = "warn"; }
  });
}
function sendToTab(tab, type) {
  try {
    chrome.tabs.sendMessage(tab.id, { type }, () => {
      if (chrome.runtime.lastError) { statusEl.textContent = "Recarregue a pagina do Instagram e tente de novo."; statusEl.className = "warn"; }
      else { window.close(); }
    });
  } catch (e) { statusEl.textContent = "Erro ao enviar mensagem para a pagina."; statusEl.className = "warn"; }
}
activeTab((tab) => {
  if (!/instagram\.com/.test(tab.url || "")) {
    statusEl.textContent = "Abra uma pagina do Instagram para usar o InstaSave.";
    statusEl.className = "warn";
    document.getElementById("openPanel").disabled = true;
    document.getElementById("scan").disabled = true;
    return;
  }
  statusEl.textContent = "Pronto. O InstaSave esta ativo nesta pagina.";
  statusEl.className = "ok";
});
document.getElementById("openPanel").addEventListener("click", () => { activeTab((tab) => sendToTab(tab, "OPEN_PANEL")); });
document.getElementById("scan").addEventListener("click", () => { activeTab((tab) => sendToTab(tab, "FORCE_SCAN")); });
'@ | Set-Content -Path "$dir\popup.js" -Encoding UTF8
Write-Host "OK popup.js"

Write-Host ""
Write-Host "=== TODOS OS ARQUIVOS CRIADOS ===" -ForegroundColor Green
Write-Host "1. Va em chrome://extensions/" -ForegroundColor Yellow
Write-Host "2. Clique no botao RECARREGAR na extensao" -ForegroundColor Yellow
Write-Host "3. Abra o Instagram nos Reels" -ForegroundColor Yellow
Write-Host "4. Clique no botao rosa no canto inferior direito" -ForegroundColor Yellow
Write-Host "5. Arraste o painel pela barra de titulo" -ForegroundColor Yellow