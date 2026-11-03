'use strict';
const { app, BrowserWindow, WebContentsView, ipcMain, dialog } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const SERVER = 'http://127.0.0.1:8766';
const CDP_PORT = Number(process.env.SMART_ERP_CDP_PORT || '9337');
const ROOT = path.resolve(__dirname, '..');
const DASH_PRELOAD = path.join(__dirname, 'preload.js');
if (!Number.isInteger(CDP_PORT) || CDP_PORT < 1024 || CDP_PORT > 65535) throw new Error('Invalid CDP port');
// Local CDP allows inspection of authenticated ERP content. Never expose it to a LAN.
app.commandLine.appendSwitch('remote-debugging-port', String(CDP_PORT));
app.commandLine.appendSwitch('remote-debugging-address', '127.0.0.1');
if (!app.requestSingleInstanceLock()) app.quit();
let win=null, erpView=null, barView=null, ownedServer=null, activeProject=null, backendSpawnError=null;
let currentPage='projects', opening=false;

async function api(apiPath, method='GET', body) {
  const response = await fetch(SERVER + apiPath, {
    method, headers: {'Content-Type': 'application/json'},
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    signal: AbortSignal.timeout(20000)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}
function pythonExecutable() {
  const envPython = process.env.SMART_ERP_PYTHON;
  if(envPython) return envPython;
  const file = process.platform==='win32' ? path.join(ROOT,'.venv','Scripts','python.exe') : path.join(ROOT,'.venv','bin','python');
  if(fs.existsSync(file)) return file;
  throw new Error('Project Python environment missing. Run Install-Desktop-Windows.ps1 in your existing Smart ERP project.');
}
const LOGDIR=path.join(ROOT, 'logs');
function lastLogLines() {
  const file=path.join(LOGDIR,'desktop_backend.stderr.log');
  try {return fs.readFileSync(file,'utf8').split(/\r?\n/).slice(-18).join('\n').slice(-1800);} catch (_) {return '';}
}
async function ensureServer() {
  // If an operator started the backend manually, reuse it without killing it.
  try {
    const health = await api('/api/health');
    if (!health.desktop_enabled) throw new Error('Port 8766 is already running a WEB-only server. Stop that server, then launch Desktop again.');
    console.log('Reusing healthy desktop FastAPI backend on 8766');
    return;
  } catch (error) {
    if (!String(error.message).includes('fetch failed')) throw error;
  }
  fs.mkdirSync(LOGDIR, {recursive:true});
  const out=fs.createWriteStream(path.join(LOGDIR,'desktop_backend.stdout.log'),{flags:'a'});
  const err=fs.createWriteStream(path.join(LOGDIR,'desktop_backend.stderr.log'),{flags:'a'});
  const marker=`\n=== Desktop backend startup ${new Date().toISOString()} ===\n`;
  out.write(marker);err.write(marker);
  backendSpawnError=null;
  ownedServer=spawn(pythonExecutable(), ['-u','run.py'], {
    cwd: ROOT, stdio: ['ignore','pipe','pipe'],
    env: {...process.env, SMART_ERP_DESKTOP:'1', PYTHONUNBUFFERED:'1'}, windowsHide:true
  });
  ownedServer.on('error', e=>{backendSpawnError=e;err.write(String(e)+'\n');});
  ownedServer.stdout.on('data', d=>{out.write(d);process.stdout.write(d);});
  ownedServer.stderr.on('data', d=>{err.write(d);process.stderr.write(d);});
  // Allow slower first-run antivirus scans; do not infer a crash from a pipe warning.
  const deadline=Date.now()+90000;
  while(Date.now()<deadline) {
    await new Promise(r=>setTimeout(r,400));
    if(backendSpawnError) break;
    if(ownedServer.exitCode!==null) break;
    try {
      const response=await api('/api/health');
      if(response.desktop_enabled) {
        console.log('FastAPI is healthy; dashboard can now open');
        return;
      }
      throw new Error('Port 8766 was occupied by a non-desktop server');
    } catch (e) {if(!String(e.message).includes('fetch failed')) throw e;}
  }
  const hint=lastLogLines();
  throw new Error('FastAPI did not become healthy on port 8766. Open logs\\desktop_backend.stderr.log and logs\\desktop_backend.stdout.log. '+
     (backendSpawnError ? String(backendSpawnError) : '') + (hint ? '\nRecent errors:\n'+hint : ''));
}
function layout() {
  if(!win || !erpView || !barView)return;
  const {width,height}=win.getContentBounds();
  const visible=currentPage==='projects';
  if(!visible){erpView.setVisible(false);barView.setVisible(false);return;}
  // Leave navigation sidebar usable and use nearly all remaining workspace.
  const x=230, top=76, margin=9;
  const w=Math.max(320,width-x-margin), h=Math.max(240,height-top-margin);
  barView.setBounds({x, y:top, width:w, height:48});
  erpView.setBounds({x, y:top+48, width:w, height:h-48});
  erpView.setVisible(true);barView.setVisible(true);
}
async function closeERP() {
  if(!erpView)return {open:false};
  // Detach CDP before destroying WebContentsView to avoid worker errors.
  try {await api('/api/browser/close','POST');}catch(error) {console.warn('Backend detach:',error.message);}
  const oldERP=erpView, oldBar=barView;
  erpView=null;barView=null;activeProject=null;
  win.contentView.removeChildView(oldERP);
  win.contentView.removeChildView(oldBar);
  oldERP.webContents.close();
  oldBar.webContents.close();
  win?.webContents.send('desktop:refresh');
  return {open:false};
}
function verifySender(event) {
  if(!win || ![win.webContents.id,barView?.webContents.id].includes(event.sender.id)) {
    throw new Error('Untrusted desktop IPC sender');
  }
}
function registerIPC() {
  ipcMain.handle('desktop:open-erp', async(event,id)=> {
    verifySender(event);
    if(opening)throw new Error('An ERP is already opening');
    opening=true;
    try {
      const projects=await api('/api/projects');
      const project=projects.find(p=>p.id===id);
      if(!project)throw new Error('ERP project not registered');
      if(project.browser!=='chromium')throw new Error('Desktop beta supports Chromium projects only');
      const url = new URL(project.url);
      if(!['http:','https:'].includes(url.protocol))throw new Error('Only HTTP(S) ERP sites are allowed');
      await closeERP();
      currentPage='projects';
      erpView=new WebContentsView({webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true, partition:`smart-erp-${id}`}});
      barView=new WebContentsView({webPreferences:{preload:DASH_PRELOAD,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}});
      // ERP code has no preload and no access to the desktop IPC bridge.
      erpView.webContents.setWindowOpenHandler(() => ({action:'allow', overrideBrowserWindowOptions:{webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}}}));
      win.contentView.addChildView(erpView);win.contentView.addChildView(barView);
      layout();
      await Promise.all([barView.webContents.loadFile(path.join(__dirname,'toolbar.html')), erpView.webContents.loadURL(url.toString())]);
      const attached = await api('/api/browser/electron/attach','POST',{project_id:id,cdp_port:CDP_PORT});
      activeProject=id;
      win.webContents.send('desktop:refresh');
      return attached;
    } catch(error){await closeERP();throw error;}
    finally {opening=false;}
  });
  ipcMain.handle('desktop:close-erp', async(event)=>{verifySender(event);return closeERP();});
  ipcMain.handle('desktop:set-page', async(event,page)=>{verifySender(event);currentPage=['projects','overview','workflows','browser','flows','approvals','register','guide'].includes(page)?page:'projects';layout();return {page:currentPage};});
  ipcMain.handle('desktop:teach', async(event)=>{verifySender(event);const result=await api('/api/recorder/start','POST');win.webContents.send('desktop:refresh');return result;});
  ipcMain.handle('desktop:navigate', async(event,page)=>{verifySender(event);if(!['projects','workflows'].includes(page))throw new Error('Unsupported destination');currentPage=page;layout();win.webContents.send('desktop:navigate',page);return {page};});
  ipcMain.handle('desktop:status', async(event)=>{verifySender(event);return {open:!!erpView,project_id:activeProject,page:currentPage};});
}
async function createMainWindow(){
  await ensureServer();
  win=new BrowserWindow({width:1550,height:940,minWidth:920,minHeight:650,title:'Smart ERP QA Desktop',backgroundColor:'#f1f8f3',show:false,webPreferences:{preload:DASH_PRELOAD,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}});
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith(SERVER+'/'))event.preventDefault();});
  win.on('resize',layout);
  win.on('closed',()=>{win=null;});
  await win.loadURL(SERVER+'/');
  win.show();
}
app.whenReady().then(async()=>{
  try {registerIPC();await createMainWindow();}
  catch(err){await dialog.showMessageBox({type:'error',title:'Smart ERP QA Desktop',message:String(err.message||err)});app.quit();}
});
app.on('activate',()=>{if(!win)createMainWindow().catch(console.error);});
app.on('before-quit',()=>{if(ownedServer && ownedServer.exitCode===null)ownedServer.kill();});
app.on('window-all-closed',()=>{app.quit();});
