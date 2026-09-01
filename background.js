"use strict";
var CAP_KEY = "is_cap";
var UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";
var captured = new Set();

function sGet(k) { return new Promise(function(r) { (chrome.storage.session || chrome.storage.local).get([k], function(d) { r(d[k] || null); }); }); }
function sSet(k, v) { var o = {}; o[k] = v; (chrome.storage.session || chrome.storage.local).set(o).catch(function() {}); }

sGet(CAP_KEY).then(function(p) { if (p) p.forEach(function(u) { captured.add(u); }); }).catch(function() {});

var pt = null;
function persist() { if (pt) return; pt = setTimeout(function() { pt = null; sSet(CAP_KEY, Array.from(captured).slice(-500)); }, 2000); }
function addCap(url) { var c = url.split("#")[0]; if (captured.has(c)) return; captured.add(c); persist(); }

// Capturar videos
chrome.webRequest.onBeforeRequest.addListener(function(d) {
  var u = d.url || "";
  if (/\.mp4(\?|$)/i.test(u) || /\.m4v(\?|$)/i.test(u)) addCap(u);
}, { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] });

// Capturar imagens grandes (conteudo, nao UI)
chrome.webRequest.onHeadersReceived.addListener(function(d) {
  var hs = d.responseHeaders || [];
  for (var i = 0; i < hs.length; i++) {
    var name = (hs[i].name || "").toLowerCase();
    var val = (hs[i].value || "").toLowerCase();
    if (name === "content-type" && /^image\/(jpeg|png)/.test(val)) {
      // Filtrar por tamanho — imagens de conteudo sao grandes
      var cl = 0;
      for (var j = 0; j < hs.length; j++) {
        if ((hs[j].name || "").toLowerCase() === "content-length") {
          cl = parseInt(hs[j].value) || 0;
          break;
        }
      }
      if (cl > 30000) addCap(d.url);
      break;
    }
    if (name === "content-type" && /^video\//.test(val)) {
      addCap(d.url);
      break;
    }
  }
}, { urls: ["*://*.cdninstagram.com/*", "*://*.fbcdn.net/*"] }, ["responseHeaders"]);

async function fetchMedia(url) {
  var r = await fetch(url, {
    method: "GET", credentials: "include",
    headers: {
      Accept: "*/*", Referer: "https://www.instagram.com/",
      "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
      "Sec-Fetch-Site": "cross-site", "User-Agent": UA
    }
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  var ct = r.headers.get("content-type") || "";
  if (ct.includes("text/html")) throw new Error("Resposta HTML ao inves de midia");
  return r.blob();
}

async function doDL(url, filename) {
  try {
    var blob = await fetchMedia(url);
    var obj = URL.createObjectURL(blob);
    var id = await chrome.downloads.download({ url: obj, filename: filename, saveAs: false, conflictAction: "uniquify" });
    setTimeout(function() { try { URL.revokeObjectURL(obj); } catch(e) {} }, 120000);
    return { ok: true, id: id };
  } catch(e) {
    try {
      var id2 = await chrome.downloads.download({ url: url, filename: filename, saveAs: false, conflictAction: "uniquify" });
      return { ok: true, id: id2 };
    } catch(e2) {
      return { ok: false, error: e2.message };
    }
  }
}

chrome.runtime.onMessage.addListener(function(msg, sender, send) {
  if (!msg || !msg.type) return false;

  if (msg.type === "DOWNLOAD_MEDIA") {
    doDL(msg.url, msg.filename).then(send);
    return true;
  }

  if (msg.type === "DOWNLOAD_ALL") {
    var items = msg.items || [];
    var results = [];
    (async function() {
      for (var i = 0; i < items.length; i++) {
        var r = await doDL(items[i].url, items[i].filename);
        results.push(r);
        if (i < items.length - 1) await new Promise(function(res) { setTimeout(res, 400); });
      }
      send({ results: results });
    })();
    return true;
  }

  if (msg.type === "GET_MEDIA_URLS") {
    send({ urls: Array.from(captured) });
    return false;
  }

  if (msg.type === "GET_STATUS") {
    send({ ok: true, version: "3.0.0", captured: captured.size });
    return false;
  }

  return false;
});