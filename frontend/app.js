'use strict';

// Navy-and-white automation dashboard, now powered by a LOCAL FastAPI + Playwright server.
const NAMES={overview:'Dashboard',register:'Add ERP Application',projects:'ERP Applications',workflows:'Workflow Library',browser:'Live ERP Browser',approvals:'Approval Plans',flows:'Business Flows',suite:'Test Case Report',scripts:'Script Workspace',reports:'Test Reports',guide:'Setup Guide',ailab:'AI Test Lab'};
const state={page:'overview',projects:[],workflows:[],metrics:{},executions:[],session:{open:false},editId:null,filter:'',selected:null,draft:null,warnings:[],editing:false,editingLocators:false,locators:null,busy:false,recordName:'purchase_indent',loginConfig:null,loginProject:null,aiDiagnosis:null,negativeCandidates:null,negativeResult:null,pomTemplates:[],pomSelected:null,pomMapping:null,pomProjectId:null,pomTemplateDoc:null,pomPreview:null,linkedResult:null,stepReview:null,replayPreflight:null,batchPreflight:null,domInspector:null,preview:null,approvalPlans:[],approvalPlan:null,approvalPreview:null,approvalRun:null,aiIdeas:null,businessFlows:[],flowDoc:null,flowPreview:null,flowRun:null,flowProject:null,flowInputs:{},loginReady:null,loginWizardProject:null,loginWizardFields:null,loginWizardOptions:null,lastAutoRun:null,workflowManagerOpen:false,workflowManagerProject:'',embeddedBusy:false};
let toastTimer;
// Web dashboard recording notifications: track only the last safely captured
// action count. Never show input values or credentials in notifications.
let lastRecordingProject = null;
let lastRecordingStepCount = 0;

// Initialize embedded browser state BEFORE the first dashboard render.
let embeddedTimer=null,embeddedURL=null,embeddedPending=Promise.resolve(),embeddedFrameInFlight=false;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,method='GET',payload){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(payload!==undefined) opts.body=JSON.stringify(payload);
  const response=await fetch('/api'+path,opts);
  const data=await response.json().catch(()=>({detail:response.statusText}));
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function notify(message,isError=false){const node=$('toast');node.textContent=message;node.className='toast show'+(isError?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.className='toast',5200)}
// Native modal with actual Yes / No buttons. Cancel / Escape never removes data.
function confirmRemoveWorkflow(key){
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');
    dialog.className='workflow-remove-confirm';
    dialog.setAttribute('aria-labelledby','workflowRemoveTitle');
    dialog.innerHTML=`<h3 id="workflowRemoveTitle">Remove this saved workflow?</h3>
      <p class="workflow-remove-name"></p>
      <p>The workflow JSON will be archived for recovery. Your ERP project, other workflows and past execution reports stay unchanged.</p>
      <div class="workflow-remove-actions"><button type="button" class="btn btn-outline" data-remove-choice="no">No, Keep</button><button type="button" class="btn btn-danger" data-remove-choice="yes">Yes, Remove</button></div>`;
    dialog.querySelector('.workflow-remove-name').textContent=key;
    let settled=false;
    function finish(accepted){
      if(settled)return;
      settled=true;
      dialog.close();
      dialog.remove();
      resolve(accepted);
    }
    dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false)});
    dialog.querySelector('[data-remove-choice="no"]').addEventListener('click',()=>finish(false));
    dialog.querySelector('[data-remove-choice="yes"]').addEventListener('click',()=>finish(true));
    document.body.appendChild(dialog);
    dialog.showModal();
    dialog.querySelector('[data-remove-choice="no"]').focus();
  });
}

function recordingStatusText(session=state.session){
  if(!session?.open)return 'NO ERP SESSION';
  if(session.paused)return `RECORDING PAUSED · ${session.step_count||0} steps`;
  if(session.recording)return `● RECORDING ON · ${session.step_count||0} steps`;
  return 'RECORDING OFF';
}
function updateRecordingIndicators(){
  const text=recordingStatusText();
  for(const id of ['globalRecordingStatus','embeddedRecordingStatus']){
    const node=$(id);
    if(node){node.textContent=text;node.classList.toggle('active',!!state.session.recording);node.classList.toggle('paused',!!state.session.paused)}
  }
  document.querySelectorAll('[data-action="embedded-teach"]').forEach(b=>b.disabled=!!state.session.recording);
}
function notifyNewCapturedSteps(oldSession,newSession,preview){
  const key=newSession?.project_id||null;
  if(!newSession?.recording){lastRecordingProject=key;lastRecordingStepCount=Number(newSession?.step_count)||0;return;}
  const next=Number(newSession.step_count)||0;
  // A new recording has a fresh step counter, or project changes.
  if(key!==lastRecordingProject||next<lastRecordingStepCount){lastRecordingProject=key;lastRecordingStepCount=next;return;}
  if(next>lastRecordingStepCount){
    const recent=(preview?.steps||[]).at(-1);
    const action=String(recent?.action||'interaction').replace(/_/g,' ');
    const label=String(recent?.target_text||'ERP control').slice(0,65);
    notify(`● Recording ON · Captured step ${next}: ${action} — ${label}`);
  }
  lastRecordingStepCount=next;
}
function intro(kicker,title,summary){return `<div class="page-intro"><div class="eyebrow">${kicker}</div><h1 class="page-heading">${title}</h1><p class="muted">${summary}</p></div>`}
function go(page,editId=null){if(!NAMES[page])return;state.page=page;state.editId=editId;document.querySelectorAll('.nav-item').forEach(b=>{b.classList.toggle('active',b.dataset.page===page)});$('breadcrumb').textContent=NAMES[page];$('sidebar').classList.remove('open');$('sidebarOverlay').hidden=true;render();if(page==='suite')void dashboardLoad();if(['scripts','reports'].includes(page))void wsLoad();if(page==='overview')void dashboardLoad()}
function pOptions(selected){return state.projects.map(p=>`<option value="${esc(p.id)}" ${p.id===selected?'selected':''}>${esc(p.name)} (${esc(p.environment)})</option>`).join('')}
function activeProject(){return state.projects.find(x=>x.id===state.session.project_id)}
function overview(){const m=state.metrics;return `
<section class="hero"><div><div class="hero-kicker">SMART AUTOMATION WORKSPACE · LOCAL BACKEND</div><h1>One dashboard. Every ERP project.</h1><p>Register an ERP, open its login page, demonstrate supported actions, review and replay a captured workflow with Playwright.</p><div class="hero-cta"><button class="btn btn-white" data-go="register">+ Register ERP</button> <button class="btn btn-white" data-go="browser">Open Browser</button></div></div><div class="hero-orbit">QA</div></section>
<section class="metrics"><div class="metric"><span class="metric-dot">P</span><div class="metric-label">Registered ERPs</div><div class="metric-value">${m.projects||0}</div><div class="metric-foot">SQLite project registry</div></div><div class="metric"><span class="metric-dot">W</span><div class="metric-label">Saved Workflows</div><div class="metric-value">${m.workflows||0}</div><div class="metric-foot">Project-specific JSON</div></div><div class="metric"><span class="metric-dot">E</span><div class="metric-label">Executions</div><div class="metric-value">${m.executions||0}</div><div class="metric-foot">Real replay history</div></div><div class="metric"><span class="metric-dot">!</span><div class="metric-label">Failed Runs</div><div class="metric-value">${m.failed||0}</div><div class="metric-foot">Stopped on failing step</div></div></section>
<div class="section-title-row"><h2 class="subheading">How to automate</h2></div>
<section class="grid-two"><div class="panel"><div class="panel-head"><h3>Teach → Review → Replay</h3><span class="tag">Connected backend</span></div><ol class="steps">
${[['01','Register a test ERP','Provide its URL, project ID and browser.'],['02','Open ERP; login manually or configure selectors','The login configuration stores selectors, never passwords.'],['03','Demonstrate once; auto-capture runs','Start Teaching ERP after manual login to capture actions and locators.'],['04','Stop, review and approve','Inspect locator candidates, values and captured steps.'],['05','Run a reviewed workflow','Replay recorded actions and receive an execution report.']].map(x=>`<li class="step"><span class="step-index">${x[0]}</span><div><strong>${x[1]}</strong><small>${x[2]}</small></div></li>`).join('')}</ol></div>
<div class="panel"><div class="panel-head"><h3>Browser status</h3><span class="tag">${state.session.open?'OPEN':'CLOSED'}</span></div><p>${state.session.open?'ERP project: <strong>'+esc(state.session.project_id)+'</strong>':'No Playwright browser is open.'}</p><p class="muted">${esc(state.session.url||'')}</p><div class="callout"><strong>Limitations:</strong> Workflow replay currently validates locator uniqueness and action completion. Multi-role approval plans are available in Approval Plans. Built-in replay validates explicit assertions, but does not infer ERP business correctness. Local AI can suggest diagnoses after a failed run.</div><div class="form-actions"><button class="btn btn-primary" data-go="browser">Manage Browser</button><button class="btn btn-outline" data-go="workflows">Workflows</button></div></div></section>
${recentRuns()}`}
function registerPage(){const p=state.projects.find(x=>x.id===state.editId);return `${intro('PROJECT REGISTRY',p?'Edit ERP project':'Register an ERP application','Project URLs and configurations are stored separately in SQLite; ERP credentials are never requested by this dashboard.')}
<section class="grid-two"><div class="panel"><form id="projectForm" method="post"><div class="form-grid">
<div class="field"><label>Project ID *</label><input name="id" required value="${esc(p?.id||'')}" ${p?'readonly':''} placeholder="leocem"></div>
<div class="field"><label>Project name *</label><input name="name" required value="${esc(p?.name||'')}" placeholder="Leocem ERP"></div>
<div class="field"><label>Application name *</label><input name="appName" required value="${esc(p?.appName||'')}" placeholder="Procurement ERP"></div>
<div class="field"><label>Environment *</label><select name="environment"><option value="test" ${p?.environment==='test'?'selected':''}>Test</option><option value="staging" ${p?.environment==='staging'?'selected':''}>Staging</option><option value="production" ${p?.environment==='production'?'selected':''}>Production (automation disabled)</option></select></div>
<div class="field full"><label>ERP URL *</label><input name="url" type="url" required value="${esc(p?.url||'')}" placeholder="https://example.com/erp"></div>
<div class="field"><label>Browser</label><select name="browser">${['chromium','firefox','webkit'].map(x=>`<option value="${x}" ${p?.browser===x?'selected':''}>${x}</option>`).join('')}</select></div>
<div class="field full"><label>Description</label><textarea name="description" maxlength="500">${esc(p?.description||'')}</textarea></div></div>
<div class="form-actions"><button type="submit" class="btn btn-primary">${p?'Save Project':'Register ERP'}</button><button type="button" class="btn btn-outline" data-go="projects">Cancel</button></div></form></div>
<aside class="panel"><h3>Configuration isolation</h3><div class="callout">Each project has a unique URL and ID. Workflow specs are saved in <code>workflows/&lt;project&gt;/</code>.</div><p class="muted">For a safe smoke test, register the built-in mock ERP at <code>http://127.0.0.1:8766/mock/</code>.</p><div class="callout warn"><strong>Security:</strong> Only use authorized test or staging ERP data. Never enter actual account passwords in this form.</div></aside></section>`}
function projectCard(p){return `<div class="project-item"><div class="project-main"><div class="project-icon">ERP</div><div><h3>${esc(p.name)}</h3><div class="project-url">${esc(p.url)}</div><div class="project-details"><span class="tag">${esc(p.id)}</span><span class="tag">${esc(p.environment)}</span><span>${esc(p.browser)}</span></div></div></div><div class="project-actions"><button class="btn btn-primary btn-small" data-action="open-project" data-id="${esc(p.id)}">Open ERP</button><button class="btn btn-outline btn-small" data-action="edit" data-id="${esc(p.id)}">Edit</button><button class="btn btn-danger btn-small" data-action="delete" data-id="${esc(p.id)}">Delete</button></div></div>`}
function loginWizardPanel(){
  const active=state.session.open && state.session.project_id;
  const matching=active && state.loginWizardProject===state.session.project_id;
  const captured=matching && !!state.loginWizardFields;
  const options=matching ? state.loginWizardOptions : null;
  const choices=options?.candidates||[];
  return `<div class="panel top-note login-setup-wizard" id="guidedLoginSetup">
    <div class="panel-head"><h3>Guided Automatic Login Setup</h3><span class="tag">Selectors only · No passwords stored</span></div>
    <p class="muted">Do this once per ERP. Open the ERP login screen, capture its controls, log in manually, then select one unique post-login marker. The marker must be absent on the login screen.</p>
    ${active && state.loginConfig?.project_id===active && state.loginReady?.configured?'<div class="callout top-note"><strong>Login selectors saved for this ERP.</strong> Future Run From Login attempts will verify authentication before replay.</div>':''}
    <div class="form-actions">
      <button class="btn btn-primary btn-small" data-action="wizard-capture-login" ${!active?'disabled':''}>1. Capture Login Fields</button>
      <button class="btn btn-outline btn-small" data-action="wizard-find-success" ${!captured?'disabled':''}>2. Find Success Marker</button>
    </div>
    ${captured?`<div class="callout top-note"><strong>Login fields captured for ${esc(state.loginWizardProject)}.</strong> Now log in manually in the ERP above; return here and click <strong>2. Find Success Marker</strong>. No username or password values were read.</div>`:''}
    ${choices.length?`<div class="field top-note"><label for="loginWizardChoice">Post-login success marker (select one you recognize)</label><select id="loginWizardChoice"><option value="">Choose a visible marker...</option>${choices.map(c=>`<option value="${c.index}">${esc(c.label)} — ${esc(c.reason)} (${esc(JSON.stringify(c.locator))})</option>`).join('')}</select></div>
    <button class="btn btn-primary btn-small" data-action="wizard-save-login">3. Verify & Save Login Setup</button>
    <p class="muted">Saving verifies one visible match now. The next automated login will verify it again before replay begins.</p>`:''}
    ${options&&!choices.length?`<div class="callout warn top-note">${esc(options.message||'No safe unique marker found. Use Browser Session’s manual JSON editor.')}</div>`:''}
    ${!active?'<p class="muted">Open your ERP from ERP Projects first.</p>':''}
  </div>`;
}
function embeddedPanel(){if(window.smartERPDesktop)return '';if(!state.session.open||!state.session.embedded)return '';
const p=activeProject();return `<section id="embeddedERP" class="embedded-erp panel" aria-label="Embedded ERP browser">
 <div class="embedded-toolbar"><div><div class="eyebrow">LIVE ERP VIEW · PLAYWRIGHT</div><strong>${esc(p?.name||state.session.project_id)}</strong> <span id="embeddedRecordingStatus" class="recording-indicator ${state.session.recording?'active':''}">${esc(recordingStatusText())}</span><small class="project-url">${esc(state.session.url||'')}</small></div>
 <div class="button-group"><button class="btn btn-outline btn-small" data-action="wizard-jump">Configure Login</button><button class="btn btn-outline btn-small" data-action="embedded-teach" ${state.session.recording?'disabled':''}>Start Teaching ERP</button><button class="btn btn-outline btn-small" data-action="embedded-save" ${!(state.session.recording||state.session.paused)?'disabled':''}>Finish &amp; Save Recording</button><button class="btn btn-outline btn-small" data-action="embedded-workflows">Saved Workflows / Replay</button><button class="btn btn-danger btn-small" data-action="embedded-close">Close Browser</button></div></div>
 <p class="embedded-hint">Click the ERP screen and type normally; scroll inside the screen. For paste, use the input below. This is a local interactive Playwright screenshot view, not a native iframe. Popup windows, downloads and some custom controls require the normal browser mode.</p>
 <div id="embeddedFocus" class="embedded-focus" tabindex="0" aria-label="Interactive ERP screen: click then use keyboard"><img id="embeddedImage" alt="Live ERP browser viewport" draggable="false"/><span id="embeddedLoading">Loading ERP screen…</span></div>
 <div class="embedded-controls"><label for="embeddedText">Paste text into currently focused ERP field</label><input id="embeddedText" type="text" autocomplete="off" placeholder="Type or paste here, then Send"/><button class="btn btn-outline btn-small" data-action="embedded-send-text">Send</button><button class="btn btn-outline btn-small" data-action="embedded-refresh">Refresh view</button><span id="embeddedScreenStatus" class="muted">Local interaction only</span></div>
 ${loginWizardPanel()}
 </section>`}

function projectPage(){const found=state.projects.filter(p=>`${p.id} ${p.name} ${p.url}`.toLowerCase().includes(state.filter.toLowerCase()));return `${embeddedPanel()}${intro('PROJECTS','Registered ERP applications','Open an ERP inside this dashboard. While the ERP view is open, project cards remain below it; closing the viewer returns to the project list.')}
<div class="panel" style="margin-bottom:16px"><div class="project-tools"><input class="search" id="projectSearch" type="search" value="${esc(state.filter)}" placeholder="Search projects"><button class="btn btn-primary" data-go="register">+ New ERP</button><button class="btn btn-outline" data-action="export">Export Projects</button><label class="btn btn-outline" for="importFile">Import Projects</label><input type="file" id="importFile" accept=".json,application/json" hidden></div></div>
<div id="projectResults" class="project-list">${found.length?found.map(projectCard).join(''):'<div class="empty"><h3>No projects found</h3><p>Register your first test ERP.</p></div>'}</div>`}
function browserPage(){return `${intro('BROWSER SESSION','Open ERP & log in manually','The ERP can open in the dashboard as an interactive image of a locally controlled Playwright browser. Complete login yourself. Login first, then click Start Teaching ERP. Actions and locators are recorded only when you explicitly start.')}
<section class="grid-two"><div class="panel"><div class="panel-head"><h3>Choose ERP</h3><span class="tag">Local Playwright</span></div><div class="field"><label>Registered project</label><select id="browserProject"><option value="">Select ERP</option>${pOptions(state.loginProject||state.session.project_id)}</select></div>
<div class="form-actions"><button class="btn btn-primary" data-action="open-selected">Open ERP Inside Dashboard</button><button class="btn btn-primary" data-action="teach-erp" ${!state.session.open?'disabled':''}>● Start Teaching ERP (After Login)</button><button class="btn btn-outline" data-action="refresh">Refresh Status</button><button class="btn btn-outline" data-action="recorder-health">Check Recorder Health</button><button class="btn btn-danger" data-action="close">Close Browser</button></div>
<div id="recorderHealth" class="callout top-note">Check Recorder Health confirms the Playwright browser has the capture script installed. This does not record or click anything.</div>
<div class="callout top-note">When using the integrated ERP view, click the ERP screenshot to focus an input, then type into it. Passwords sent to the local session are not saved in Smart ERP's workflow JSON. Then go to Workflows and click Start Fresh Recording. No steps are captured before Start Teaching ERP is clicked.</div></div>
<div class="panel"><div class="panel-head"><h3>Current Session</h3><span class="tag">${state.session.open?'ACTIVE':'CLOSED'}</span></div>
<p><strong>Project:</strong> ${esc(state.session.project_id||'None')}</p><p><strong>URL:</strong> <span class="project-url">${esc(state.session.url||'No browser opened')}</span></p><p><strong>Recorder:</strong> ${state.session.paused?'Paused':state.session.recording?'Recording '+state.session.step_count+' actions':'Stopped'}</p><div class="form-actions"><button class="btn btn-primary" data-go="workflows">Continue to Recorder →</button></div>
<div class="callout warn top-note">Embedded mode uses a Playwright headless browser mirrored inside the dashboard; the legacy standalone browser mode is still available through the API. The Codegen-style recorder supports ordinary clicks, fills, native selects, checkboxes and Enter. Complex grids, cross-origin pages, custom dropdown logic and new tabs may require manual locator review.</div></div></section>
${loginWizardPanel()}
<section class="panel top-note"><div class="panel-head"><h3>Automatic login — one-time locator setup</h3><span class="tag">No passwords saved</span></div>
<p class="muted">When you open an ERP, the backend safely inspects the login form and may capture unique username, password and login-button selectors without recording any typed values. Choose "Use Auto-Captured Login Selectors" to import candidates; you must still configure and verify a unique post-login success selector.</p>
<div class="form-actions"><button class="btn btn-outline" data-action="load-login-config">Load Login Locator JSON</button><button class="btn btn-primary" data-action="discover-login">Use Auto-Captured Login Selectors</button>${state.loginConfig&&state.loginProject?`<span class="tag">${esc(state.loginProject)}</span>`:''}</div>
${state.loginConfig?`<div class="field top-note"><label>Login config: projects/${esc(state.loginProject)}/login.json — selectors only</label><textarea id="loginConfigJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify(state.loginConfig,null,2))}</textarea><button class="btn btn-primary" data-action="save-login-config">Save Login Locator JSON</button> <button class="btn btn-outline" data-action="test-login-config">Test 3 Login Locators</button></div>`:''}
<div class="callout warn top-note">Runtime credentials are requested when you choose <strong>Run From Login</strong> in Workflows. MFA, CAPTCHA, SSO and unknown login layouts may require manual login instead.</div></section>`}
function stepTable(steps){return `<div style="overflow-x:auto"><table class="steps-table"><thead><tr><th>#</th><th>Action</th><th>Locator</th><th>Recorded value</th><th>Observed</th></tr></thead><tbody>${steps.map((s,i)=>`<tr><td>${i+1}</td><td>${esc(s.action)}</td><td><code>${esc(s.target || JSON.stringify(s.locator))}</code></td><td>${esc(s.value===null?'—':String(s.value).slice(0,120))}</td><td>${s.observed_count===1?'<span class="good">One match observed</span>':'<span class="bad">Needs review</span>'}</td></tr>`).join('')}</tbody></table></div>`}
function wfOptions(){return state.workflows.map(w=>`<option value="${esc(w.project_id+'/'+w.name)}" ${state.selected?.project_id===w.project_id&&state.selected?.name===w.name?'selected':''}>${esc(w.project_id)} / ${esc(w.name)} ${w.reviewed?'✓':''}</option>`).join('')}
function savedWorkflowManager(){
 const project=state.workflowManagerProject;
 const rows=state.workflows.filter(w=>!project||w.project_id===project);
 return `<section class="panel top-note" id="workflow-manager">
 <div class="panel-head"><h3>Manage Saved Workflows</h3><span class="tag">${rows.length} shown</span></div>
 <p class="muted">Choose an ERP to view its saved workflows. Removing one archives its JSON and removes it from the backend list, without deleting execution history. Workflows used in Business Flows or Approval Plans cannot be removed until those references are updated.</p>
 <div class="field" style="max-width:360px"><label for="manageWorkflowProject">Filter by ERP project</label><select id="manageWorkflowProject"><option value="">All ERP projects</option>${state.projects.map(p=>`<option value="${esc(p.id)}" ${project===p.id?'selected':''}>${esc(p.name)} (${esc(p.id)})</option>`).join('')}</select></div>
 <div style="overflow-x:auto" class="top-note"><table class="steps-table"><thead><tr><th>ERP project</th><th>Workflow name</th><th>Steps</th><th>Status</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
 ${rows.map(w=>`<tr><td>${esc(w.project_id)}</td><td><strong>${esc(w.name)}</strong></td><td>${Number(w.step_count)||0}</td><td><span class="tag ${w.reviewed?'':'amber'}">${w.reviewed?'Reviewed':'Draft'}</span></td><td>${esc(w.updated_at||'—')}</td><td><div class="button-group"><button class="btn btn-outline btn-small" data-action="manage-load-workflow" data-project="${esc(w.project_id)}" data-name="${esc(w.name)}">Open</button><button class="btn btn-danger btn-small" data-action="remove-saved-workflow" data-project="${esc(w.project_id)}" data-name="${esc(w.name)}">Remove</button></div></td></tr>`).join('')}
 </tbody></table>${rows.length?'':'<p class="muted">No saved workflows found for this project.</p>'}</div>
 <div class="callout warn"><strong>Safety:</strong> Click Remove, then choose Yes or No. If you choose Yes, the workflow JSON is archived locally for recovery; execution history and other projects are preserved. Workflows referenced by approval plans or business flows cannot be removed.</div>
 </section>`;
}
function pomPanel(){const w=state.selected;const project=state.pomProjectId||w?.project_id||state.projects[0]?.id||'';
return `<section class="panel top-note"><div class="panel-head"><h3>Shared Page Object Model (POM)</h3><span class="tag">Reusable across projects</span></div>
<p class="muted">A shared template holds logical steps. Each ERP's own mapping connects those steps to recorded locator keys. Templates contain no ERP URLs, CSS selectors, or passwords.</p>
${w?`<div class="form-grid"><div class="field"><label>New shared template name</label><input id="pomNewTemplate" value="${esc(w.name)}" placeholder="purchase_indent"></div></div>
<div class="form-actions"><button class="btn btn-outline" data-action="pom-create" ${!w.reviewed?'disabled':''}>Create Shared POM from Reviewed Workflow</button></div>`:''}
<div class="form-grid"><div class="field"><label>Shared POM template</label><select id="pomTemplate"><option value="">Choose template</option>${state.pomTemplates.map(t=>`<option value="${esc(t)}" ${t===state.pomSelected?'selected':''}>${esc(t)}</option>`).join('')}</select></div>
<div class="field"><label>ERP project mapping</label><select id="pomProject">${pOptions(project)}</select></div></div>
<div class="form-actions"><button class="btn btn-outline" data-action="pom-load-map">Load POM Mapping</button><button class="btn btn-outline" data-action="pom-preview" ${!state.pomSelected?'disabled':''}>Preview POM</button></div>
${state.pomTemplateDoc?`<div class="field top-note"><label>Shared business actions JSON (no selectors here). Add explicit capture_text / assert_text actions only after recording their targets. Editing invalidates approvals.</label><textarea id="pomTemplateJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify(state.pomTemplateDoc,null,2))}</textarea><button class="btn btn-outline" data-action="pom-save-template">Save Shared Template (requires mapping reapproval)</button></div>`:''}
${state.pomMapping?`<div class="field top-note"><label>Project-specific logical field → recorded locator key JSON (review before saving)</label><textarea id="pomMapJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify(state.pomMapping,null,2))}</textarea></div><div class="form-actions"><button class="btn btn-outline" data-action="pom-save-map">Save Draft Mapping</button><button class="btn btn-primary" data-action="pom-approve-map">Approve POM Mapping</button></div>`:''}
<div class="field top-note"><label>Runtime test data JSON (no passwords)</label><textarea id="pomTestData" class="json-editor" spellcheck="false">{}</textarea></div>
<label><input type="checkbox" id="pomAllowWrites"> I authorize any write actions only in TEST/STAGING</label>
<div class="form-actions"><button class="btn btn-primary" data-action="pom-run" ${!state.pomSelected?'disabled':''}>Run Shared POM (Current Browser)</button><button class="btn btn-outline" data-action="pom-negative">Run Safe Native Negative Checks</button></div>
${state.pomPreview?`<pre class="json-preview" style="max-height:230px;overflow:auto">${esc(JSON.stringify(state.pomPreview,null,2))}</pre>`:''}
</section>
<section class="panel top-note"><div class="panel-head"><h3>Linked procurement (experimental)</h3><span class="tag amber">Only reviewed, same-login stages</span></div>
<p class="muted">Set the exact shared workflow template names in order. Each stage must include configured capture steps to produce runtime identifiers. A failure blocks later stages. Different approver roles are intentionally blocked until role switching is configured.</p>
<div class="field"><label>Linked plan JSON — edit project and template names</label><textarea id="linkedPlanJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify({project_id:project,stages:[{template:'purchase_indent',role:'creator'},{template:'lpo_creation',role:'creator'}],test_data:{},allow_test_transactions:false},null,2))}</textarea></div>
<div class="form-actions"><button class="btn btn-outline" data-action="linked-preview">Check Dependencies</button><button class="btn btn-primary" data-action="linked-run">Run Ready Chain (TEST Only)</button></div>
${state.linkedResult?`<pre class="json-preview" style="max-height:250px;overflow:auto">${esc(JSON.stringify(state.linkedResult,null,2))}</pre>`:''}</section>`;
}
function workflowPage(){const w=state.selected;return `${intro('RECORDER & REPLAY','Teach once. Replay reliably.','Record only verified actions in your authorized test ERP. Every saved workflow is isolated by project and must be reviewed before replay.')}
<section class="grid-two"><div class="panel"><div class="panel-head"><h3>Automatic process learning</h3><span class="tag ${state.session.recording?'amber':''}">${state.session.recording?'TEACHING ON':'IDLE'}</span></div><p><strong>Connected ERP:</strong> ${esc(state.session.project_id||'No active browser')}</p>
<div class="field"><label>New workflow name</label><input id="workflowName" value="${esc(state.recordName)}" placeholder="purchase_indent"></div>
<div class="form-actions recorder-actions">
<button class="btn btn-primary" data-action="start-record" ${!state.session.open?'disabled':''}>● Start Teaching ERP (After Login)</button>
<button class="btn btn-outline" data-action="pause-record" ${!state.session.recording?'disabled':''}>Ⅱ Pause</button>
<button class="btn btn-outline" data-action="resume-record" ${!state.session.paused?'disabled':''}>▶ Resume</button>
<button class="btn btn-primary" data-action="stop-record" ${!(state.session.recording||state.session.paused)?'disabled':''}>■ Finish Demonstration & Save JSON</button>
</div>
<div class="callout top-note"><strong>How to record:</strong> Open ERP → login directly in the ERP browser → Start Teaching ERP → perform the workflow → Finish Demonstration & Save JSON. Recording is OFF during manual login. Passwords and login forms are excluded. Browser stays open.</div>
<div id="recorderLive"><p class="muted">Actions captured: <strong>${state.session.step_count||0}</strong> · ${state.session.paused?'PAUSED':state.session.recording?'RECORDING':'STOPPED'}</p>
${state.session.warnings?.length?`<div class="callout warn">${state.session.warnings.map(esc).join(' · ')}</div>`:''}
${state.preview?.steps?.length?`<div class="top-note"><h4>Live recorded steps (last 50)</h4>${stepTable(state.preview.steps)}</div>`:'<p class="muted">No recorded actions yet. Click inside the ERP browser while recording.</p>'}</div></div>
<div class="panel"><div class="panel-head"><h3>Saved workflows</h3><span class="tag">${state.workflows.length}</span></div><div class="field"><label>Choose workflow</label><select id="workflowSelect"><option value="">Select a workflow</option>${wfOptions()}</select></div><div class="form-actions"><button class="btn btn-outline" data-action="load-workflow">Load Workflow</button><button class="btn btn-outline" data-action="refresh">Refresh</button><button class="btn btn-primary" data-action="toggle-workflow-manager">${state.workflowManagerOpen?'Hide Workflow List':'Manage Saved Workflows'}</button></div><div class="callout top-note"><strong>Workflow review:</strong> Login credentials and password fields are not recorded. Inspect every non-secret input before approval. Observed uniqueness is rechecked by Playwright when running.</div></div></section>
${state.workflowManagerOpen?savedWorkflowManager():''}
<section class="panel top-note" id="allReplayDiagnostics"><div class="panel-head"><h3>Why are my workflows blocked?</h3><span class="tag">Read-only checks</span></div>
<p class="muted">Diagnose the first step of up to 20 workflows for the currently open ERP project. This checks them on the CURRENT screen only; workflows starting on other pages will correctly report a mismatch. No ERP buttons are clicked and no records are changed.</p>
<button class="btn btn-outline" data-action="diagnose-all-replay" ${!state.session.open?'disabled':''}>Diagnose All Workflows for Open ERP</button>
${state.batchPreflight?`<p class="muted">ERP: ${esc(state.batchPreflight.project_id)} · Current screen only · ${state.batchPreflight.entries.length} workflows</p>
<div style="overflow-x:auto"><table class="steps-table"><thead><tr><th>Workflow</th><th>Step 1</th><th>Result</th><th>Reason / next action</th></tr></thead><tbody>
${state.batchPreflight.entries.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.target||'Unknown')}</td><td><span class="tag ${r.ready?'':'amber'}">${r.ready?'READY':esc(r.reason_code||'BLOCKED')}</span></td><td>${esc(r.reason||'See individual diagnostic')}</td></tr>`).join('')}
</tbody></table></div>`:''}
</section>
<section class="panel top-note"><div class="panel-head"><h3>Live ERP HTML / ID Inspector</h3><span class="tag">READ ONLY</span></div>
<p class="muted">Inspect the LIVE ERP browser after manual login. The app reads safe control attributes from the HTML DOM and proposes unique JSON locators. HTML preview contains no input values or passwords. It does not modify a saved workflow.</p>
<div class="form-actions"><button class="btn btn-outline" data-action="inspect-dom" ${!state.session.open?'disabled':''}>Inspect Current Page IDs & Buttons</button></div>
${state.domInspector?`<p class="muted">Project: ${esc(state.domInspector.project_id)} · Page: ${esc(state.domInspector.page_url)} · Visible controls: ${state.domInspector.scanned} (max 100)</p>
<div class="json-preview" style="max-height:410px;overflow:auto">
${state.domInspector.controls.length?`<table style="width:100%;border-collapse:collapse"><thead><tr><th>HTML element (sanitized)</th><th>Proposed JSON locator</th><th>Status</th></tr></thead><tbody>
${state.domInspector.controls.map((c,i)=>`<tr><td style="max-width:300px;word-break:break-word"><code>${esc(c.html)}</code></td><td><code>${c.locator?esc(JSON.stringify(c.locator)):'No stable locator'}</code>${c.locator?` <button class="btn btn-outline" data-action="copy-dom-locator" data-index="${i}">Copy JSON</button>`:''}</td><td>${c.unique?'1 match':esc(c.issue||'Review required')}${c.generated_id?' · Generated ID':''}</td></tr>`).join('')}
</tbody></table>`:'No visible non-sensitive controls found on the main page.'}</div>
<p class="muted">A unique ID on one page is not guaranteed to remain stable after login, navigation, or a deployment. Confirm the correct element and save changes through the workflow locator editor, then approve again.</p>`:''}
</section>
${w?`<section class="panel top-note"><div class="panel-head"><h3>${esc(w.project_id)} / ${esc(w.name)}</h3><span class="tag ${w.reviewed?'':'amber'}">${w.reviewed?'Reviewed':'Draft - review required'}</span></div><p class="muted">Starts at: ${esc(w.start_url)} · ${w.steps.length} steps</p>${stepTable(w.steps)}<div class="panel top-note"><div class="panel-head"><h3>Generate Page Object Model automation</h3><span class="tag ${w.reviewed?'':'amber'}">${w.reviewed?'Approved JSON':'Review required'}</span></div>
<p class="muted"><strong>Manual ERP login → Teach ERP → Locator JSON + ordered workflow JSON → Generate POM → Replay → Reports</strong></p>
<div class="form-actions"><button class="btn btn-primary" data-action="export-pom-bundle" ${!w.reviewed?'disabled':''}>⬇ Generate POM Python + pytest (ZIP)</button><button class="btn btn-outline" data-action="export-python">Download Single Replay Script (.py)</button></div>
<p class="muted">The ZIP contains reusable Page Objects, a workflow runner, offline tests and opt-in positive/negative pytest examples. Browser input/locators come only from reviewed JSON. No business-rule tests are invented. To execute from this dashboard, use the reviewed replay controls below. Its results appear in Overview.</p>
</div>
${w.schema_version===2?`<div class="callout top-note"><strong>JSON-driven:</strong> Step targets live in <code>projects/${esc(w.project_id)}/locators.json</code>. The Python engine resolves them by name. Editing locators requires re-approval of affected workflows.</div>`:''}
<div class="form-actions"><button class="btn btn-outline" data-action="json-toggle">${state.editing?'Hide Editor':'Edit Workflow JSON'}</button><button class="btn btn-outline" data-action="test-first">Test First Locator on Current Page</button><button class="btn btn-outline" data-action="preflight-first">Diagnose Replay Start (No Clicks)</button><button class="btn btn-outline" data-action="inspect-dom">Inspect Live HTML IDs (No Clicks)</button>${w.schema_version===1?`<button class="btn btn-outline" data-action="convert-v2">Convert to JSON Locators</button>`:`<button class="btn btn-outline" data-action="locators-toggle">${state.editingLocators?'Hide Locator Editor':'View / Edit Locator JSON'}</button>`}<button class="btn btn-primary" data-action="approve" ${w.reviewed?'disabled':''}>Approve Reviewed Workflow</button></div>
${state.replayPreflight?`<div class="panel top-note" id="replayStartDiagnostic"><div class="panel-head"><h3>Replay Start Diagnostic</h3><span class="tag ${state.replayPreflight.ready?'':'amber'}">${state.replayPreflight.ready?'LOCATOR READY':'NOT READY'}</span></div>
<p class="muted">Current page: ${esc(state.replayPreflight.current_url)}</p>
<p class="muted">First executable page: ${esc(state.replayPreflight.recorded_start_url)} · Original login actions skipped: ${Number(state.replayPreflight.skipped_initial_login_steps)||0}</p>
<p><strong>First executable step #${Number(state.replayPreflight.first_executable_step_number)||1}:</strong> ${esc(state.replayPreflight.first_step_action)} — ${esc(state.replayPreflight.first_step_target||JSON.stringify(state.replayPreflight.first_step_locator))}</p>
<p><strong>Matches:</strong> ${state.replayPreflight.matches} · <strong>Visible:</strong> ${state.replayPreflight.visible_matches} · <strong>Reason:</strong> ${esc(state.replayPreflight.reason_code||'UNKNOWN')}</p>
<div class="callout warn">${state.replayPreflight.findings.map(x=>`<p>${esc(x)}</p>`).join('')}</div>
<h4 class="top-note">Visible buttons and links (read-only, first 40)</h4>
<p class="muted">These controls help you identify missing navigation steps. They are not automatic locator replacements.</p>
<div class="json-preview" style="max-height:240px;overflow:auto">${state.replayPreflight.visible_controls.length?state.replayPreflight.visible_controls.map(x=>`<div>${esc(x.role)}: ${esc(x.text)}</div>`).join(''):'No controls detected in the main document. The control might be inside an iframe or shadow DOM.'}</div>
<h4 class="top-note">Recorded alternative locator diagnostics (read-only)</h4>
<p class="muted">A unique match is only a candidate. Confirm the correct intended element before editing locator JSON and reapproving.</p>
<div class="json-preview" style="max-height:210px;overflow:auto">${(state.replayPreflight.candidate_checks||[]).length?(state.replayPreflight.candidate_checks||[]).map(c=>`<div>${c.uniquely_visible?'MATCHES ONCE':'NOT READY'} · ${c.matches} found, ${c.visible_matches} visible: <code>${esc(JSON.stringify(c.locator))}</code></div>`).join(''):'No alternative locators were saved with this recording. Re-record this step if the primary locator is wrong.'}</div></div>`:''}
${state.editingLocators&&state.locators?`<div class="field top-note"><label>Project-specific locator library — edits invalidate affected approvals</label><textarea id="locatorJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify(state.locators,null,2))}</textarea><button class="btn btn-primary" data-action="save-locators">Save Locator Library</button></div>`:''}
${state.editing?`<div class="field top-note"><label>Advanced editor — JSON (no secrets). Saving resets approval.</label><textarea id="workflowJSON" class="json-editor" spellcheck="false">${esc(JSON.stringify(w,null,2))}</textarea><button class="btn btn-primary" data-action="save-json">Save Edited JSON</button></div>`:''}
<div class="panel top-note"><div class="panel-head"><h3>Verify a specific recorded step (e.g. Step 4)</h3><span class="tag amber">Requires intended element confirmation</span></div>
<p class="muted">Navigate the Playwright ERP browser to the original page first. This checks one locator's visibility and uniqueness; it never clicks. If it matches the wrong element, edit the locator JSON instead.</p>
<div class="field"><label>Step number</label><input id="stepReviewNumber" type="number" min="1" max="${w.steps.length}" value="4"></div>
<div class="form-actions"><button class="btn btn-outline" data-action="step-review-load">Inspect Step</button><button class="btn btn-outline" data-action="step-review-candidates">Check Candidate Locators</button><button class="btn btn-outline" data-action="step-review-ai">Local AI Suggestion</button><button class="btn btn-outline" data-action="step-review-verify">Verify Intended Locator on Current Page</button></div>
${state.stepReview?`<pre class="json-preview" style="max-height:220px;overflow:auto">${esc(JSON.stringify(state.stepReview,null,2))}</pre>`:''}
</div>
<div class="panel top-note"><div class="panel-head"><h3>Suggested negative test cases</h3><span class="tag">HTML constraints only</span></div>
<p class="muted">Detect required fields, numeric min/max and email/minlength rules from recorded fields. AI cannot infer all ERP rules. Running these checks never clicks Save, Submit or Approve.</p>
<div class="form-actions"><button class="btn btn-outline" data-action="generate-negative" ${w.schema_version!==2?'disabled':''}>Generate Negative Cases</button><button class="btn btn-outline" data-action="run-negative" ${!w.reviewed||!state.session.open?'disabled':''}>Run Safe Negative Checks (Current Form)</button></div>
${state.negativeCandidates?`<div class="callout top-note">Generated ${state.negativeCandidates.cases.length} candidates. Review field targets and configured constraints before running.</div><pre class="json-preview" style="max-height:230px;overflow:auto">${esc(JSON.stringify(state.negativeCandidates.cases,null,2))}</pre>`:''}
${state.negativeResult?`<div class="callout top-note"><strong>Results:</strong> ${esc(JSON.stringify(state.negativeResult.summary))}<p>${esc(state.negativeResult.note)}</p></div>`:''}
</div>
<div class="callout warn top-note"><strong>Safe replay:</strong> Use only test/staging. Save, Approve and Submit can change records. This phase does not validate ERP business outcomes and does not automatically retry failed actions.</div>
<div class="field top-note"><label>Runtime test values (JSON, optional). For a step value of <code>&#36;{quantity}</code> enter <code>{"quantity": 12}</code>. Do not enter passwords or secrets.</label><textarea id="testDataJSON" class="json-editor" spellcheck="false" placeholder='{"quantity":12}'>{}</textarea></div>
<div class="run-controls"><label><input type="checkbox" id="allowWrites"> I authorize this workflow to change records in my test/staging ERP.</label><label class="top-note"><input type="checkbox" id="allowNavRepair"> Allow exact-label navigation locator recovery (e.g. Procurement menus) in approved replay. Requires one visible interactive control; never auto-fixes record-changing buttons.</label></div>
<div class="callout top-note" id="sessionReplayMode"><strong>Already logged in?</strong> This replay uses your CURRENT ERP browser session. It does not open another browser, reload the ERP, or type credentials. A complete recorded login sequence at the beginning is skipped; later business actions are retained. If the ERP session has expired, sign in manually first.</div>
<div class="run-readiness" id="replayReadiness">${!w.reviewed?'Review and approve this recording before replay.':!state.session.open?'Open the ERP inside Projects, log in, and return here.':state.session.project_id!==w.project_id?'The open ERP project does not match this workflow. Open '+esc(w.project_id)+' instead.':'Preflight required: click Diagnose Replay Start before running. The engine will not guess missing elements.'}</div>
<div class="form-actions"><button class="btn btn-primary" data-action="run-workflow">▶ Check &amp; Replay Approved Workflow (Already Logged In)</button></div>
<div class="panel top-note" id="runtimeLoginPanel"><div class="panel-head"><h3>Run from Login → ERP workflow</h3><span class="tag">Runtime credentials</span></div>
<p class="muted">The approved workflow starts only after automatic login succeeds. Saved login.json must contain your ERP-specific username, password, login-button, and post-login success selectors. <strong>Entering credentials alone does not configure the login locators.</strong> Passwords are never saved.</p>
<div class="callout ${state.loginReady?.configured?'':'warn'} top-note" id="loginSetupStatus">${esc(state.loginReady?.message||'Select a saved workflow to check login setup.')}</div>
<div class="form-actions"><button class="btn btn-outline btn-small" data-action="check-login-setup">Check Login Setup</button><button class="btn btn-outline btn-small" data-action="configure-login-setup">Configure Login Selectors</button></div>
<div class="form-grid"><div class="field"><label>Test username</label><input id="runUsername" autocomplete="off" maxlength="200" placeholder="Your authorized test account"></div><div class="field"><label>Test password</label><input id="runPassword" type="password" autocomplete="new-password" placeholder="Runtime only"></div></div>
<div class="form-actions"><button class="btn btn-primary" data-action="run-from-login" data-mode="embedded">▶ Run From Login (Inside Dashboard)</button><button class="btn btn-outline" data-action="run-from-login" data-mode="window">▶ Run From Login (New Browser)</button></div>
<div class="callout top-note">Use <strong>Inside Dashboard</strong> for your single-link setup at <code>127.0.0.1:8766</code>. <strong>New Browser</strong> launches a separate Playwright window. Both modes require an approved TEST/STAGING workflow and login selectors.</div>
${state.lastAutoRun&&state.lastAutoRun.project_id===w.project_id&&state.lastAutoRun.workflow===w.name?`<div class="callout ${state.lastAutoRun.status==='PASSED'?'':'warn'} top-note" id="lastAutoRun"><strong>Latest automatic run: ${esc(state.lastAutoRun.status)}</strong><p>${esc(state.lastAutoRun.message||'')}</p><p>Login verified: ${state.lastAutoRun.login_verified?'Yes':'No'} · Failed step: ${esc(state.lastAutoRun.failed_step??'None')}</p>${state.lastAutoRun.navigation_recoveries?.length?`<p>Verified navigation repairs: ${esc(state.lastAutoRun.navigation_recoveries.length)}</p>`:''}</div>`:''}
</div>
<div class="panel top-note"><div class="panel-head"><h3>Optional AI failure hints (local Ollama)</h3><span class="tag">No auto-fixes</span></div>
<p class="muted">After a FAILED execution, this asks your locally running Ollama model for suggestions. Only the failure type, step number and action type are sent. No ERP data, screenshots, values or locator strings.</p>
<div class="form-actions"><button class="btn btn-outline" data-action="ai-analyze">AI Analyze Latest Failure</button></div>
${state.aiDiagnosis?`<div class="callout top-note"><strong>Unverified AI suggestions</strong><p style="white-space:pre-wrap">${esc(state.aiDiagnosis)}</p></div>`:''}
</div>
</section>`:''}
${state.draft?.warnings?.length?`<section class="panel top-note"><h3>Recorder warnings</h3>${state.draft.warnings.map(x=>`<p class="bad">${esc(x)}</p>`).join('')}</section>`:''}
${pomPanel()}
${recentRuns()}`}
function approvalPage(){
 const active=state.approvalPlan;
 const project=active?.project_id||state.session.project_id||state.projects[0]?.id||'';
 const options=state.approvalPlans.map(p=>`<option value="${esc(p.project_id+'/'+p.name)}" ${active&&(active.project_id+'/'+active.name)===p.project_id+'/'+p.name?'selected':''}>${esc(p.project_id)} / ${esc(p.name)}${p.registered?'':' (register ERP first)'}</option>`).join('');
 const preview=state.approvalPreview;
 return `${intro('MULTI-ERP CONFIGURATION','Approval Workflow Manager','One Playwright automation engine, different approved workflows, accounts and approval orders for each ERP. Edit project-specific JSON and review all stages before running.')}
 <section class="grid-two"><div class="panel"><h3>Choose approval plan</h3>
 <div class="field"><label>Existing plans</label><select id="approvalPlanSelect"><option value="">Select saved plan</option>${options}</select></div>
 <div class="form-actions"><button class="btn btn-outline" data-action="approval-load">Load Plan</button><button class="btn btn-primary" data-action="approval-new">New Plan</button></div>
 <p class="muted">Your Kagami example defines 3 PI approvals and 4 LPO approvals. A different ERP may define fewer approvers, different buttons or a different sequence.</p>
 <div class="callout warn">Real record changes and user switching are blocked until each required workflow is recorded, reviewed, and its post-approval assertion is configured. Accounts/passwords are NEVER placed in plan JSON.</div>
 </div><div class="panel"><h3>Active browser</h3><p>Project: <strong>${esc(state.session.project_id||'None')}</strong></p><p>Status: <strong>${state.session.open?'Open':'Closed'}</strong></p>
 <p class="muted">Open the matching ERP from Browser Session. For automatic role switching, start on the login screen and configure the project's login selectors. Account secrets belong only in your local .env file.</p><button class="btn btn-outline" data-go="browser">Manage Browser</button></div></section>
 <section class="panel top-note"><div class="panel-head"><h3>Plan JSON editor</h3><span class="tag">No credentials</span></div>
 <p class="muted">Each stage refers to a saved reviewed workflow. Workflow steps may capture IDs (pi_number/lpo_number/grn_number) and reuse them via variables such as \${pi_number}. Approval stages require an assertion after the click.</p>
 <textarea id="approvalPlanJSON" class="json-editor" style="min-height:300px" spellcheck="false">${esc(JSON.stringify(active||{schema_version:1,project_id:project,name:'indent_to_grn',description:'Configure workflows and accounts for this ERP',logout_workflow:'logout',stages:[{name:'Create Indent',workflow:'create_indent',account:null,phase:'create',require_assertion:true},{name:'Approve Indent',workflow:'approve_indent',account:null,phase:'approval',require_assertion:true},{name:'Create LPO',workflow:'create_lpo',account:null,phase:'create',require_assertion:true},{name:'Create GRN',workflow:'create_grn',account:null,phase:'grn',require_assertion:true}]},null,2))}</textarea>
 <div class="form-actions"><button class="btn btn-primary" data-action="approval-save">Save Approval Plan</button><button class="btn btn-outline" data-action="approval-preview">Validate Plan</button></div>
 ${preview?`<div class="top-note"><h3>Preflight: ${preview.ready?'READY':'NOT READY'}</h3>${preview.issues.length?`<div class="callout warn">${preview.issues.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`:'<div class="callout">Every recorded workflow and required assertion is approved and ready.</div>'}
 <div style="overflow:auto"><table class="steps-table"><thead><tr><th>#</th><th>Stage</th><th>Account</th><th>Workflow</th><th>Status</th></tr></thead><tbody>${preview.stages.map(st=>`<tr><td>${st.number}</td><td>${esc(st.name)}</td><td>${esc(st.account||'Manual session')}</td><td>${esc(st.workflow)}</td><td class="${st.ready?'good':'bad'}">${st.ready?'Ready':esc(st.issues.join('; '))}</td></tr>`).join('')}</tbody></table></div></div>`:''}
 </section>
 <section class="panel top-note"><h3>Optional AI positive / negative test ideas</h3>
 <p class="muted">Only sanitized action types and field constraints are sent to the selected provider. OpenAI requires your opt-in and local OPENAI_API_KEY. Ollama runs locally. AI suggestions are not executable tests.</p>
 <div class="form-grid"><div class="field"><label>Provider</label><select id="aiCaseProvider"><option value="rules">Offline rule ideas</option><option value="ollama">Local Ollama</option><option value="openai">OpenAI API</option></select></div><div class="field"><label>Model (optional)</label><input id="aiCaseModel" placeholder="Leave blank for configured default"></div></div>
 <div class="form-grid"><div class="field"><label>Recorded workflow</label><select id="aiCaseWorkflow"><option value="">Select workflow</option>${state.workflows.filter(w=>w.project_id===(active?.project_id||project)).map(w=>`<option value="${esc(w.name)}">${esc(w.name)}</option>`).join('')}</select></div></div>
 <div class="form-actions"><button class="btn btn-outline" data-action="ai-case-ideas">Suggest Positive + Negative Tests</button></div>
 ${state.aiIdeas?`<div class="callout top-note"><strong>${esc(state.aiIdeas.provider)}: ${state.aiIdeas.cases.filter(x=>x.category==='positive').length} positive, ${state.aiIdeas.cases.filter(x=>x.category==='negative').length} negative ideas</strong><p>${esc(state.aiIdeas.note)}</p><pre class="json-preview" style="max-height:260px;overflow:auto">${esc(JSON.stringify(state.aiIdeas.cases,null,2))}</pre></div>`:''}
 </section>
 <section class="panel top-note"><h3>Run approval plan in TEST/STAGING</h3>
 <p class="muted">Provide additional runtime values only if needed. Captured transaction IDs are passed to later stages automatically; do not hardcode another record's ID.</p>
 <div class="field"><label>Runtime test data (JSON)</label><textarea id="approvalTestData" class="approval-small-data" spellcheck="false">{}</textarea></div>
 <div class="run-controls"><label><input id="approvalAllowWrites" type="checkbox"> I confirm authorized test/staging access and permit this plan to create, submit and approve test records.</label></div>
 <div class="form-actions"><button class="btn btn-primary" data-action="approval-run" ${!state.session.open?'disabled':''}>Run Reviewed Approval Plan</button></div>
 ${state.approvalRun?`<div class="callout top-note"><strong>${esc(state.approvalRun.status)} — ${state.approvalRun.completed_stages} / ${state.approvalRun.total_stages} stages</strong><p>${esc(state.approvalRun.message)}</p><pre class="json-preview" style="max-height:260px;overflow:auto">${esc(JSON.stringify(state.approvalRun,null,2))}</pre></div>`:''}
 </section>`;
}
function recentRuns(){return `<div class="section-title-row"><h2 class="subheading">Recent executions</h2></div><section class="panel">${state.executions.length?`<div style="overflow:auto"><table class="steps-table"><thead><tr><th>ID</th><th>ERP</th><th>Workflow</th><th>Status</th><th>Message</th></tr></thead><tbody>${state.executions.slice(0,12).map(r=>`<tr><td>${r.id}</td><td>${esc(r.project_id)}</td><td>${esc(r.workflow_name)}</td><td class="${r.status==='PASSED'?'good':'bad'}">${esc(r.status)}</td><td>${esc(r.message)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="muted">No workflow replays yet.</div>'}</section>`}
function guidePage(){return `${intro('GETTING STARTED','Real backend, local browser','This version connects the green-and-white UI to a Python FastAPI server, SQLite and Playwright on your computer.')}
<div class="grid-two"><div class="panel"><h3>Recommended first test</h3><ol class="steps">${[['01','Register local mock ERP','Project ID: mock_erp · URL: http://127.0.0.1:8766/mock/'],['02','Open and log in','Use any non-empty DUMMY credentials in mock browser.'],['03','Demonstrate once','Click Create New Indent, fill safe test data, and do not Save initially.'],['04','Review workflow','Stop, inspect values/locators and approve.'],['05','Replay in mock','Click Run Reviewed Workflow; confirm test transaction checkbox.']].map(x=>`<li class="step"><span class="step-index">${x[0]}</span><div><strong>${x[1]}</strong><small>${x[2]}</small></div></li>`).join('')}</ol></div>
<div class="panel"><h3>Important limits</h3><div class="callout warn">The Hugging Face Static Space cannot run this backend. Run <code>python run.py</code> from VS Code on Windows. Local execution controls a browser on that Windows PC.</div><p class="muted">This version now supports reviewed approval plans with environment-backed account switching and captured ID transfer. Existing ERP-specific Kagami functions remain reference code; rule-specific round-robin and PDF checks require validated ERP adapters. AI is an optional local failure assistant only. These need separate verified workflows and your ERP rules.</p></div></div>`}
function flowPage(){
 const flow=state.flowDoc;
 const project=flow?.project_id||state.flowProject||state.session.project_id||state.projects[0]?.id||'';
 const choices=state.businessFlows.map(x=>`<option value="${esc(x.project_id+'/'+x.name)}" ${flow&&(flow.project_id+'/'+flow.name)===(x.project_id+'/'+x.name)?'selected':''}>${esc(x.project_id)} / ${esc(x.name)} (${x.stages} stages)</option>`).join('');
 const wf=state.workflows.filter(x=>x.project_id===project&&x.reviewed);
 const preview=state.flowPreview;
 return `${intro('END-TO-END BUSINESS PROCESS','Flow Studio: Indent → PO → GRN','Log in manually, record each stage, review locators and assertions, then assemble an ERP-specific flow using the same Playwright runner.')}
 <section class="grid-two"><div class="panel"><h3>1. Select ERP and build a business flow</h3><p class="muted">Capture each stage from Workflows, for example indent creation, approval, purchase order and GRN. Save and approve each recording before linking it here.</p>
 <div class="field"><label>ERP project</label><select id="flowProject"><option value="">Choose registered ERP</option>${pOptions(project)}</select></div>
 <div class="form-actions"><button class="btn btn-primary" data-action="flow-new">New Indent-to-GRN Flow</button><button class="btn btn-outline" data-go="workflows">Record a Stage</button></div>
 <div class="field top-note"><label>Previously saved flows</label><select id="flowSelect"><option value="">Choose flow</option>${choices}</select></div>
 <div class="form-actions"><button class="btn btn-outline" data-action="flow-load">Load Saved Flow</button></div>
 <p class="muted">Approved workflows for selected ERP: <strong>${wf.length}</strong>${wf.length?' — '+wf.map(x=>esc(x.name)).join(', '):'. Record and approve your actual stage workflows first.'}</p>
 </div><div class="panel"><h3>2. Runtime browser</h3><p>Connected ERP: <strong>${esc(state.session.project_id||'None')}</strong> · ${state.session.open?'Open':'Closed'}</p><p class="muted">Keep the authenticated Playwright browser open on the first stage screen. Flow replay never guesses an element, changes your account or reloads the login page.</p><button class="btn btn-outline" data-go="browser">Open / Close Browser</button>
 <div class="form-actions top-note"><button class="btn btn-outline" data-action="flow-prepare" ${!state.session.open?'disabled':''}>Stop Passive Capture for Replay</button></div><div class="callout warn top-note"><strong>Separate approver accounts?</strong> Use Approval Plans for verified logout/login and role transitions. Flow Studio runs only within one authenticated account.</div></div></section>
 ${flow?`<section class="panel top-note"><div class="panel-head"><h3>3. Assign recorded workflows to business stages</h3><span class="tag">Project-specific JSON</span></div>
 <p class="muted">Replace <code>replace_me</code> with names from your approved workflows. Omit any phases your ERP does not have. Do not add credentials. Every stage must end with a verified assertion, such as status visible, after the final action.</p>
 <div class="field"><label>Flow mapping JSON (saved under flows/${esc(flow.project_id)}/)</label><textarea id="flowJSON" class="json-editor" style="min-height:340px" spellcheck="false">${esc(JSON.stringify(flow,null,2))}</textarea></div>
 <div class="form-actions"><button class="btn btn-primary" data-action="flow-save">Save Flow Mapping</button><button class="btn btn-outline" data-action="flow-preview">Validate Dependencies</button></div>
 <div class="field top-note"><label>Runtime inputs, optional; e.g. {"quantity":10}. A capture_text step can populate variables for later stages.</label><textarea id="flowTestData" class="json-editor" style="min-height:80px" spellcheck="false">${esc(JSON.stringify(state.flowInputs,null,2))}</textarea></div>
 <label><input id="flowAllowWrites" type="checkbox"> I authorize creating, submitting or approving records in TEST/STAGING with my current account.</label>
 <div class="form-actions top-note"><button class="btn btn-primary" data-action="flow-run" ${!state.session.open?'disabled':''}>▶ Run Validated Business Flow</button></div>
 ${preview?`<div class="top-note"><h3>Preflight: <span class="${preview.ready?'good':'bad'}">${preview.ready?'READY':'NOT READY'}</span></h3><p class="muted">${esc(preview.note||'')}</p>${preview.issues?.length?`<div class="callout warn">${preview.issues.map(x=>`<p>${esc(x)}</p>`).join('')}</div>`:''}<table class="steps-table"><thead><tr><th>#</th><th>Business phase</th><th>Workflow</th><th>Preflight</th></tr></thead><tbody>${preview.stages.map(x=>`<tr><td>${x.number}</td><td>${esc(x.phase)}</td><td>${esc(x.workflow)}</td><td class="${x.ready?'good':'bad'}">${x.ready?'Ready':esc(x.issues.join('; '))}</td></tr>`).join('')}</tbody></table></div>`:''}
 ${state.flowRun?`<div class="top-note"><h3>Execution: ${esc(state.flowRun.status)}</h3><pre class="json-preview" style="max-height:280px;overflow:auto">${esc(JSON.stringify(state.flowRun,null,2))}</pre></div>`:''}</section>`:'<div class="panel top-note">Create or load a flow to configure your end-to-end stages.</div>'}
 <section class="panel top-note"><h3>For other ERP applications</h3><p class="muted">Register the second ERP, log in manually, capture its own screens and link its own workflows to the same phase names. Locator JSON remains isolated by ERP. Different document types, approval roles and business rules still require reviewed mappings and explicit assertions.</p></section>`;
}
function render(){stopEmbeddedPolling();if(window.smartERPDesktop)window.smartERPDesktop.setPage(state.page);const pages={overview,register:registerPage,projects:projectPage,workflows:workflowPage,browser:browserPage,approvals:approvalPage,flows:flowPage,suite:leocemTestCasesPage,scripts:scriptPage,reports:scriptReportsPage,guide:guidePage,ailab:window.optionalAiLabPage};$('content').innerHTML=pages[state.page]();$('modeName').textContent=(window.smartERPDesktop?'Desktop Chromium':'Local Playwright');$('footerMode').textContent=window.smartERPDesktop?'FastAPI + SQLite + Chromium (Electron)':'FastAPI + SQLite + Playwright';document.body.classList.toggle('erp-embedded-active',state.page==='projects'&&!!state.session.open&&!!state.session.embedded);if(state.page==='projects'&&state.session.embedded&&!state.session.electron)startEmbeddedPolling();updateRecordingIndicators();if(state.page==='overview'&&window.qaAnimateNumbers)window.qaAnimateNumbers()}
async function refresh(show=false){try{const [projects,workflows,metrics,executions,session,pomTemplates,approvalPlans,businessFlows]=await Promise.all([api('/projects'),api('/workflows'),api('/metrics'),api('/executions'),api('/browser/status'),api('/pom/templates'),api('/approval-plans'),api('/flows')]);Object.assign(state,{projects,workflows,metrics,executions,session,pomTemplates,approvalPlans,businessFlows});render();if(show)notify('Dashboard refreshed')}catch(e){notify(e.message,true)}}
async function openProject(id){if(window.smartERPDesktop){await window.smartERPDesktop.openERP(id)}else{await api('/browser/open','POST',{project_id:id,embedded:true})}state.preview=null;await refresh();go('projects');notify('ERP opened in this dashboard. Click inside to log in; begin teaching after login.')}
async function loadWorkflow(id){if(!id)return;state.replayPreflight=null;state.aiDiagnosis=null;state.negativeCandidates=null;state.negativeResult=null;const [project_id,name]=id.split('/');state.selected=await api(`/workflows/${encodeURIComponent(project_id)}/${encodeURIComponent(name)}`);if(state.selected.schema_version===2){state.negativeCandidates=await api(`/workflows/${encodeURIComponent(project_id)}/${encodeURIComponent(name)}/negative-candidates`)}state.locators=state.selected.schema_version===2?await api(`/projects/${encodeURIComponent(project_id)}/locators`):null;state.loginReady=await api(`/projects/${encodeURIComponent(project_id)}/login-ready`);state.editing=false;state.editingLocators=false;go('workflows')}
async function runAction(action,btn){
 if(state.busy)return;state.busy=true;btn.disabled=true;
 try{
  if(action.startsWith('suite-')){await suiteAction(action);return;}
  if(action==='flow-prepare'){
    if(!confirm('Stop recording and DISCARD unsaved browser actions? Saved JSON workflows and your ERP login are preserved.'))return;
    const status=await api('/flows/prepare-browser','POST');await refresh();go('flows');
    notify(`Recorder stopped; ${status.discarded_unsaved_steps} unsaved actions discarded. Saved workflows unchanged.`);
  }
  if(action==='flow-new'){
    const project=$('flowProject')?.value||state.flowProject||state.session.project_id;
    if(!project)throw new Error('Choose the registered ERP project first');
    state.flowProject=project;state.flowDoc=await api(`/flows/starter/${encodeURIComponent(project)}`);
    state.flowPreview=null;state.flowRun=null;render();notify('Map each business phase to a reviewed workflow for this ERP');
  }
  if(action==='flow-load'){
    const id=$('flowSelect')?.value;if(!id)throw new Error('Select a saved flow');
    const [project,name]=id.split('/');state.flowDoc=await api(`/flows/${encodeURIComponent(project)}/${encodeURIComponent(name)}`);
    state.flowProject=project;state.flowPreview=null;state.flowRun=null;render();notify('Business flow loaded');
  }
  if(action==='flow-save'){
    const mapping=JSON.parse($('flowJSON')?.value||'{}');
    state.flowDoc=await api(`/flows/${encodeURIComponent(mapping.project_id)}/${encodeURIComponent(mapping.name)}`,'PUT',mapping);
    state.flowProject=mapping.project_id;state.flowPreview=null;state.flowRun=null;await refresh();go('flows');notify('ERP-specific flow mapping saved');
  }
  if(action==='flow-preview'){
    const mapping=JSON.parse($('flowJSON')?.value||'{}');
    const test_data=JSON.parse($('flowTestData')?.value||'{}');
    state.flowDoc=await api(`/flows/${encodeURIComponent(mapping.project_id)}/${encodeURIComponent(mapping.name)}`,'PUT',mapping);
    state.flowInputs=test_data;state.flowPreview=await api(`/flows/${mapping.project_id}/${mapping.name}/preview`,'POST',{test_data});
    state.flowProject=mapping.project_id;await refresh();go('flows');
    notify(state.flowPreview.ready?'Flow dependencies ready':'Flow needs recorded steps, approval, or assertions',!state.flowPreview.ready);
  }
  if(action==='flow-run'){
    const mapping=JSON.parse($('flowJSON')?.value||'{}');
    if(!state.flowDoc||JSON.stringify(mapping)!==JSON.stringify(state.flowDoc))throw new Error('Save your edited flow before running');
    const test_data=JSON.parse($('flowTestData')?.value||'{}');state.flowInputs=test_data;
    if(!$('flowAllowWrites')?.checked)throw new Error('Confirm authorized TEST/STAGING transactions');
    if(!confirm(`Execute ${mapping.name} in the currently logged-in ${mapping.project_id} ERP? This may create/approve records. Each stage stops on failure and no action is retried.`))return;
    state.flowRun=await api('/flows/run','POST',{project_id:mapping.project_id,name:mapping.name,test_data,allow_test_transactions:true,confirm_same_session:true});
    await refresh();go('flows');notify(`${state.flowRun.status}: ${state.flowRun.completed_stages}/${state.flowRun.total_stages} stages`,state.flowRun.status!=='PASSED');
  }
  if(action==='ai-case-ideas'){
    const wf=$('aiCaseWorkflow')?.value;const provider=$('aiCaseProvider')?.value;const model=$('aiCaseModel')?.value.trim()||null;
    const project=state.approvalPlan?.project_id||state.session.project_id;
    if(!wf||!project)throw new Error('Choose an ERP and one recorded workflow');
    if(provider==='openai'&&!confirm('Send ONLY sanitized workflow action types and field constraints to OpenAI to suggest test ideas? No credentials, field values, URLs or locators will be sent.'))return;
    state.aiIdeas=await api('/ai/test-cases','POST',{project_id:project,workflow_name:wf,provider,model});render();notify(`${state.aiIdeas.cases.length} unexecuted test ideas generated`);
  }
  if(action==='approval-load'){
    const raw=$('approvalPlanSelect')?.value;if(!raw)throw new Error('Select an approval plan');
    const [p,n]=raw.split('/');state.approvalPlan=await api(`/approval-plans/${p}/${n}`);state.approvalPreview=await api(`/approval-plans/${p}/${n}/preview`);state.approvalRun=null;render();notify('Approval plan loaded');
  }
  if(action==='approval-new'){
    state.approvalPlan={schema_version:1,project_id:state.session.project_id||state.projects[0]?.id||'mock_erp',name:'new_indent_to_grn',description:'Edit workflows and approval roles',logout_workflow:null,stages:[{name:'Create and submit Indent',workflow:'create_indent',account:null,phase:'create',require_assertion:true},{name:'Approve Indent',workflow:'approve_indent',account:null,phase:'approval',require_assertion:true},{name:'Create and submit LPO',workflow:'create_lpo',account:null,phase:'create',require_assertion:true},{name:'Create GRN',workflow:'create_grn',account:null,phase:'grn',require_assertion:true}]};state.approvalPreview=null;state.approvalRun=null;render();notify('Edit the JSON and save your new plan');
  }
  if(action==='approval-save'){
    const plan=JSON.parse($('approvalPlanJSON')?.value||'{}');
    state.approvalPlan=await api(`/approval-plans/${encodeURIComponent(plan.project_id)}/${encodeURIComponent(plan.name)}`,'PUT',plan);
    state.approvalPreview=await api(`/approval-plans/${plan.project_id}/${plan.name}/preview`);state.approvalRun=null;await refresh();notify('Approval plan saved. Review preflight issues before execution.');
  }
  if(action==='approval-preview'){
    const plan=JSON.parse($('approvalPlanJSON')?.value||'{}');
    state.approvalPlan=await api(`/approval-plans/${encodeURIComponent(plan.project_id)}/${encodeURIComponent(plan.name)}`,'PUT',plan);
    state.approvalPreview=await api(`/approval-plans/${plan.project_id}/${plan.name}/preview`);await refresh();notify(state.approvalPreview.ready?'Ready to run':'Plan has prerequisites; see checklist',!state.approvalPreview.ready);
  }
  if(action==='approval-run'){
    const plan=JSON.parse($('approvalPlanJSON')?.value||'{}');
    if(JSON.stringify(plan)!==JSON.stringify(state.approvalPlan))throw new Error('Save and validate any edited plan before running');
    const test_data=JSON.parse($('approvalTestData')?.value||'{}');
    if(!$('approvalAllowWrites')?.checked)throw new Error('Confirm authorized test/staging record changes');
    if(!confirm('Execute this exact approval plan in the open authorized TEST/STAGING ERP? Each action may create/submit/approve records. Failed stages will stop the sequence.'))return;
    state.approvalRun=await api('/approval-plans/run','POST',{project_id:plan.project_id,name:plan.name,allow_test_transactions:true,test_data});
    await refresh();notify(`${state.approvalRun.status}: ${state.approvalRun.completed_stages}/${state.approvalRun.total_stages} stages`,state.approvalRun.status!=='PASSED');
  }

  if(action==='recorder-health'){
    const status=await api('/browser/recorder-health');
    const el=$('recorderHealth');
    const detail=`${status.installed?'Recorder script installed':'Recorder script is missing'} | Frame: ${status.frame_count} | Captured steps: ${status.step_count} | Mode: ${status.recording?'RECORDING':'STOPPED'} | ${status.note}`;
    if(el)el.textContent=detail;
    notify(detail,!status.installed);
  }
  if(action==='refresh') await refresh(true);
  if(action==='open-project')await openProject(btn.dataset.id);
  if(action==='open-selected'){const id=$('browserProject')?.value;if(!id)throw new Error('Select an ERP first');await openProject(id)}
  if(action==='close'||action==='embedded-close'){if(window.smartERPDesktop)await window.smartERPDesktop.closeERP();else await api('/browser/close','POST');await refresh();go('projects');notify('Browser closed; back to ERP projects')}
  if(action==='embedded-teach'){await api('/recorder/start','POST');lastRecordingProject=state.session.project_id;lastRecordingStepCount=0;await refresh();go('projects');notify('● RECORDING ON — interact with the ERP. Captured actions will show as notifications.')}
  if(action==='embedded-save'){
    if(!(state.session.recording||state.session.paused))throw new Error('Start Teaching ERP before saving a workflow.');
    const input=prompt('Workflow name (lowercase letters, digits, underscores or hyphens):',state.recordName);
    if(input===null)return;
    const name=input.trim();
    if(!/^[a-z][a-z0-9_-]{0,59}$/.test(name))throw new Error('Use a workflow name starting with a lowercase letter.');
    state.recordName=name;
    const result=await api('/recorder/stop','POST',{name});
    state.draft=result;state.preview=null;
    await refresh();await loadWorkflow(result.workflow.project_id+'/'+result.workflow.name);
    notify(`Saved ${result.workflow.steps.length} steps. Review and approve the workflow before replay.`);
  }
  if(action==='embedded-workflows')go('workflows');
  if(action==='embedded-refresh')await refreshEmbeddedImage();
  if(action==='embedded-send-text'){const input=$('embeddedText');if(input?.value){await embeddedSend({kind:'type',text:input.value});input.value='';$('embeddedFocus')?.focus()}}
  if(action==='wizard-jump'){ $('guidedLoginSetup')?.scrollIntoView({behavior:'smooth',block:'start'}); }
  if(action==='wizard-capture-login'){
    const id=state.session.project_id;
    if(!id)throw new Error('Open an ERP login screen inside the dashboard first.');
    const data=await api(`/projects/${encodeURIComponent(id)}/login-setup/capture`,'POST');
    state.loginWizardProject=id;state.loginWizardFields=data.fields;state.loginWizardOptions=null;
    state.loginProject=id;render();
    notify('Login controls verified (3 unique selectors). Sign in manually, then click Find Success Marker.');
  }
  if(action==='wizard-find-success'){
    const id=state.session.project_id;
    if(!id||state.loginWizardProject!==id||!state.loginWizardFields)throw new Error('Capture login fields before manually signing in.');
    const data=await api(`/projects/${encodeURIComponent(id)}/login-setup/success-options`);
    state.loginWizardOptions=data;render();
    notify(data.ready?`Found ${data.candidates.length} post-login marker options. Choose the correct one.`:data.message,!data.ready);
  }
  if(action==='wizard-save-login'){
    const id=state.session.project_id;
    if(!id||state.loginWizardProject!==id)throw new Error('Use the same ERP session for both login steps.');
    const selected=$('loginWizardChoice')?.value;
    if(selected===undefined||selected==='')throw new Error('Choose a post-login marker from the list first.');
    if(!confirm('Save these verified login LOCATORS for the registered test ERP? No username or password values are stored.'))return;
    const result=await api(`/projects/${encodeURIComponent(id)}/login-setup/save`,'POST',{index:Number(selected)});
    state.loginConfig=await api(`/projects/${encodeURIComponent(id)}/login-config`);
    state.loginReady=await api(`/projects/${encodeURIComponent(id)}/login-ready`);
    state.loginWizardOptions=null;state.loginWizardFields=null;
    render();notify(result.message);
  }
  if(action==='load-login-config'){
    const project=$('browserProject')?.value||state.session.project_id;
    if(!project)throw new Error('Select a registered ERP first');
    state.loginProject=project;
    state.loginConfig=await api(`/projects/${encodeURIComponent(project)}/login-config`);
    render();notify('Edit and verify selectors before saving. Passwords are never stored.');
  }
  if(action==='discover-login'){
    const project=$('browserProject')?.value||state.session.project_id;
    if(!project)throw new Error('Select an ERP and open its login page first');
    const guessed=await api('/browser/login-candidates');
    if(guessed.project_id!==project)throw new Error('Browser is connected to another project');
    if(!guessed.detected)throw new Error(guessed.reason||'No unique login controls detected. Open the login screen before manual login.');
    const existing=await api(`/projects/${encodeURIComponent(project)}/login-config`);
    state.loginProject=project;
    state.loginConfig={...existing, username:guessed.username, password:guessed.password, submit:guessed.submit};
    render();
    notify('Login selectors imported (no passwords). Set the POST-login success selector and review before saving.');
  }
  if(action==='save-login-config'){
    if(!state.loginProject)throw new Error('Select an ERP first');
    const config=JSON.parse($('loginConfigJSON').value);
    state.loginConfig=await api(`/projects/${encodeURIComponent(state.loginProject)}/login-config`,'PUT',config);
    if(state.selected?.project_id===state.loginProject)state.loginReady=await api(`/projects/${encodeURIComponent(state.loginProject)}/login-ready`);
    render();notify('Login selectors saved. Test them on the login page before replay.');
  }
  if(action==='test-login-config'){
    if(!state.loginProject)throw new Error('Load login locator JSON first');
    const result=await api(`/projects/${encodeURIComponent(state.loginProject)}/login-config/test`,'POST');
    notify(result.uniquely_visible?'All 3 pre-login locators uniquely visible.':'One or more login locators need correction. See the warning.',!result.uniquely_visible);
    if(!result.uniquely_visible)alert(JSON.stringify(result.fields,null,2));
  }
  if(action==='edit')go('register',btn.dataset.id);
  if(action==='delete'){const id=btn.dataset.id;if(confirm(`Delete project ${id}? Only projects without workflows can be deleted.`)){await api('/projects/'+encodeURIComponent(id),'DELETE');await refresh();notify('Project removed')}}
  if(action==='export'){const blob=new Blob([JSON.stringify({schema_version:1,projects:state.projects},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='smart-erp-projects.json';a.click();URL.revokeObjectURL(url)}
  if(action==='teach-erp' || action==='start-record'){
    if(!state.session.open)throw new Error('Open ERP Application and log in manually first');
    if(state.session.recording && !confirm('Recording is already active. Start a new recording and discard unsaved steps?'))return;
    if(state.session.step_count && !confirm('Start fresh? Unsaved captured steps will be cleared.'))return;
    await api('/recorder/start','POST');state.preview=null;lastRecordingProject=state.session.project_id;lastRecordingStepCount=0;await refresh();
    if(state.session.embedded)go('projects');else go('workflows');
    notify('● RECORDING ON — click in the ERP now. Every captured action will appear as a notification. Finish & Save in Workflows.');
  }
  if(action==='pause-record'){await api('/recorder/pause','POST');await refresh();notify('Capture paused; ERP browser remains open.')}
  if(action==='resume-record'){await api('/recorder/resume','POST');await refresh();notify('Capture resumed; continue in ERP browser.')}
  if(action==='export-pom-bundle'){
    const w=state.selected;
    if(!w||!w.reviewed)throw new Error('Load and approve a reviewed workflow first');
    const url=`/api/workflows/${encodeURIComponent(w.project_id)}/${encodeURIComponent(w.name)}/pom-bundle`;
    const response=await fetch(url,{cache:'no-store'});
    if(!response.ok){
      const reason=await response.json().catch(()=>({detail:'POM generation failed'}));
      throw new Error(typeof reason.detail==='string'?reason.detail:'POM generation failed');
    }
    const blob=await response.blob();
    const objectURL=URL.createObjectURL(blob);
    const link=document.createElement('a');
    link.href=objectURL;link.download=w.project_id+'_'+w.name+'_pom.zip';
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(objectURL),1500);
    notify('Generated POM ZIP downloaded. Review code and tests before executing against TEST/STAGING.');
  }
  if(action==='export-python'){
    const w=state.selected;if(!w)throw new Error('Select a saved workflow first');
    const link=document.createElement('a');link.href=`/api/workflows/${encodeURIComponent(w.project_id)}/${encodeURIComponent(w.name)}/python`;link.download=w.name+'.py';document.body.appendChild(link);link.click();link.remove();
    notify('Python code export requested. Review the downloaded script before use.');
  }
  if(action==='stop-record'){const name=state.recordName.trim();if(!name)throw new Error('Enter workflow name');const draft=await api('/recorder/stop','POST',{name});state.draft=draft;state.preview=null;await refresh();await loadWorkflow(draft.workflow.project_id+'/'+draft.workflow.name);notify(`Saved ${draft.workflow.steps.length} steps and ${draft.negative_candidates} suggested negative cases. Review before replay.`)}
  if(action==='generate-negative'){
    const w=state.selected;if(!w)throw new Error('Select workflow first');
    state.negativeCandidates=await api(`/workflows/${w.project_id}/${w.name}/negative-candidates`);
    render();notify(`${state.negativeCandidates.cases.length} field-constraint negative candidates generated; review them before running.`);
  }
  if(action==='run-negative'){
    const w=state.selected;if(!w)throw new Error('Select approved workflow first');
    if(!confirm('Test invalid field values on the CURRENT form only, in TEST/STAGING? No Save/Submit/Approve will be clicked.'))return;
    state.negativeResult=await api('/workflows/run-negative','POST',{project_id:w.project_id,name:w.name,confirm_safe_test:true});
    await refresh();notify(`Negative check results: ${JSON.stringify(state.negativeResult.summary)}`);
  }
  if(action==='toggle-workflow-manager'){
    state.workflowManagerOpen=!state.workflowManagerOpen;render();
  }
  if(action==='manage-load-workflow'){
    await loadWorkflow(btn.dataset.project+'/'+btn.dataset.name);
    notify('Workflow loaded. Review its steps before replay.');
  }
  if(action==='remove-saved-workflow'){
    const project=btn.dataset.project, name=btn.dataset.name;
    const key=project+'/'+name;
    if(!await confirmRemoveWorkflow(key))return;
    const result=await api(`/workflows/${encodeURIComponent(project)}/${encodeURIComponent(name)}`,'DELETE');
    if(state.selected?.project_id===project&&state.selected?.name===name){
      state.selected=null;state.locators=null;state.editing=false;state.editingLocators=false;
      state.replayPreflight=null;state.stepReview=null;state.negativeCandidates=null;
    }
    await refresh();go('workflows');notify(`Removed ${key} from backend. Recovery archive: ${result.archive_path}`);
  }
  if(action==='load-workflow'){const id=$('workflowSelect')?.value;if(!id)throw new Error('Choose a workflow');await loadWorkflow(id)}
  if(action==='json-toggle'){state.editing=!state.editing;render()}
  if(action==='locators-toggle'){state.editingLocators=!state.editingLocators;render()}
  if(action==='save-locators'){const w=state.selected;if(!w||w.schema_version!==2)throw new Error('Select a JSON-driven workflow');const updated=JSON.parse($('locatorJSON').value);state.locators=await api(`/projects/${encodeURIComponent(w.project_id)}/locators`,'PUT',updated);await refresh();await loadWorkflow(w.project_id+'/'+w.name);notify('Locator library saved. Re-review affected workflows before replay.')}
  if(action==='convert-v2'){const w=state.selected;if(!w||w.schema_version!==1)throw new Error('Select a legacy workflow');if(!confirm('Back up and convert this existing workflow to project JSON locators? Approval will reset.'))return;await api(`/workflows/${w.project_id}/${w.name}/convert-v2`,'POST');await refresh();await loadWorkflow(w.project_id+'/'+w.name);notify('Legacy workflow converted; review generated locator keys.')}

  if(action==='step-review-load'){
    const w=state.selected;if(!w)throw new Error('Choose a workflow');const n=Number($('stepReviewNumber')?.value);
    state.stepReview=await api(`/workflows/${w.project_id}/${w.name}/step-review/${n}`);render();notify('Inspect the candidate and original page before verification.');
  }
  if(action==='step-review-candidates'){
    const w=state.selected;if(!w)throw new Error('Choose workflow');const n=Number($('stepReviewNumber')?.value);
    state.stepReview=await api(`/workflows/${w.project_id}/${w.name}/step-review/${n}/candidates`);
    render();notify('Review the matching alternatives and edit locator JSON manually if necessary.');
  }
  if(action==='step-review-ai'){
    const w=state.selected;if(!w)throw new Error('Choose workflow');const n=Number($('stepReviewNumber')?.value);
    state.stepReview=await api(`/workflows/${w.project_id}/${w.name}/step-review/${n}/ai-suggest`,'POST');
    render();notify('Optional local AI suggested a candidate. No locator was changed. Review and verify manually.');
  }
  if(action==='step-review-verify'){
    const w=state.selected;if(!w)throw new Error('Choose workflow');const n=Number($('stepReviewNumber')?.value);
    if(!confirm(`Are you on the correct ERP page and does locator step ${n} identify the intended element? No click will be executed.`))return;
    state.stepReview=await api(`/workflows/${w.project_id}/${w.name}/step-review/${n}/verify`,'POST',{confirm_intended_element:true});
    await refresh();await loadWorkflow(w.project_id+'/'+w.name);notify(`Step ${n} is uniquely visible. Review the full workflow again.`);
  }
  if(action==='pom-create'){
    const w=state.selected;if(!w)throw new Error('Choose a reviewed recording');const name=$('pomNewTemplate')?.value.trim();
    if(!name)throw new Error('Enter a shared template name');
    const result=await api('/pom/create-from-workflow','POST',{project_id:w.project_id,workflow_name:w.name,template_name:name});
    state.pomSelected=result.template.name;state.pomProjectId=w.project_id;state.pomMapping=result.mapping;state.pomTemplateDoc=result.template;
    await refresh();notify('Shared POM created. Map its logical fields for each new ERP project.');
  }
  if(action==='pom-load-map'){
    const name=$('pomTemplate')?.value;const project=$('pomProject')?.value;
    if(!name||!project)throw new Error('Select a POM template and ERP project');
    state.pomSelected=name;state.pomProjectId=project;
    state.pomMapping=await api(`/pom/maps/${project}/${name}`);state.pomTemplateDoc=await api(`/pom/templates/${name}`);state.pomPreview=null;render();
    notify('Review mappings to the selected ERP locator library.');
  }
  if(action==='pom-save-template'){
    const updated=JSON.parse($('pomTemplateJSON').value);
    if(!state.pomSelected||updated.name!==state.pomSelected)throw new Error('Template identity cannot change');
    if(!confirm('Editing a shared business template affects all ERP project mappings. Each mapping must be reviewed and approved again. Continue?'))return;
    state.pomTemplateDoc=await api(`/pom/templates/${state.pomSelected}`,'PUT',updated);
    render();notify('Template saved. Reapprove the POM mapping before replay.');
  }
  if(action==='pom-save-map'){
    const mapping=JSON.parse($('pomMapJSON').value);
    state.pomMapping=await api(`/pom/maps/${mapping.project_id}/${mapping.template_name}`,'PUT',mapping);
    render();notify('Mapping saved as draft; explicit approval required.');
  }
  if(action==='pom-approve-map'){
    if(!state.pomMapping)throw new Error('Load mapping first');
    if(!confirm('Have you mapped and verified every logical field to the correct locator in this ERP?'))return;
    const x=state.pomMapping;state.pomMapping=await api(`/pom/maps/${x.project_id}/${x.template_name}/approve`,'POST');
    render();notify('Project mapping approved.');
  }
  if(action==='pom-preview'||action==='pom-run'){
    const name=$('pomTemplate')?.value||state.pomSelected;const project=$('pomProject')?.value||state.pomProjectId;
    if(!name||!project)throw new Error('Choose a POM template and project');
    const test_data=JSON.parse($('pomTestData')?.value||'{}');
    const payload={project_id:project,template_name:name,test_data,allow_test_transactions:Boolean($('pomAllowWrites')?.checked)};
    if(action==='pom-run'&&!confirm(`Run ${name} in ${project} using the OPEN authorized browser? TEST/STAGING only.`))return;
    state.pomPreview=await api(action==='pom-run'?'/pom/run':'/pom/preview','POST',payload);
    await refresh();notify(action==='pom-run'?`${state.pomPreview.status}: check execution history`:'Mapping and test-data preflight succeeded.',action==='pom-run'&&state.pomPreview.status!=='PASSED');
  }
  if(action==='pom-negative'){
    const project=$('pomProject')?.value||state.pomProjectId;
    const template=$('pomTemplate')?.value||state.pomSelected;
    if(!project||!template)throw new Error('Select project and template');
    if(!confirm('On the CURRENT form in TEST/STAGING, safely try invalid values in mapped native fields? No Save/Submit/Approve is executed.'))return;
    state.pomPreview=await api('/pom/run-negative','POST',{project_id:project,template_name:template,confirm_safe_test:true});
    await refresh();notify(`Native negative result: ${state.pomPreview.status}`);
  }
  if(action==='linked-preview'||action==='linked-run'){
    const plan=JSON.parse($('linkedPlanJSON')?.value||'{}');
    if(action==='linked-run'&&!confirm('Run every listed linked stage? No automatic retry, and test/staging transactions only.'))return;
    state.linkedResult=await api(action==='linked-run'?'/pom/linked/run':'/pom/linked/preview','POST',plan);
    await refresh();notify(state.linkedResult.ready?'Dependency preflight passed':`${state.linkedResult.status}. See stage results.`);
  }
  if(action==='save-json'){const w=state.selected;if(!w)throw new Error('Select workflow');const updated=JSON.parse($('workflowJSON').value);state.selected=await api(`/workflows/${w.project_id}/${w.name}`,'PUT',updated);state.editing=false;await refresh();notify('Workflow edited; review required again')}
  if(action==='inspect-dom'){
    state.domInspector=await api('/browser/dom-inspector');
    render();notify(`Inspected ${state.domInspector.scanned} visible controls. No ERP buttons clicked.`);
  }
  if(action==='copy-dom-locator'){
    const selected=state.domInspector?.controls?.[Number(btn.dataset.index)];
    if(!selected?.locator)throw new Error('This control has no stable unique locator');
    await navigator.clipboard.writeText(JSON.stringify(selected.locator,null,2));
    notify('Locator JSON copied. Verify the target before saving to a workflow.');
  }
  if(action==='diagnose-all-replay'){
    if(!state.session.open||!state.session.project_id)throw new Error('Open an ERP project first');
    const project=state.session.project_id;
    const choices=state.workflows.filter(w=>w.project_id===project).slice(0,20);
    if(!choices.length)throw new Error(`No saved workflows for ${project}`);
    const entries=[];
    for(const workflow of choices){
      try{
        const diagnostic=await api(`/workflows/${encodeURIComponent(project)}/${encodeURIComponent(workflow.name)}/preflight-first`);
        const details=(diagnostic.findings||[]).find(x=>!x.startsWith('LOCATOR READY')&&!x.startsWith('ROUTE VERIFIED'))||diagnostic.findings?.[0]||'';
        entries.push({name:workflow.name,target:diagnostic.first_step_target,ready:!!diagnostic.ready,reason_code:diagnostic.reason_code,reason:details});
      }catch(error){entries.push({name:workflow.name,ready:false,reason_code:'CHECK_ERROR',reason:error.message})}
    }
    state.batchPreflight={project_id:project,entries};render();
    $('allReplayDiagnostics')?.scrollIntoView({behavior:'smooth',block:'start'});
    const ready=entries.filter(x=>x.ready).length;
    notify(`Read-only replay check: ${ready}/${entries.length} workflows ready on the CURRENT ERP screen.`,ready===0);
  }
  if(action==='preflight-first'){
    const w=state.selected;if(!w||!w.steps.length)throw new Error('Load a saved workflow first');
    state.replayPreflight=await api(`/workflows/${encodeURIComponent(w.project_id)}/${encodeURIComponent(w.name)}/preflight-first?reuse_existing_login=true`);
    render();notify(state.replayPreflight.ready?'Step 1 uniquely verified. Later steps still need review.':`Replay blocked: ${state.replayPreflight.reason_code||'NOT_READY'} — ${(state.replayPreflight.findings||[])[0]||'Inspect the start diagnostic.'}`,!state.replayPreflight.ready);$('replayStartDiagnostic')?.scrollIntoView({behavior:'smooth',block:'start'});
  }
  if(action==='test-first'){const w=state.selected;if(!w?.steps.length)throw new Error('No steps');const input=w.schema_version===2?{project_id:w.project_id,target:w.steps[0].target}:{locator:w.steps[0].locator};const result=await api(w.schema_version===2?'/locator/test-target':'/locator/test','POST',input);notify(`First locator: ${result.count} element matched, visible=${result.visible}. Check you are on the correct ERP page.`)}
  if(action==='approve'){const w=state.selected;if(!w)throw new Error('Select workflow');if(!confirm('Have you manually checked each locator and input value? This authorizes replay on TEST/STAGING only.'))return;await api(`/workflows/${w.project_id}/${w.name}/approve`,'POST');await refresh();await loadWorkflow(w.project_id+'/'+w.name);notify('Workflow reviewed and approved')}
  if(action==='check-login-setup'){
    const w=state.selected;if(!w)throw new Error('Load a workflow first');
    state.loginReady=await api(`/projects/${encodeURIComponent(w.project_id)}/login-ready`);
    const label=$('loginSetupStatus');if(label)label.textContent=state.loginReady.message;
    notify(state.loginReady.message,!state.loginReady.configured);
  }
  if(action==='configure-login-setup'){
    const w=state.selected;if(!w)throw new Error('Load a workflow first');
    state.loginProject=w.project_id;
    state.loginConfig=await api(`/projects/${encodeURIComponent(w.project_id)}/login-config`);
    go('browser');
    const picker=$('browserProject');if(picker)picker.value=w.project_id;
    notify('Configure login selectors on the login screen. You must verify the unique post-login success selector; no password is saved.');
  }
  if(action==='run-from-login'){
    const w=state.selected;
    if(!w)throw new Error('Select a saved workflow');
    if(!w.reviewed)throw new Error('Review and approve this workflow first. Credentials do not replace workflow approval.');
    const project=state.projects.find(p=>p.id===w.project_id);
    if(!project||project.environment==='production')throw new Error('Run From Login is available only for TEST/STAGING projects.');
    state.loginReady=await api(`/projects/${encodeURIComponent(w.project_id)}/login-ready`);
    if(!state.loginReady.configured)throw new Error(state.loginReady.message);
    const username=$('runUsername')?.value.trim();
    const password=$('runPassword')?.value;
    const test_data=JSON.parse($('testDataJSON')?.value||'{}');
    const allow_test_transactions=$('allowWrites')?.checked||false;
    const allow_nav_repair=$('allowNavRepair')?.checked||false;
    const embedded=btn.dataset.mode==='embedded';
    if(!username||!password)throw new Error('Enter authorized TEST username and password for this run');
    if(!test_data||Array.isArray(test_data)||typeof test_data!=='object')throw new Error('Test data must be a JSON object');
    if(!confirm(`Start ${w.name} on ${w.project_id} (TEST/STAGING only) using ${embedded?'the link-based dashboard':'a separate browser window'}? Automatic login must verify its success marker before replay. Navigation recovery: ${allow_nav_repair?'enabled':'off'}.`))return;
    const payload={project_id:w.project_id,name:w.name,username,password,test_data,allow_test_transactions,embedded,allow_nav_repair};
    $('runPassword').value='';
    notify('Automatic login started. The workflow will run only after the success selector is verified.');
    let result;
    try { result=await api('/workflows/run-from-login','POST',payload); }
    finally { payload.password=''; }
    state.lastAutoRun=result;
    await refresh();
    notify(`${result.login_verified?'Login verified. ':''}${result.status}: ${result.message}`,result.status!=='PASSED');
    if(result.status==='FAILED')alert(`Run failed at step ${result.failed_step??'unknown'}: ${result.message}
Screenshot: ${result.screenshot||'not saved'}
Trace: ${result.trace||'not saved'}`);
    if(embedded){go('projects');notify(result.status==='PASSED'?'Automation completed inside the dashboard. Open Overview for the report.':'Replay stopped; the ERP remains in your dashboard so you can inspect the failed page.',result.status!=='PASSED');}
  }
  if(action==='ai-analyze'){
    const w=state.selected;
    if(!w)throw new Error('Select a workflow');
    const recent=state.executions.find(x=>x.project_id===w.project_id&&x.workflow_name===w.name&&x.status==='FAILED');
    if(!recent)throw new Error('No FAILED execution found for this workflow');
    const result=await api('/ai/diagnose','POST',{execution_id:recent.id});
    state.aiDiagnosis=result.suggestion;
    render();notify('Local AI suggestions received. Review manually before editing locators.');
  }
  if(action==='run-workflow'){const w=state.selected;if(!w)throw new Error('Load a saved workflow first');if(!w.reviewed)throw new Error('This workflow is a draft. Review its actions/locators and click Approve before replay.');if(!state.session.open)throw new Error('Open an ERP inside ERP Projects and log in before replay.');if(state.session.project_id!==w.project_id)throw new Error(`Open the correct ERP project (${w.project_id}) before running this workflow.`);if(state.session.recording||state.session.paused)throw new Error('Finish and save the current demonstration before replay.');const flag=$('allowWrites')?.checked||false;const allow_nav_repair=$('allowNavRepair')?.checked||false;const test_data=JSON.parse($('testDataJSON')?.value||'{}');if(!test_data||Array.isArray(test_data)||typeof test_data!=='object')throw new Error('Runtime test data must be a JSON object');
    // Check first step on the ACTUAL post-login screen before any state-changing click.
    state.replayPreflight=await api(`/workflows/${encodeURIComponent(w.project_id)}/${encodeURIComponent(w.name)}/preflight-first?reuse_existing_login=true`);
    if(!state.replayPreflight.ready){render();const cause=(state.replayPreflight.findings||[])[0]||'Inspect Replay Start Diagnostic';notify(`Replay blocked: ${state.replayPreflight.reason_code||'NOT_READY'} — ${cause}`,true);$('replayStartDiagnostic')?.scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(!confirm(`Continue ${w.name} in the CURRENT, already logged-in ${w.project_id} ERP session (TEST/STAGING only)?\n\nNo browser will be opened and no login will be performed. ${state.replayPreflight.skipped_initial_login_steps||0} verified initial login actions will be skipped. Business actions may change test records.`))return;
    const result=await api('/workflows/run','POST',{project_id:w.project_id,name:w.name,allow_test_transactions:flag,allow_nav_repair,reuse_existing_login:true,test_data});await refresh();notify(`${result.status}: ${result.message}${result.skipped_initial_login_steps?' (Skipped '+result.skipped_initial_login_steps+' recorded login steps)':''}`,result.status!=='PASSED');if(result.status==='FAILED')alert(`Workflow failed.\n${result.message}\nTrace: ${result.trace||'not saved'}\nScreenshot: ${result.screenshot||'not saved'}`)}
 }catch(e){notify(e.message,true)}finally{state.busy=false;if(document.contains(btn))btn.disabled=false}
}
document.addEventListener('click',e=>{const nav=e.target.closest('[data-page]');if(nav)return go(nav.dataset.page);const route=e.target.closest('[data-go]');if(route)return go(route.dataset.go);const act=e.target.closest('[data-action]');if(act)void runAction(act.dataset.action,act)});
document.addEventListener('submit',async e=>{if(!e.target.matches('form#projectForm'))return;e.preventDefault();try{const raw=Object.fromEntries(new FormData(e.target).entries());await api('/projects','POST',raw);state.editId=null;await refresh();go('projects');notify('ERP registered in SQLite')}catch(err){notify(err.message,true)}});
document.addEventListener('input',e=>{if(e.target.id==='workflowName')state.recordName=e.target.value;if(e.target.id==='projectSearch'){state.filter=e.target.value;const result=state.projects.filter(p=>`${p.id} ${p.name} ${p.url}`.toLowerCase().includes(state.filter.toLowerCase()));$('projectResults').innerHTML=result.map(projectCard).join('')||'<div class="empty">No matching projects</div>'}});
document.addEventListener('change',async e=>{if(e.target.id==='browserProject')state.loginProject=e.target.value;if(e.target.id==='flowProject')state.flowProject=e.target.value;if(e.target.id==='manageWorkflowProject'){state.workflowManagerProject=e.target.value;render()}if(e.target.id==='importFile'&&e.target.files?.length){try{const doc=JSON.parse(await e.target.files[0].text());if(!Array.isArray(doc.projects))throw new Error('File must contain projects list');for(const p of doc.projects)await api('/projects','POST',{id:p.id,name:p.name,appName:p.appName,url:p.url,environment:p.environment,browser:p.browser,description:p.description||''});await refresh();notify(`Imported ${doc.projects.length} projects`)}catch(err){notify('Import stopped: '+err.message,true)}}});
$('menuToggle').addEventListener('click',()=>{if(window.innerWidth>760){document.body.classList.toggle('sidebar-collapsed');return;}const open=$('sidebar').classList.toggle('open');$('sidebarOverlay').hidden=!open});$('sidebarOverlay').addEventListener('click',()=>{$('sidebar').classList.remove('open');$('sidebarOverlay').hidden=true});
render();void refresh();setInterval(async()=>{
  if(state.busy || !state.session.open || !['browser','workflows','projects'].includes(state.page))return;
  try{
    const [session,preview]=await Promise.all([api('/browser/status'),api('/recorder/preview')]);
    const changed=JSON.stringify(state.session)!==JSON.stringify(session)||JSON.stringify(state.preview)!==JSON.stringify(preview);
    notifyNewCapturedSteps(state.session,session,preview);
    state.session=session;state.preview=preview;
    updateRecordingIndicators();
    // Do not replace the entire page on every captured click: that destroys
    // workflow selection, JSON editor state, confirmations and input values.
    // Update only the live recorder area; explicit Refresh performs a full render.
    if(changed){
      const live=$('recorderLive');
      if(live){
        const capture=state.preview||{steps:[],warnings:[]};
        live.innerHTML=`<p class="muted">Actions captured: <strong>${state.session.step_count||0}</strong> · ${state.session.paused?'PAUSED':state.session.recording?'RECORDING':'STOPPED'}</p>`+
          (state.session.warnings?.length?`<div class="callout warn">${state.session.warnings.map(esc).join(' · ')}</div>`:'')+
          (capture.steps?.length?`<div class="top-note"><h4>Live recorded steps (last 50)</h4>${stepTable(capture.steps)}</div>`:'<p class="muted">No recorded actions yet. Click inside the ERP browser while recording.</p>');
      }
      document.querySelectorAll('[data-action="pause-record"]').forEach(b=>b.disabled=!state.session.recording);
      document.querySelectorAll('[data-action="resume-record"]').forEach(b=>b.disabled=!state.session.paused);
      document.querySelectorAll('[data-action="stop-record"]').forEach(b=>b.disabled=!(state.session.recording||state.session.paused));
    }
  }catch(_){}
},900);

// Mirrored Playwright browser: no iframe (ERP websites often disallow embedding).
// Only this localhost UI requests screenshots; keyboard/typing stays in the local backend.
function stopEmbeddedPolling(){if(embeddedTimer){clearInterval(embeddedTimer);embeddedTimer=null}if(embeddedURL){URL.revokeObjectURL(embeddedURL);embeddedURL=null}}
async function refreshEmbeddedImage(){
  if(embeddedFrameInFlight||!$('embeddedImage'))return;
  embeddedFrameInFlight=true;
  try{
    const response=await fetch('/api/browser/embedded/frame',{cache:'no-store'});
    if(!response.ok)throw new Error(`Live viewport HTTP ${response.status}`);
    const next=URL.createObjectURL(await response.blob());
    const img=$('embeddedImage');
    if(!img){URL.revokeObjectURL(next);return}
    const previous=embeddedURL;
    img.src=next;embeddedURL=next;
    $('embeddedLoading')?.remove();
    if(previous)URL.revokeObjectURL(previous);
  }catch(e){const status=$('embeddedScreenStatus');if(status)status.textContent='View refresh: '+e.message}
  finally{embeddedFrameInFlight=false}
}
function startEmbeddedPolling(){void refreshEmbeddedImage();embeddedTimer=setInterval(()=>{if(state.page==='projects'&&state.session.embedded)void refreshEmbeddedImage()},1150)}
function embeddedSend(data){
  embeddedPending=embeddedPending.catch(()=>{}).then(async()=>{
    await api('/browser/embedded/action','POST',data);
    void refreshEmbeddedImage();
  }).catch(error=>notify(error.message,true));return embeddedPending;
}
function embeddedPosition(e,img){
  const box=img.getBoundingClientRect(),w=img.naturalWidth,h=img.naturalHeight;
  if(!w||!h)return null;
  const scale=Math.min(box.width/w,box.height/h);
  const left=box.left+(box.width-w*scale)/2,top=box.top+(box.height-h*scale)/2;
  const x=Math.floor((e.clientX-left)/scale),y=Math.floor((e.clientY-top)/scale);
  if(x<0||y<0||x>=w||y>=h)return null;
  return {x,y};
}
let embeddedClickTimer=null;
document.addEventListener('click',e=>{
  if(e.target?.id!=='embeddedImage')return;
  const pos=embeddedPosition(e,e.target);
  if(!pos)return;
  $('embeddedFocus')?.focus();
  if(embeddedClickTimer){clearTimeout(embeddedClickTimer);embeddedClickTimer=null}
  if(e.detail===1) embeddedClickTimer=setTimeout(()=>{embeddedClickTimer=null;void embeddedSend({kind:'click',...pos})},220);
});
document.addEventListener('dblclick',e=>{
  if(e.target?.id!=='embeddedImage')return;
  e.preventDefault();
  if(embeddedClickTimer){clearTimeout(embeddedClickTimer);embeddedClickTimer=null}
  const pos=embeddedPosition(e,e.target);if(pos)void embeddedSend({kind:'dblclick',...pos});
});
document.addEventListener('wheel',e=>{
  if(!e.target.closest?.('#embeddedFocus'))return;
  e.preventDefault();void embeddedSend({kind:'scroll',delta_y:Math.max(-1200,Math.min(1200,Math.round(e.deltaY)))});
},{passive:false});
document.addEventListener('keydown',e=>{
  if(e.target?.id!=='embeddedFocus')return;
  if(e.ctrlKey||e.metaKey){if(e.key.toLowerCase()==='a'){e.preventDefault();void embeddedSend({kind:'press',key:'ControlOrMeta+A'})}return}
  const shortcuts={ ' ':'Space','Enter':'Enter','Tab':'Tab','Escape':'Escape','Backspace':'Backspace','Delete':'Delete','ArrowUp':'ArrowUp','ArrowDown':'ArrowDown','ArrowLeft':'ArrowLeft','ArrowRight':'ArrowRight','Home':'Home','End':'End','PageUp':'PageUp','PageDown':'PageDown'};
  if(e.key.length===1){e.preventDefault();void embeddedSend({kind:'type',text:e.key})}
  else if(shortcuts[e.key]){e.preventDefault();void embeddedSend({kind:'press',key:shortcuts[e.key]})}
});
document.addEventListener('paste',e=>{
  if(e.target?.id!=='embeddedFocus')return;
  e.preventDefault();const str=e.clipboardData?.getData('text/plain');if(str)void embeddedSend({kind:'type',text:str.slice(0,2048)});
});

if(window.smartERPDesktop){window.smartERPDesktop.onNavigate(page=>{if(NAMES[page])go(page)});window.smartERPDesktop.onRefresh(()=>{void refresh()})}

// SMART_ERP_OPTIONAL_AI_LAB_V636_20261029
