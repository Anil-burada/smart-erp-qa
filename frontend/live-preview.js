/* SMART_ERP_PREVIEW_NO_POPUP_V2: authorization injected by authenticated Caddy gateway */
/* Smart ERP QA remote-view preview — screenshots only, no browser control. */
(() => {
  'use strict';
  const style = document.createElement('style');
  style.textContent = `
    #liveqa-toggle{position:fixed;right:18px;bottom:18px;z-index:900;border:1px solid #91b4df;background:#102e59;color:#fff;border-radius:40px;padding:12px 18px;font:600 14px Arial,sans-serif;box-shadow:0 6px 20px #001a3b55;cursor:pointer}
    #liveqa-panel{position:fixed;right:18px;bottom:77px;width:min(820px,calc(100vw - 36px));height:min(670px,calc(100vh - 110px));z-index:901;background:#fff;color:#11243d;border:1px solid #a4b6ce;border-radius:14px;box-shadow:0 18px 55px #00193466;display:none;overflow:hidden;flex-direction:column;font:14px Arial,sans-serif}
    #liveqa-panel.open{display:flex}#liveqa-header{background:#102e59;color:#fff;padding:13px 16px;display:flex;align-items:center;justify-content:space-between;gap:10px}#liveqa-header button{background:#fff;color:#123055;border:0;border-radius:6px;padding:7px 13px;cursor:pointer}#liveqa-status{padding:10px 16px;background:#eaf1fb;color:#224264;font-size:12px}
    #liveqa-stage{flex:1;background:#0b172a;display:flex;align-items:center;justify-content:center;overflow:auto;position:relative}#liveqa-image{display:none;width:100%;height:100%;object-fit:contain}#liveqa-empty{padding:20px;text-align:center;color:#d0dbea;line-height:1.6;max-width:380px}#liveqa-footer{padding:9px 16px;font-size:11px;line-height:1.4;color:#4e637a;background:#f5f8fc}
    @media (max-width:600px){#liveqa-toggle{padding:10px 13px;font-size:12px;right:10px;bottom:10px}#liveqa-panel{right:8px;bottom:58px;width:calc(100vw - 16px);height:70vh}}
  `;
  document.head.appendChild(style);
  const button = document.createElement('button');
  button.id = 'liveqa-toggle'; button.type = 'button';
  button.textContent = '◉ Live ERP Preview'; button.setAttribute('aria-expanded','false');
  const panel = document.createElement('section'); panel.id='liveqa-panel';
  panel.setAttribute('aria-label','Live ERP automation screenshot preview');
  panel.innerHTML = `<div id="liveqa-header"><strong>Live ERP Browser Preview · View only</strong><button type="button" id="liveqa-close">Close</button></div><div id="liveqa-status" role="status">Preview not started</div><div id="liveqa-stage"><div id="liveqa-empty">Click Run Automation in Smart ERP QA. The latest masked screenshots will appear here while the Playwright script is running on your host laptop.</div><img id="liveqa-image" alt="Masked screenshot of the ERP browser currently being automated"></div><div id="liveqa-footer">Updates approximately every 1.5–3 seconds when Playwright is interacting with the ERP. Read-only screenshots; this is not remote browser control. Show only to authorized testers. Sensitive information outside input fields may be visible.</div>`;
  document.body.append(button,panel);
  const status=panel.querySelector('#liveqa-status'), img=panel.querySelector('#liveqa-image'), empty=panel.querySelector('#liveqa-empty');
  let currentId='',lastFrame=0, timer=null, pending=false, objectUrl='';
  function forgetImage(){if(objectUrl){URL.revokeObjectURL(objectUrl);objectUrl='';}img.removeAttribute('src');}
  function close(){panel.classList.remove('open');button.setAttribute('aria-expanded','false');forgetImage();img.style.display='none';empty.style.display='block';if(timer)clearInterval(timer);timer=null;}
  async function refresh(){
    if(pending || !panel.classList.contains('open'))return;
    pending=true;
    try{
      const response=await fetch('/api/live-preview/status',{cache:'no-store',credentials:'same-origin'});
      if(response.status===401){throw new Error('Preview authorization denied. Check the protected Caddy gateway.');}
      if(!response.ok)throw new Error('Preview status is not accessible');
      const info=await response.json();
      if(!info.active){currentId='';lastFrame=0;status.textContent='No active automation run';img.style.display='none';empty.style.display='block';empty.textContent='Run Automation from this dashboard to display live ERP screenshots.';return;}
      if(info.run_id!==currentId){currentId=info.run_id;lastFrame=0;img.style.display='none';empty.style.display='block';}
      if(!info.available){status.textContent='Automation running · waiting for first Playwright frame';return;}
      status.textContent='RUNNING · latest frame captured '+(info.updated_at||'')+' · Screenshot preview';
      if(info.frame_version!==lastFrame){
        lastFrame=info.frame_version;
        // Route only accepts the active validated run ID; no arbitrary path.
        if(!/^[a-f0-9]{32}$/.test(currentId))return;
        const jpg=await fetch('/api/live-preview/frame/'+currentId+'?v='+encodeURIComponent(String(lastFrame)),{cache:'no-store',credentials:'same-origin'});
        if(!jpg.ok)throw new Error('Frame unavailable');
        forgetImage();objectUrl=URL.createObjectURL(await jpg.blob());
        img.src=objectUrl;img.style.display='block';empty.style.display='none';
      }
    }catch(err){status.textContent=err.message||'Preview unavailable. Check server and gateway.';}
    finally{pending=false;}
  }
  button.addEventListener('click',()=>{if(panel.classList.contains('open')){close();return;}panel.classList.add('open');button.setAttribute('aria-expanded','true');refresh();timer=setInterval(refresh,1700);});
  panel.querySelector('#liveqa-close').addEventListener('click',close);
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&panel.classList.contains('open'))close();});
})();
