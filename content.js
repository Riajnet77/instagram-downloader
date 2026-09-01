(() => {
  "use strict";
  if (window.__IS_LOADED__) return;
  window.__IS_LOADED__ = true;

  let shadow=null,panel=null,curEl=null,lastEl=null,panelVid=null,curUrl="",toastEl=null,toastT=null;
  let photos=[],photoIdx=0,mode="reel",isFs=false;
  let zm={s:1,x:0,y:0,drag:false,sx:0,sy:0};
  const $=s=>shadow.querySelector(s);
  const delay=ms=>new Promise(r=>setTimeout(r,ms));
  function debounce(f,m){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),m)}}
  function throttle(f,m){let l=0;return(...a)=>{let n=Date.now();if(n-l>=m){l=n;f(...a)}}}
  function fmt(s){if(!isFinite(s)||s<0)s=0;let sec=Math.floor(s),m=Math.floor(sec/60);return m+":"+String(sec%60).padStart(2,"0")}
  function fmtF(s){if(!isFinite(s)||s<0)return"--:--";let sec=Math.floor(s),h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),ss=sec%60;return h>0?h+":"+String(m).padStart(2,"0")+":"+String(ss).padStart(2,"0"):m+":"+String(ss).padStart(2,"0")}

  function getPerfUrl(){try{let e=performance.getEntriesByType("resource"),mp=[];for(let i=0;i<e.length;i++)if(/\.mp4(\?|$)/i.test(e[i].name))mp.push(e[i]);return mp.length?mp[mp.length-1].name:""}catch(e){return""}}
  function findVid(){let vs=document.querySelectorAll("video"),vh=window.innerHeight,best=null,bs=-1;vs.forEach(v=>{if(v.closest("#is-root"))return;let r=v.getBoundingClientRect();if(r.width<40||r.height<40)return;let vis=Math.min(r.bottom,vh)-Math.max(r.top,0);if(vis<=0)return;let cd=Math.abs(r.top+r.height/2-vh/2),sc=vis-cd;if(!v.paused&&!v.ended)sc+=vh*2;if(sc>bs){bs=sc;best=v}});return best}

  // Esconde os controles do Instagram ao redor do vídeo
  function hideIgOverlay(el){
    if(!el.parentNode)return;el._hSibs=[];
    Array.from(el.parentNode.children).forEach(c=>{if(c!==el){el._hSibs.push({e:c,o:c.style.visibility});c.style.visibility="hidden"}});
  }
  function restoreIgOverlay(el){
    if(!el._hSibs)return;el._hSibs.forEach(s=>{s.e.style.visibility=s.o});el._hSibs=null;
  }

  function returnToOrig(){
    if(!panelVid)return;
    restoreIgOverlay(panelVid);
    if(panelVid._origParent){panelVid._origParent.insertBefore(panelVid,panelVid._origNext);panelVid.style.cssText="";panelVid._origParent=null}
    else{panelVid.pause();panelVid.remove()}
    panelVid=null;
  }

  function posCap(){let b=$(".is-cap");if(!b||!curEl||panel.classList.contains("open")){if(b)b.style.display="none";return}let r=curEl.getBoundingClientRect();if(r.width<40||r.height<40){b.style.display="none";return}b.style.display="flex";b.style.left=Math.max(8,r.right-38)+"px";b.style.top=Math.max(8,r.top+8)+"px"}

  function isPostUrl(){return/\/p\//i.test(location.pathname)}
  function isReelUrl(){return/\/reel\//i.test(location.pathname)}

  function scanPhotos(){
    photos=[];photoIdx=0;let seen=new Set(),cands=[];
    document.querySelectorAll("img").forEach(img=>{
      if(img.closest("#is-root"))return;
      let src=img.currentSrc||img.src;if(!src)return;
      if(!/cdninstagram\.com|fbcdn\.net/i.test(src))return;
      if(/\/emoji\//i.test(src))return;if(/\/s150x150\//i.test(src))return;if(/\/p150x150\//i.test(src))return;
      let r=img.getBoundingClientRect();if(r.width<100&&r.height<100)return;
      let key=src.split("?")[0];if(seen.has(key))return;seen.add(key);
      cands.push({type:"photo",url:src,thumb:src,area:r.width*r.height});
    });
    cands.sort((a,b)=>b.area-a.area);
    if(cands.length>3){let mx=cands[0].area;cands=cands.filter(c=>c.area>=mx*0.12)}
    if(cands.length>15)cands.length=15;
    photos=cands.map(c=>({type:c.type,url:c.url,thumb:c.thumb}));
    let vs=new Set();
    document.querySelectorAll("video").forEach(v=>{
      if(v.closest("#is-root"))return;
      let src=v.src||v.currentSrc;if(!src){let s=v.querySelector("source");if(s)src=s.src}if(!src)return;
      let key=src.split("?")[0];if(vs.has(key))return;vs.add(key);
      photos=photos.filter(p=>p.url.split("?")[0]!==key);
      photos.push({type:"video",url:src,thumb:""});
    });
  }

  async function scanWithRetry(){scanPhotos();if(photos.length===0){await delay(600);scanPhotos()}if(photos.length===0){await delay(1000);scanPhotos()}return photos.length>0}

  function resetZm(){zm={s:1,x:0,y:0,drag:false,sx:0,sy:0};let img=$(".is-st img");if(img)img.style.transform="";updateZmUI()}
  function applyZm(){let img=$(".is-st img");if(!img){updateZmUI();return}if(zm.s<=1){img.style.transform="";zm.x=0;zm.y=0}else{img.style.transform="translate("+zm.x+"px,"+zm.y+"px) scale("+zm.s+")";img.style.transformOrigin="center center"}updateZmUI()}
  function updateZmUI(){let l=$(".is-zl");if(l)l.textContent=Math.round(zm.s*100)+"%"}

  function initZoom(){
    let st=$(".is-st");
    st.addEventListener("wheel",e=>{if(!$(".is-st img")||(panelVid&&panelVid.tagName==="VIDEO"))return;e.preventDefault();zm.s=Math.max(0.5,Math.min(8,zm.s+(e.deltaY>0?-0.25:0.25)));if(zm.s<=1){zm.x=0;zm.y=0}applyZm()},{passive:false});
    st.addEventListener("dblclick",e=>{if(!$(".is-st img")||(panelVid&&panelVid.tagName==="VIDEO"))return;zm.s=zm.s>1?1:3;applyZm()});
    st.addEventListener("mousedown",e=>{if(zm.s<=1||e.target.closest(".is-nl,.is-nr,.is-tm"))return;e.preventDefault();zm.drag=true;zm.sx=e.clientX-zm.x;zm.sy=e.clientY-zm.y;let img=$(".is-st img");if(img)img.style.cursor="grabbing"});
    document.addEventListener("mousemove",e=>{if(!zm.drag)return;zm.x=e.clientX-zm.sx;zm.y=e.clientY-zm.sy;applyZm()});
    document.addEventListener("mouseup",()=>{if(!zm.drag)return;zm.drag=false;let img=$(".is-st img");if(img)img.style.cursor=zm.s>1?"grab":""});
    $(".is-zout").addEventListener("click",()=>{zm.s=Math.max(0.5,zm.s-0.5);if(zm.s<=1){zm.x=0;zm.y=0}applyZm()});
    $(".is-zin").addEventListener("click",()=>{zm.s=Math.min(8,zm.s+0.5);applyZm()});
    $(".is-zrst").addEventListener("click",()=>{resetZm();updateInfo()});
  }

  function showVCtrl(){$(".is-ctrl").style.display="flex";$(".is-trow").style.display="block";$(".is-tm").style.display="flex";$(".is-zrow").style.display="none"}
  function hideVCtrl(){$(".is-ctrl").style.display="none";$(".is-trow").style.display="none";$(".is-tm").style.display="none";$(".is-zrow").style.display="none"}
  function showZCtrl(){$(".is-zrow").style.display="flex"}
  function hideZCtrl(){$(".is-zrow").style.display="none"}
  function resetCtrl(){$(".is-bar").value=0;$(".is-bar").max=0;$(".is-tc").textContent="0:00";$(".is-tt").textContent="0:00";$(".is-trow").textContent="0:00 / 0:00";$(".is-pb").innerHTML=I.pla;$(".is-sp").value="1"}

  function tickCtrl(){
    let v=panelVid;
    if(v&&v.tagName==="VIDEO"&&isFinite(v.duration)){
      $(".is-tc").textContent=fmt(v.currentTime);$(".is-tt").textContent=fmt(v.duration);
      $(".is-bar").max=v.duration;$(".is-bar").value=v.currentTime;
      $(".is-trow").textContent=fmtF(v.currentTime)+" / "+fmtF(v.duration);
    }
    updateInfo();
  }

  function updateInfo(){
    let p=$(".is-pinfo");if(!p)return;
    let ic=mode==="post"&&photos.length>1?`<span class="is-ic">${photoIdx+1}/${photos.length}</span>`:"";
    if(panelVid&&panelVid.tagName==="VIDEO"){
      p.innerHTML=`<span class="is-it it-vd">Video</span><span>${panelVid.videoWidth||"??"}x${panelVid.videoHeight||"??"}</span><span>${isFinite(panelVid.duration)?fmtF(panelVid.duration):"--:--"}</span><span class="is-spd">${panelVid.playbackRate}x</span>${ic}`;
      p.style.display="flex";
    } else {
      let img=$(".is-st img");
      if(img&&img.naturalWidth>1){
        let zt=zm.s>1?`<span class="is-spd">${Math.round(zm.s*100)}%</span>`:"";
        p.innerHTML=`<span class="is-it it-ph">Foto</span><span>${img.naturalWidth}x${img.naturalHeight}</span>${zt}${ic}`;
        p.style.display="flex";
      } else p.style.display="none";
    }
  }

  function showEmpty(msg){$(".is-st").style.display="none";hideVCtrl();hideZCtrl();$(".is-strip").style.display="none";$(".is-pinfo").style.display="none";$(".is-da").style.display="none";$(".is-nf").style.display="flex";$(".is-nf").textContent=msg}

  function toggleFs(){isFs=!isFs;panel.classList.toggle("fs",isFs);$(".is-fsbtn").innerHTML=isFs?I.mn:I.mx}

  function loadVid(el){
    if(!el){showEmpty("Role ate um reel.");curUrl="";resetCtrl();return}
    let stage=$(".is-st"),info=$(".is-nf"),strip=$(".is-strip"),pinfo=$(".is-pinfo"),nl=$(".is-nl"),nr=$(".is-nr"),dlA=$(".is-da");
    info.style.display="none";strip.style.display="none";dlA.style.display="none";stage.style.display="flex";showVCtrl();resetCtrl();resetZm();
    if(panelVid&&panelVid!==el)returnToOrig();
    curUrl=getPerfUrl();

    // ESCONDER overlay do Instagram antes de mover
    hideIgOverlay(el);

    stage.querySelectorAll("img,video").forEach(e=>e.remove());
    panelVid=el;el._origParent=el.parentNode;el._origNext=el.nextSibling;
    let r=el.getBoundingClientRect();
    el.style.position="fixed";el.style.width=r.width+"px";el.style.height=r.height+"px";el.style.left=r.left+"px";el.style.top=r.top+"px";el.style.zIndex="2147483002";
    stage.appendChild(el);
    el.style.width="100%";el.style.height="100%";el.style.left="0";el.style.top="0";el.style.position="relative";el.style.objectFit="contain";
    el.addEventListener("play",()=>{$(".is-pb").innerHTML=I.pau});
    el.addEventListener("pause",()=>{$(".is-pb").innerHTML=I.pla});
    try{el.play().catch(()=>{})}catch(e){}
    $(".is-pb").innerHTML=I.pau;nl.style.display="none";nr.style.display="none";pinfo.style.display="flex";updateInfo();
  }

  function loadPhoto(idx){
    if(idx<0||idx>=photos.length)return;
    photoIdx=idx;let item=photos[idx];
    let stage=$(".is-st"),info=$(".is-nf"),strip=$(".is-strip"),pinfo=$(".is-pinfo"),nl=$(".is-nl"),nr=$(".is-nr"),dlA=$(".is-da");
    returnToOrig();resetZm();stage.querySelectorAll("img,video").forEach(e=>e.remove());
    resetCtrl();hideVCtrl();hideZCtrl();
    info.style.display="none";stage.style.display="flex";pinfo.style.display="flex";
    let isC=photos.length>1;
    if(item.type==="video"){
      let vid=document.createElement("video");vid.src=item.url;vid.playsInline=true;vid.preload="metadata";
      vid.style.cssText="width:100%;height:100%;object-fit:contain;outline:none;display:block";
      stage.appendChild(vid);panelVid=vid;showVCtrl();$(".is-sp").value="1";
      vid.addEventListener("loadedmetadata",()=>{$(".is-bar").max=vid.duration;$(".is-tt").textContent=fmtF(vid.duration);updateInfo()});
      vid.addEventListener("play",()=>{$(".is-pb").innerHTML=I.pau;updateInfo()});
      vid.addEventListener("pause",()=>{$(".is-pb").innerHTML=I.pla;updateInfo()});
      vid.play().catch(()=>{});$(".is-pb").innerHTML=I.pau;
    } else {
      let img=document.createElement("img");img.src=item.url;img.alt="";
      img.style.cssText="max-width:100%;max-height:100%;object-fit:contain;display:block;cursor:zoom-in";
      img.addEventListener("load",()=>{updateInfo();if(zm.s>1)applyZm()});
      stage.appendChild(img);panelVid=null;showZCtrl();
    }
    curUrl=item.url;
    nl.style.display=isC&&photoIdx>0?"flex":"none";nr.style.display=isC&&photoIdx<photos.length-1?"flex":"none";
    if(isC){
      strip.style.display="flex";
      strip.innerHTML=photos.map((m,i)=>{
        let bg=m.thumb?`background-image:url('${m.thumb}');background-size:cover;background-position:center`:"background:#222";
        let vi=m.type==="video"?'<span style="position:absolute;bottom:1px;right:1px;width:13px;height:13px;border-radius:50%;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;color:#fff;font-size:6px">&#9654;</span>':"";
        return`<div class="is-si${i===photoIdx?" act":""}" data-i="${i}" style="${bg}">${vi}</div>`;
      }).join("");
      strip.querySelectorAll(".is-si").forEach(el=>{el.addEventListener("click",()=>loadPhoto(parseInt(el.dataset.i)))});
      dlA.style.display="inline-flex";dlA.innerHTML=I.dl+" Todos ("+photos.length+")";
    } else {strip.style.display="none";dlA.style.display="none"}
    updateInfo();
  }

  async function openP(){
    panel.classList.add("open");
    if(isReelUrl()){mode="reel";let v=findVid();if(v){curEl=v;loadVid(v)}else showEmpty("Role ate um reel.")}
    else if(isPostUrl()){mode="post";let f=await scanWithRetry();if(f)loadPhoto(0);else showEmpty("Nenhuma midia. Clique em atualizar.")}
    else{scanPhotos();if(photos.length>0){mode="post";loadPhoto(0)}else{mode="reel";let v=findVid();if(v){curEl=v;loadVid(v)}else showEmpty("Navegue ate um post ou reel.")}}
  }
  function closeP(){panel.classList.remove("open");if(isFs)toggleFs();returnToOrig();resetZm()}
  function toggleP(){panel.classList.contains("open")?closeP():openP()}
  function toast(m){if(!toastEl)return;toastEl.textContent=m;toastEl.classList.add("show");clearTimeout(toastT);toastT=setTimeout(()=>toastEl.classList.remove("show"),2800)}

  async function dlCur(){
    if(!curUrl){toast("Sem URL");return}
    let isVid=mode==="reel"||(photos[photoIdx]&&photos[photoIdx].type==="video");
    let idx=mode==="post"?photoIdx:0;
    let fn="instagram/"+(isVid?"reel":"post")+"_"+Date.now()+(idx>0?"_"+(idx+1):"")+"."+(isVid?"mp4":"jpg");
    toast("Baixando...");
    try{let r=await chrome.runtime.sendMessage({type:"DOWNLOAD_MEDIA",url:curUrl,filename:fn});toast(r&&r.ok?"Download iniciado!":"Erro ao baixar")}catch(e){toast("Erro: "+e.message)}
  }
  async function dlAll(){
    if(photos.length<=1)return;toast("Baixando "+photos.length+"...");
    for(let i=0;i<photos.length;i++){let fn="instagram/post_"+Date.now()+"_"+(i+1)+"."+(photos[i].type==="video"?"mp4":"jpg");try{await chrome.runtime.sendMessage({type:"DOWNLOAD_MEDIA",url:photos[i].url,filename:fn})}catch(e){}if(i<photos.length-1)await delay(400)}
    toast(photos.length+" download(s)!");
  }

  function tick(){if(mode!=="reel")return;let nv=findVid();if(panelVid&&nv&&nv!==curEl){returnToOrig();panelVid=null}curEl=nv;posCap();if(curEl&&curEl!==lastEl){lastEl=curEl;if(panel.classList.contains("open"))loadVid(curEl)}}

  const I={
    dl:'<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    dlB:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    pla:'<svg viewBox="0 0 24 24" width="14" height="14" fill="#fff"><path d="M8 5v14l11-7z"/></svg>',
    pau:'<svg viewBox="0 0 24 24" width="14" height="14" fill="#fff"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
    x:'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#999" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    ref:'<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    br:'<svg viewBox="0 0 24 24" width="11" height="11" fill="#e1306c"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm4.2 8.5l-5.5 3.2c-.3.2-.7 0-.7-.4V7.2c0-.4.4-.6.7-.4l5.5 3.2c.3.2.3.7 0 .9z"/></svg>',
    left:'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    right:'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    mx:'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>',
    mn:'<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>'
  };

  // ═══ CSS ═══
  const CSS=`
    :host{all:initial}*{box-sizing:border-box;margin:0;padding:0}
    .is-cap{position:fixed;z-index:2147483002;width:30px;height:30px;border:none;border-radius:8px;cursor:pointer;display:none;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#e1306c,#f77737);box-shadow:0 2px 10px rgba(0,0,0,.4);transition:transform .1s}
    .is-cap:hover{transform:scale(1.1)}
    .is-fab{position:fixed;right:14px;bottom:14px;z-index:2147482999;width:42px;height:42px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);box-shadow:0 4px 16px rgba(220,39,67,.4);transition:transform .15s}
    .is-fab:hover{transform:scale(1.1)}

    .is-p{position:fixed;bottom:16px;right:16px;z-index:2147483001;width:360px;border-radius:18px;display:flex;flex-direction:column;background:rgb(12,12,16);border:1px solid rgba(255,255,255,.07);font:11px/1.3 system-ui,sans-serif;box-shadow:0 16px 56px rgba(0,0,0,.7),0 0 0 1px rgba(255,255,255,.03);user-select:none;overflow:hidden;opacity:0;visibility:hidden;transform:translateY(16px) scale(.97);transition:all .3s cubic-bezier(.4,0,.2,1)}
    .is-p.open{opacity:1;visibility:visible;transform:translateY(0) scale(1)}
    .is-p.fs{width:min(92vw,640px);bottom:12px;right:12px;border-radius:14px}

    .is-hd{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;border-bottom:1px solid rgba(255,255,255,.05);cursor:grab;flex:0 0 auto}
    .is-hd:active{cursor:grabbing}
    .is-lg{display:inline-flex;align-items:center;gap:5px;font-weight:700;font-size:11px;color:#fff}
    .is-lg svg{color:#e1306c}
    .is-vr{font-size:8px;font-weight:700;color:#444;background:rgba(255,255,255,.04);padding:1px 4px;border-radius:3px}
    .is-hd button{background:none;border:none;color:#555;cursor:pointer;display:flex;padding:3px;border-radius:5px;transition:all .1s}
    .is-hd button:hover{background:rgba(255,255,255,.08);color:#fff}

    .is-st{position:relative;height:420px;background:#000;display:flex;align-items:center;justify-content:center;cursor:pointer;overflow:hidden;flex:0 0 auto}
    .is-p.fs .is-st{height:min(65vh,540px)}
    .is-st video{width:100%;height:100%;outline:none;display:block;object-fit:contain}
    .is-st img{max-width:100%;max-height:100%;object-fit:contain;display:block}

    .is-nl,.is-nr{position:absolute;top:50%;transform:translateY(-50%);width:28px;height:28px;border-radius:50%;border:none;background:rgba(0,0,0,.6);color:#fff;cursor:pointer;display:none;align-items:center;justify-content:center;z-index:2;transition:background .15s}
    .is-nl{left:8px}.is-nr{right:8px}
    .is-nl:hover,.is-nr:hover{background:rgba(0,0,0,.85)}

    .is-strip{display:none;gap:4px;padding:6px 12px;overflow-x:auto;flex:0 0 auto;border-bottom:1px solid rgba(255,255,255,.05)}
    .is-si{width:36px;height:36px;border-radius:6px;flex-shrink:0;cursor:pointer;border:2px solid transparent;transition:border-color .15s;position:relative;background-size:cover;background-position:center}
    .is-si.act{border-color:#e1306c}.is-si:hover{border-color:rgba(255,255,255,.25)}

    .is-tm{display:none;align-items:baseline;gap:6px;padding:8px 16px;border-radius:10px;background:rgba(0,0,0,.7);position:absolute;top:10px;left:10px;z-index:2}
    .is-tc{font-size:32px;font-weight:900;color:#fff;line-height:1;letter-spacing:-1px}
    .is-ts{font-size:20px;color:#ff6b35;font-weight:800}
    .is-tt{font-size:20px;color:rgba(255,255,255,.5);font-weight:600}

    .is-nf{display:none;align-items:center;justify-content:center;height:420px;padding:20px;text-align:center;color:#444;font-size:11px;line-height:1.5;flex:0 0 auto}
    .is-p.fs .is-nf{height:min(65vh,540px)}

    .is-ctrl{display:none;align-items:center;gap:6px;padding:6px 12px 2px;flex:0 0 auto}
    .is-pb{width:28px;height:28px;flex:0 0 auto;border:none;border-radius:50%;background:#fff;color:#111;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:transform .1s;box-shadow:0 2px 8px rgba(0,0,0,.3)}
    .is-pb:hover{transform:scale(1.1)}
    .is-bar{flex:1;accent-color:#e1306c;cursor:pointer;height:4px;border-radius:100px}
    .is-sp{flex:0 0 auto;background:rgba(255,255,255,.05);color:#aaa;border:1px solid rgba(255,255,255,.08);border-radius:5px;padding:2px 4px;font:600 10px system-ui;cursor:pointer}
    .is-trow{display:none;padding:0 12px 5px;color:#999;font-size:10px;font-variant-numeric:tabular-nums;flex:0 0 auto;font-weight:500}

    .is-zrow{display:none;align-items:center;gap:5px;padding:6px 12px;flex:0 0 auto;border-top:1px solid rgba(255,255,255,.05)}
    .is-zout,.is-zin{width:26px;height:26px;border-radius:6px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:#bbb;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;transition:all .1s;flex-shrink:0}
    .is-zout:hover,.is-zin:hover{background:rgba(255,255,255,.1);color:#fff}
    .is-zl{flex:1;text-align:center;font-size:11px;font-weight:700;color:#888;font-variant-numeric:tabular-nums}
    .is-zrst{padding:3px 10px;border-radius:5px;border:1px solid rgba(255,255,255,.08);background:none;color:#666;font:600 9px system-ui;cursor:pointer;flex-shrink:0;transition:all .1s}
    .is-zrst:hover{background:rgba(255,255,255,.08);color:#fff}

    .is-pinfo{display:none;align-items:center;gap:6px;padding:6px 12px;border-top:1px solid rgba(255,255,255,.05);font-size:10px;color:#777;flex:0 0 auto;flex-wrap:wrap}
    .is-it{padding:2px 6px;border-radius:4px;font-weight:700;font-size:8.5px;text-transform:uppercase;letter-spacing:.4px}
    .it-ph{background:rgba(59,130,246,.18);color:#60a5fa}
    .it-vd{background:rgba(239,68,68,.18);color:#f87171}
    .is-spd{padding:2px 6px;border-radius:4px;background:rgba(255,107,53,.18);color:#ff6b35;font-weight:700;font-size:9px}
    .is-ic{margin-left:auto;color:#555;font-size:9px;font-weight:600}

    .is-ft{display:flex;align-items:center;gap:5px;padding:8px 12px;flex:0 0 auto}
    .is-dl{flex:1;display:inline-flex;align-items:center;justify-content:center;gap:5px;border:none;cursor:pointer;background:linear-gradient(135deg,#f09433,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888);color:#fff;padding:9px 10px;border-radius:9px;font:700 11px system-ui;transition:filter .12s,transform .08s;box-shadow:0 2px 10px rgba(220,39,67,.3)}
    .is-dl:hover{filter:brightness(1.15)}.is-dl:active{transform:scale(.97)}
    .is-da{padding:9px 10px;border-radius:9px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:#bbb;font:600 10px system-ui;cursor:pointer;transition:all .1s;white-space:nowrap;display:none;align-items:center;gap:4px}
    .is-da:hover{background:rgba(255,255,255,.1);color:#fff}
    .is-rf{width:32px;height:32px;border:none;border-radius:8px;background:rgba(255,255,255,.04);color:#666;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .1s;flex-shrink:0}
    .is-rf:hover{background:rgba(255,255,255,.1);color:#fff}
    .is-fsbtn{width:32px;height:32px;border:none;border-radius:8px;background:rgba(255,255,255,.04);color:#666;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .1s;flex-shrink:0}
    .is-fsbtn:hover{background:rgba(255,255,255,.1);color:#fff}

    .is-to{position:fixed;left:50%;bottom:20px;z-index:2147483003;transform:translateX(-50%);background:rgb(12,12,16);color:#fff;padding:7px 14px;border-radius:8px;font:600 11px system-ui;box-shadow:0 4px 16px rgba(0,0,0,.5);opacity:0;visibility:hidden;transition:all .2s;pointer-events:none;white-space:nowrap}
    .is-to.show{opacity:1;visibility:visible;transform:translateX(-50%) translateY(-2px)}
  `;

  function init(){
    if(shadow)return;
    let h=document.createElement("div");h.id="is-root";
    shadow=h.attachShadow({mode:"open"});
    shadow.innerHTML=`<style>${CSS}</style>
      <button class="is-cap">${I.dl}</button>
      <button class="is-fab">${I.dlB}</button>
      <div class="is-p">
        <div class="is-hd"><span class="is-lg">${I.br} InstaSave <span class="is-vr">v3</span></span><button class="is-x">${I.x}</button></div>
        <div class="is-st">
          <button class="is-nl">${I.left}</button><button class="is-nr">${I.right}</button>
          <div class="is-tm"><span class="is-tc">0:00</span><span class="is-ts"> / </span><span class="is-tt">0:00</span></div>
        </div>
        <div class="is-strip"></div>
        <div class="is-nf">Role ate um reel.</div>
        <div class="is-ctrl">
          <button class="is-pb">${I.pla}</button>
          <input class="is-bar" type="range" min="0" max="0" value="0" step="0.1"/>
          <select class="is-sp"><option value="0.5">0.5x</option><option value="0.75">0.75x</option><option value="1" selected>1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option></select>
        </div>
        <div class="is-trow">0:00 / 0:00</div>
        <div class="is-zrow">
          <button class="is-zout">&minus;</button>
          <span class="is-zl">100%</span>
          <button class="is-zin">+</button>
          <button class="is-zrst">Reset</button>
        </div>
        <div class="is-pinfo"></div>
        <div class="is-ft">
          <button class="is-dl">${I.dl} Baixar</button>
          <button class="is-da">${I.dl} Todos</button>
          <button class="is-rf">${I.ref}</button>
          <button class="is-fsbtn">${I.mx}</button>
        </div>
      </div>
      <div class="is-to"></div>`;
    document.documentElement.appendChild(h);
    panel=$(".is-p");toastEl=$(".is-to");

    $(".is-fab").addEventListener("click",toggleP);
    $(".is-cap").addEventListener("click",openP);
    $(".is-x").addEventListener("click",closeP);
    $(".is-pb").addEventListener("click",()=>{if(panelVid&&panelVid.tagName==="VIDEO")panelVid.paused?panelVid.play().catch(()=>{}):panelVid.pause()});
    $(".is-bar").addEventListener("input",()=>{if(panelVid&&panelVid.tagName==="VIDEO"&&isFinite(panelVid.duration))panelVid.currentTime=parseFloat($(".is-bar").value)});
    $(".is-sp").addEventListener("change",()=>{if(panelVid&&panelVid.tagName==="VIDEO"){panelVid.playbackRate=parseFloat($(".is-sp").value);updateInfo()}});
    $(".is-dl").addEventListener("click",dlCur);
    $(".is-da").addEventListener("click",dlAll);
    $(".is-fsbtn").addEventListener("click",toggleFs);
    $(".is-rf").addEventListener("click",async()=>{if(mode==="post"){let f=await scanWithRetry();if(f)loadPhoto(0);else toast("Nenhuma midia")}else{let v=findVid();if(v){curEl=v;loadVid(v)}else toast("Nenhum reel")}});
    $(".is-st").addEventListener("click",e=>{if(e.target.closest(".is-nl,.is-nr,.is-tm"))return;if(zm.s>1)return;if(panelVid&&panelVid.tagName==="VIDEO")panelVid.paused?panelVid.play().catch(()=>{}):panelVid.pause()});
    $(".is-nl").addEventListener("click",()=>{if(mode==="post"&&photoIdx>0)loadPhoto(photoIdx-1)});
    $(".is-nr").addEventListener("click",()=>{if(mode==="post"&&photoIdx<photos.length-1)loadPhoto(photoIdx+1)});

    initZoom();
    setInterval(tickCtrl,200);

    let drag=false,sx,sy,sl,st;
    $(".is-hd").addEventListener("mousedown",e=>{drag=true;sx=e.clientX;sy=e.clientY;let r=panel.getBoundingClientRect();sl=r.left;st=r.top;panel.style.transition="none";panel.style.bottom="auto";panel.style.right="auto";panel.style.left=sl+"px";panel.style.top=st+"px";e.preventDefault()});
    document.addEventListener("mousemove",e=>{if(!drag)return;panel.style.left=(sl+e.clientX-sx)+"px";panel.style.top=(st+e.clientY-sy)+"px"});
    document.addEventListener("mouseup",()=>{if(drag){drag=false;panel.style.transition=""}});
  }

  chrome.runtime.onMessage.addListener(m=>{
    if(!m)return;
    if(m.type==="OPEN_PANEL"){if(!shadow)init();openP()}
    if(m.type==="FORCE_SCAN"){if(!shadow)init();if(isPostUrl()){mode="post";scanWithRetry().then(f=>{if(f)loadPhoto(0);else toast("Nada")})}else{mode="reel";let v=findVid();if(v){curEl=v;loadVid(v)}else toast("Nada")}openP()}
  });

  function start(){
    if(!document.body){requestAnimationFrame(start);return}
    init();tick();
    document.addEventListener("keydown",e=>{if(e.key==="Escape"&&panel.classList.contains("open"))closeP();if(e.key==="f"&&!e.ctrlKey&&!e.metaKey&&panel.classList.contains("open"))toggleFs()});
    window.addEventListener("scroll",throttle(()=>{tick();posCap()},120),{passive:true});
    setInterval(tick,1200);
    new MutationObserver(debounce(tick,600)).observe(document.body,{childList:true,subtree:true});
    let lastH=location.href;
    new MutationObserver(debounce(()=>{
      if(location.href!==lastH){
        lastH=location.href;
        if(panel.classList.contains("open")){
          if(isReelUrl()){mode="reel";let v=findVid();if(v){curEl=v;loadVid(v)}}
          else if(isPostUrl()){mode="post";returnToOrig();scanWithRetry().then(f=>{if(f)loadPhoto(0);else showEmpty("Nenhuma midia.")})}
          else{mode="reel";let v=findVid();if(v){curEl=v;loadVid(v)}else showEmpty("Navegue ate um post ou reel.")}
        }
        posCap();
      }
    },500)).observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start();
})();