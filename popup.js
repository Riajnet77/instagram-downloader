"use strict";
const statusEl = document.getElementById("status");
const mediaInfo = document.getElementById("mediaInfo");
const btnOpen = document.getElementById("btnOpen");
const btnScan = document.getElementById("btnScan");

function withTab(cb) {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    if (tabs && tabs[0]) cb(tabs[0]);
    else { statusEl.textContent = "Nenhuma aba ativa."; statusEl.className = "err"; }
  });
}

function send(tab, type, cb) {
  try {
    chrome.tabs.sendMessage(tab.id, { type }, response => {
      if (chrome.runtime.lastError) {
        statusEl.textContent = "Recarregue a pagina do Instagram e tente de novo.";
        statusEl.className = "warn";
      } else if (cb) cb(response);
    });
  } catch (e) {
    statusEl.textContent = "Erro ao comunicar com a pagina.";
    statusEl.className = "err";
  }
}

withTab(tab => {
  if (!/instagram\.com/i.test(tab.url || "")) {
    statusEl.textContent = "Abra uma pagina do Instagram para usar o InstaSave.";
    statusEl.className = "warn";
    btnOpen.disabled = true;
    btnScan.disabled = true;
    return;
  }

  statusEl.textContent = "Conectado. Escaneando midia...";
  statusEl.className = "ok";
  btnOpen.disabled = false;
  btnScan.disabled = false;

  // Perguntar ao content script o que detectou
  send(tab, "GET_MEDIA_INFO", resp => {
    if (!resp) return;
    let count = resp.count || 0;
    let pt = resp.pageType || "?";
    let types = resp.types || [];

    if (count > 0) {
      let photos = types.filter(t => t === "photo").length;
      let videos = types.filter(t => t === "video").length;
      statusEl.textContent = `${count} midia(s) detectada(s) nesta pagina.`;
      statusEl.className = "ok";

      let html = '<div class="mi-row"><span class="mi-badge ' + (pt === "reel" ? "mi-vd" : "") + '">' + pt + '</span></div>';
      if (photos) html += '<div class="mi-row"><span class="mi-badge mi-ph">Foto</span> ' + photos + (photos > 1 ? "fotos" : "foto") + '</div>';
      if (videos) html += '<div class="mi-row"><span class="mi-badge mi-vd">Video</span> ' + videos + (videos > 1 ? "videos" : "video") + '</div>';
      mediaInfo.innerHTML = html;
      mediaInfo.style.display = "block";
    } else {
      statusEl.textContent = "Nenhuma midia detectada. Navegue ate um post ou reel.";
      statusEl.className = "warn";
    }
  });
});

btnOpen.addEventListener("click", () => withTab(tab => send(tab, "OPEN_PANEL")));
btnScan.addEventListener("click", () => withTab(tab => send(tab, "FORCE_SCAN", () => window.close())));