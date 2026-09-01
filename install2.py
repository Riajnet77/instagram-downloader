import os
os.chdir(os.path.dirname(os.path.abspath(__file__))

c1 = r'''(() => {
  "use strict";
  if (window.__IS_LOADED__) return;
  window.__IS_LOADED__ = true;
  let shadow=null,panel=null,curEl=null,lastEl=null,panelVid=null,curUrl="",toastEl=null,toastT=null;
  const vid=()=>document.querySelector("#is-root video");
  const $=s=>shadow.querySelector(s);
  function debounce(f,m){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),m)}}
  function throttle(f,m){let l=0;return(...a)=>{let n=Date.now();if(n-l>=m){l=n;f(...a)}}}
  function fmt(s){if(!isFinite(s)||s<0)s=0;let sec=Math.floor(s),m=Math.floor((sec%3600)/60);return m+":"+String(sec%60).padStart(2,"0")}

  function getPerfUrl(){try{let e=performance.getEntriesByType("resource"),mp=[];for(let i=0;i<e.length;i++)if(/\.mp4(\?|$)/i.test(e[i].name))mp.push(e[i]);if(mp.length)return mp[mp.length-1].name}catch(e){return""}}

  function mkName(u){let d=new Date(),p=n=>String(n).padStart(2,"0");return"instagram/reel_"+d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+"_"+p(d.getHours())+p(d.getMinutes())+p(d.getSeconds())+".mp4"}

  async function dl(u){if(!u){toast("Sem URL");return}toast("Baixando...");try{let r=await chrome.runtime.sendMessage({type:"DOWNLOAD_MEDIA",url:u,filename:mkName(u)};toast(r&&r.ok?"Download iniciado!":"Erro")}catch(e){toast("Erro")}}

  function findVid(){let vs=document.querySelectorAll("video"),vh=window.innerHeight,best=null,bs=-1;vs.forEach(v=>{if(v.closest("#is-root"))return;let r=v.getBoundingClientRect();if(r.width<40||r.height<40)return;let vis=Math.min(r.bottom,vh)-Math.max(r.top,0);if(vis<=0)return;let cd=Math.abs(r.top+r.height/2-vh/2),sc=vis-cd;if(!v.paused&&!v.ended)sc+=vh*2;if(sc>bs){bs=sc;best=v}});return best}

  function posCap(){let b=$(".is-cap");if(!b||!curEl){if(b)b.style.display="none";return}let r=curEl.getBoundingClientRect();if(r.width<40||r.height<40){b.style.display="none";return}b.style.display="flex";b.style.left=Math.max(8,r.right-42)+"px";b.style.top=Math.max(8,r.top+8)+"px"}

  function tick(){
    let nv=findVid();
    if(panelVid&&nv&&nv!==curEl){returnToOrig();panelVid=null}
    curEl=nv;posCap();
    if(curEl&&curEl!==lastEl){lastEl=curEl;if(panel.classList.contains("open"))loadVid(curEl)}
  }

  function returnToOrig(){
    if(!panelVid)return;
    if(panelVid._origParent){panelVid._origParent.insertBefore(panelVid,panelVid._origNext);panelVid._origParent=null;panelVid=null}
  }

  function sync(){
    let v=vid();if(!v)return;
    let d=isFinite(v.duration)?v.duration:0,c=v.currentTime||0;
    $(".is-tc").textContent=fmt(c);$(".is-tt").textContent=fmt(d);$(".is-trow").textContent=fmt(c)+" / "+fmt(d);
    let bar=$(".is-bar");if(d){bar.max=d;bar.value=c}
  }

  function playH(){$(".is-pb").innerHTML=I.pau}
  function pauseH(){$(".is-pb").innerHTML=I.pla}
  function endH(){$(".is-pb").innerHTML=I.pla;sync()}

  function attachListeners(v){
    v.removeEventListener("loadedmetadata",sync);
    v.removeEventListener("timeupdate",sync);
    v.removeEventListener("play",playH);
    v.removeEventListener("pause",pauseH);
    v.removeEventListener("ended",endH);
    v.addEventListener("loadedmetadata",sync);
    v.addEventListener("timeupdate",sync);
    v.addEventListener("play",playH);
    v.addEventListener("pause",pauseH);
    v.addEventListener("ended",endH);
  }

  async function loadVid(el){
    let stage=$(".is-st"),info=$(".is-nf"),ctrl=$(".is-ctrl"),trow=$(".is-trow");
    if(!el){stage.style.display="none";ctrl.style.display="none";trow.style.display="none";info.style.display="flex";info.textContent="Role ate um reel.";curUrl="";resetT();return}
    info.style.display="none";stage.style.display="flex";ctrl.style.display="flex";trow.style.display="block";

    if(panelVid&&panelVid!==el){returnToOrig()}

    curUrl=getPerfUrl();

    panelVid=el;
    el._origParent=el.parentNode;
    el._origNext=el.nextSibling;
    el.style.position="relative";el.style.width="100%";el.style.height="100%";el.style.objectFit="contain";
    stage.appendChild(el);
    attachListeners(el);

    try{el.play().catch(()=>{})}catch(e){}
    $(".is-pb").innerHTML=I.pau;
  }

  function resetT(){$(".is-tc").textContent="0:00";$(".is-tt").textContent="0:00";$(".is-trow").textContent="0:00 / 0:00";let b=$(".is-bar");b.value=0;b.max=0}

  function openP(){panel.classList.add("open");loadVid(curEl||null)}
  function closeP(){panel.classList.remove("open");returnToOrig()}
  function toggleP(){panel.classList.contains("open")?closeP():openP()}
  function toast(m){if(!toastEl)return;toastEl.textContent=m;toastEl.classList.add("show");clearTimeout(toastT);toastT=setTimeout(()=>toastEl.classList.remove("show"),2600)}

  const I={
    dl:'<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    dlB:'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    pla:'<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
    pau:'<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
    x:'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    ref:'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    br:'<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm4.2 8.5l-5.5 3.2c-.3.2-.7 0-.7-.4V7.2c0-.4.4-.6.7-.4l5.5 3.2c.3.2.3.7 0 .9z"/></svg>'
  };

  const CSS=`
    :host{all:initial}*{box-sizing:border-box;margin:0;padding:0}
    .is-cap{position:fixed;z-index:2147483002;width:34px;height:34px;border:none;border-radius:9px;cursor:pointer;display:none;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#e1306c,#f77737);box-shadow:0 3px 12px rgba(0,0,0,.4);transition:transform .1s}
    .is-cap:hover{transform:scale(1.1)}
    .is-fab{position:fixed;right:16px;bottom:16px;z-index:2147483000;width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);box-shadow:0 4px 16px rgba(220,39,67,.4);transition:transform .15s,box-shadow .15s}
    .is-fab:hover{transform:translateY(-2px) scale(1.06);box-shadow:0 8px 24px rgba(220,39,67,.5)}
    .is-p{position:fixed;top:0;right:0;height:100vh;width:300px;max-width:calc(100vw - 40px);z-index:2147483001;display:flex;flex-direction:column;background:rgba(18,18,24,.96);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);color:#e7e9ee;border:1px solid rgba(255,255,255,.08);border-radius:16px;font:12px/1.4 system-ui,sans-serif;transform:translateX(120%);transition:transform .3s cubic-bezier(.4,0,.2,1);box-shadow:0 20px 60px rgba(0,0,0,.6);user-select:none;overflow:hidden}
    .is-p.open{transform:translateX(0)}
    .is-hd{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.06);cursor:grab;flex:0 0 auto}
    .is-hd:active{cursor:grabbing}
    .is-lg{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;color:#fff}
    .is-lg svg{color:#e1306c}
    .is-vr{font-size:9px;font-weight:600;color:#555;background:rgba(255,255,255,.06);padding:1px 5px;border-radius:4px}
    .is-hd button{background:none;border:none;color:#666;cursor:pointer;display:flex;padding:4px;border-radius:6px;transition:all .1s}
    .is-hd button:hover{background:rgba(255,255,255,.08);color:#fff}
    .is-st{position:relative;flex:1;min-height:0;background:#000;display:flex;align-items:center;justify-content:center;cursor:pointer;overflow:hidden}
    .is-vid{width:100%;max-height:100%;outline:none;display:block;object-fit:contain}
    .is-tm{position:absolute;top:8px;left:8px;display:flex;align-items:baseline;gap:4px;padding:4px 8px;border-radius:6px;background:rgba(0,0,0,.6);backdrop-filter:blur(4px);color:#fff;font-variant-numeric:tabular-nums}
    .is-tc{font-size:18px;font-weight:800}
    .is-ts{color:#777;font-size:12px}
    .is-tt{font-size:12px;color:#999}
    .is-nf{display:none;align-items:center;justify-content:center;flex:1;padding:20px 14px;text-align:center;color:#555;font-size:11.5px;line-height:1.6}
    .is-ctrl{display:flex;align-items:center;gap:8px;padding:8px 12px 3px;flex:0 0 auto}
    .is-pb{width:30px;height:30px;flex:0 0 auto;border:none;border-radius:50%;background:#fff;color:#111;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform .1s}
    .is-pb:hover{transform:scale(1.08)}
    .is-bar{flex:1;accent-color:#e1306c;cursor:pointer;height:3px}
    .is-sp{flex:0 0 auto;background:rgba(255,255,255,.06);color:#ccc;border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:3px 5px;font:600 10.5px system-ui;cursor:pointer}
    .is-trow{padding:0 12px 6px;color:#555;font-size:10.5px;font-variant-numeric:tabular-nums;flex:0 0 auto}
    .is-ft{display:flex;align-items:center;gap:6px;padding:10px 12px;border-top:1px solid rgba(255,255,255,.06);flex:0 0 auto}
    .is-dl{flex:1;display:inline-flex;align-items:center;justify-content:center;gap:5px;border:none;cursor:pointer;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);color:#fff;padding:9px 12px;border-radius:10px;font:700 12px system-ui;transition:filter .12s,transform .08s;box-shadow:0 2px 12px rgba(220,39,67,.3)}
    .is-dl:hover{filter:brightness(1.15)}.is-dl:active{transform:scale(.97)}
    .is-rf{width:36px;height:36px;border:none;border-radius:9px;background:rgba(255,255,255,.06);color:#999;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .1s}
    .is-rf:hover{background:rgba(255,255,255,.1);color:#fff}
    .is-to{position:fixed;left:50%;bottom:24px;z-index:2147483003;transform:translateX(-50%);background:rgba(18,18,24,.95);backdrop-filter:blur(12px);color:#fff;padding:8px 16px;border-radius:10px;font:600 12px system-ui;box-shadow:0 8px 24px rgba(0,0,0,.5);opacity:0;visibility:hidden;transition:all .2s;pointer-events:none;white-space:nowrap}
    .is-to.show{opacity:1;visibility:visible;transform:translateX(-50%) translateY(-3px)}
  `;

  function init(){
    if(shadow)return;
    let h=document.createElement("div");h.id="is-root";
    shadow=h.attachShadow({mode:"open"});
    shadow.innerHTML=`<style>${CSS}</style><button class="is-cap">${I.dl}</button><button class="is-fab">${I.dlB}</button><div class="is-p"><div class="is-hd"><span class="is-lg">${I.br} InstaSave <span class="is-vr">v2</span></span></span><button class="is-x">${I.x}</button></div><div class="is-st"></div><div class="is-nf">Role ate um reel.</div><div class="is-ctrl"><button class="is-pb">${I.pla}</button><input class="is-bar" type="range" min="0" max="0" value="0" step="0.1"/><select class="is-sp"><option value="0.5">0.5x</option><option value="0.75">0.75x</option><option value="1" selected>1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option></select></div><div class="is-trow">0:00 / 0:00</div><div class="is-ft"><button class="is-dl">${I.dl} Baixar</button><button class="is-rf">${I.ref}</button></div></div></div><div class="is-to"></div>`;
    document.documentElement.appendChild(h);
    panel=$(".is-p");
    let pb=$(".is-pb"),bar=$(".is-bar"),tr=$(".is-trow"),sp=$(".is-sp");
    toastEl=$(".is-to");
    $(".is-fab").addEventListener("click",toggleP);
    $(".is-cap").addEventListener("click",openP);
    $(".is-x").addEventListener("click",closeP);
    pb.addEventListener("click",() => { let v=vid();if(v) v.paused ? v.play().catch(() => {}) : v.pause(); });
    bar.addEventListener("input", () => { let v=vid(); if (v && isFinite(v.duration)) v.currentTime = + bar.value; });
    sp.addEventListener("change", () => { let v=vid(); if (v) v.playbackRate = + sp.value; });
    $(".is-dl").addEventListener("click", () => dl(curUrl));
    $(".is-rf").addEventListener("click", () => loadVid(curEl || null));
    $(".is-st").addEventListener("click", () => { let v=vid(); if (v) v.paused ? v.play().catch(() => {}) : v.pause(); });

    // DRAG
    let hd=$(".is-hd"),drag=false,sx,sy,sl,st;
    hd.addEventListener("mousedown",e=>{drag=true;sx=e.clientX;sy=e.clientY;let r=panel.getBoundingClientRect();sl=r.left;st=r.top;panel.style.transition="none";panel.style.right="auto";panel.style.left=sl+"px";panel.style.top=st+"px";e.preventDefault()});
    document.addEventListener("mousemove",e=>{if(!drag)return;panel.style.left=(sl+e.clientX-sx)+"px";panel.style.top=(st+e.clientY-sy)+"px"});
    document.addEventListener("mouseup",()=>{if(drag){drag=false;panel.style.transition=""}});
  }

  chrome.runtime.onMessage.addListener(m=>{if(!m)return;if(m.type==="OPEN_PANEL"){if(!shadow)init();openP();tick()}if(m.type==="FORCE_SCAN"){if(!shadow)init();tick();openP()}});

  function start(){if(!document.body){requestAnimationFrame(start);return}init();tick();document.addEventListener("keydown",e=>{if(e.key==="Escape"&&panel.classList.contains("open"))closeP()});window.addEventListener("scroll",throttle(()=>{tick();posCap()},120),{passive:true});setInterval(tick,1200);new MutationObserver(debounce(tick,600)).observe(document.body,{childList:true,subtree:true})}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start();
})();
'@
[System.IO.File]::WriteAllText("C:\Users\jairt\Downloads\instagram-downloader\content.js", $f, [System.Text.UTF8Encoding]::new($false))
Write-Host "OK" -ForegroundColor Green