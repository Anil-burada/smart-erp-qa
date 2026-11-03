'use strict';
// Local, editable source files. No browser-uploaded Python is executed implicitly.
const wsState={catalog:[],root:'',selected:'',project:'',modules:[],runs:[],detail:null,active:null,error:'',loading:false};
const dashState={data:null,project:'',error:'',loading:false};
const leocemState={config:null,error:'',positive:true,negative:false};
const casePlanState={plan:null,error:''};
const qaPeriodState={period:'day',date:'',data:null,error:''};
const wsSafe=v=>encodeURIComponent(v||'');
function wsSelected(){return wsState.catalog.find(x=>x.id===wsState.selected);}
function wsProject(){return wsState.project||state.session.project_id||state.projects[0]?.id||'';}
function wsTag(status){const s=String(status||'NOT RUN');const cls=s==='PASSED'?'good':s==='FAILED'||s==='ERROR'?'bad':'';return `<span class="status-pill ${cls}">${esc(s.replaceAll('_',' '))}</span>`;}
function wsModuleList(){return [...new Set(wsState.catalog.map(s=>s.module))];}
function leocemScenarioSwitches(){return `<div class="scenario-choices" role="group" aria-label="Automation mode: choose Positive or Negative, only one can be on">
 <label class="scenario-switch"><input type="checkbox" value="positive" data-leocem-scenario="positive" ${leocemState.positive?'checked':''}><span class="scenario-switch-track" aria-hidden="true"></span><span><strong>Positive scenarios</strong><small>Existing script: Login → PI → approvals → LPO → GRN</small></span></label>
 <label class="scenario-switch"><input type="checkbox" value="negative" data-leocem-scenario="negative" ${leocemState.negative?'checked':''}><span class="scenario-switch-track" aria-hidden="true"></span><span><strong>Negative scenarios</strong><small>Real ERP: Login checks → PI validations → PI approval guard → LPO validations (unsaved)</small></span></label>
 </div>`;}
function leocemKpi(label,count,descriptor,kind){const value=Number(count)||0;return `<article class="leocem-stat ${kind}"><small>${esc(label)}</small><strong data-qa-count="${value}">0</strong><span>${esc(descriptor)}</span></article>`;}
window.qaAnimateNumbers=function(){document.querySelectorAll('[data-qa-count]').forEach(el=>{const n=Number(el.dataset.qaCount)||0;if(matchMedia('(prefers-reduced-motion: reduce)').matches||!n){el.textContent=n;return;}const start=performance.now();const tick=now=>{if(!el.isConnected)return;const t=Math.min(1,(now-start)/550);el.textContent=Math.round(n*(1-Math.pow(1-t,3))).toLocaleString();if(t<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);});};
function evidenceLink(runId,path){const base='/api/script-workspace/runs/'+encodeURIComponent(runId)+'/evidence/'+path.split('/').map(wsSafe).join('/');const preview=/\.(png|pdf)$/i.test(path);return preview?`<button class="btn btn-outline btn-small evidence-preview-action" data-evidence-base="${esc(base)}" data-evidence-title="${esc(path)}" data-evidence-kind="${path.toLowerCase().endsWith('.pdf')?'pdf':'png'}">Preview ${esc(path)}</button>`:`<a class="btn btn-outline btn-small" href="${esc(base)}">Download ${esc(path)}</a>`;}

function scriptPage(){
 const cfg=leocemState.config;const selected=leocemState.negative?(wsState.catalog.find(x=>x.id==='procurement/v636_pi_po_negative.py')||wsSelected()):(cfg?.script||wsSelected());const issues=cfg?.issues||[];
 return `${intro('LEOCEM / SCRIPT','Leocem Script Workspace','Your existing Playwright script is linked to this dashboard. Edit it in VS Code and run the latest SAVED version. No ERP or module selection is required.')}
 <section class="leocem-hero"><span class="eyebrow">FIXED PROJECT • LEOCEM PROCUREMENT</span><h2>Positive or Negative. One Run button.</h2><p>PI → PI approvals → LPO → LPO approvals → GRN</p>
 <div class="leocem-actions"><button class="btn btn-white" data-leocem-run ${wsState.active?'disabled':''}>▶ Run Automation</button><button class="btn btn-hero-outline" data-script="stop" ${!wsState.active?'disabled':''}>Stop</button></div>${leocemScenarioSwitches()}${wsState.active?'<div class="run-indeterminate" role="status" aria-label="Automation running"></div>':''}</section>
 <section class="panel leocem-source"><div class="panel-head"><h3>Linked script — edit in VS Code</h3>${selected?wsTag(selected.valid?'SAVED FILE READY':'SCRIPT ERROR'):''}</div>
 <div class="source-meta"><span>Saved local file (changes are read at the next run)</span><code>${esc(selected?.path||'working_scripts/procurement/pi_lpo_grn.py')}</code><small>Revision: ${esc(selected?.sha256?.slice(0,12)||'unavailable')} • No re-upload needed</small></div>
 <div class="form-actions"><button class="btn btn-outline" data-script="copy">Copy VS Code command</button><button class="btn btn-outline" data-script="refresh">Refresh status</button></div>
 <p class="muted small">${cfg?.url?`Configured TEST/STAGING URL: <strong>${esc(cfg.url)}</strong>`:'Set the authorized Leocem TEST/STAGING URL in your local .env file first.'} Positive uses your saved Python login. Negative uses approved test login accounts (override ERPQA_LEOCEM_NEGATIVE_USERNAME/PASSWORD and ERPQA_LEOCEM_NEGATIVE_PO_USERNAME/PASSWORD in .env only if different).</p>
 ${issues.length?`<div class="qa-alert" role="alert"><strong>Setup required:</strong><ul>${issues.map(i=>`<li>${esc(i)}</li>`).join('')}</ul></div>`:''}
 <details class="source-notes"><summary>Important execution and safety details</summary><p>The first login and later role switching are handled by the script. Approval clicks without verified ERP status are marked Needs review, not Pass. The run can create, submit and approve test records; stopping cannot roll back records. Confirm the saved revision and authorized environment at launch.</p></details></section>
 <div id="wsRunDetail">${wsDetailHtml()}</div>`;
}
function wsDetailHtml(){const d=wsState.detail;if(!d)return '<section class="panel empty"><h3>No script run selected</h3><p>Run your reviewed script or select a report from Reports & Evidence.</p></section>';
 const r=d.run,c=r.counts||{};return `<section class="panel script-live"><div class="panel-head"><div><h3>Live execution & results</h3><p class="muted small">${esc(r.script_id)} · revision ${esc(r.sha256.slice(0,12))}</p></div>${wsTag(r.status)}</div>
 <div class="mini-stats">${[['Passed checks',c.passed||0],['Failed checks',c.failed||0],['Needs review',c.review||0],['Blocked',c.blocked||0]].map(x=>`<div><span>${x[0]}</span><strong>${x[1]}</strong></div>`).join('')}</div>
 <p class="muted small">These are explicit script checks and stages, not a count of every console line or AI-generated test case.</p>
 <div class="form-actions"><a class="btn btn-primary" href="/api/script-workspace/runs/${r.id}/export/html?view=true" target="_blank" rel="noopener">View Test Execution Report</a><a class="btn btn-outline" href="/api/script-workspace/runs/${r.id}/export/xlsx">Download Execution Excel</a><a class="btn btn-outline" href="/api/script-workspace/runs/${r.id}/export/html">Download Execution HTML</a><a class="btn btn-outline" href="/api/script-workspace/runs/${r.id}/export/json">Download JSON</a></div>
 <h4>Execution log</h4><pre class="script-console" id="scriptConsole">${esc(d.log||'Waiting for script output...')}</pre>
 <details open><summary>Recorded checks (${d.checks.length})</summary><div class="suite-table"><table><thead><tr><th>Check</th><th>Result</th><th>Expected</th><th>Actual</th></tr></thead><tbody>${d.checks.map(x=>`<tr><td>${esc(x.name||x.testcase_id)}</td><td>${wsTag(x.status)}</td><td>${esc(x.expected||'—')}</td><td>${esc(x.actual||'—')}</td></tr>`).join('')||'<tr><td colspan="4">No structured checks received yet.</td></tr>'}</tbody></table></div></details>
 <h4>Screenshots, prints & trace</h4><div class="evidence-links">${d.evidence.map(path=>evidenceLink(r.id,path)).join('')||'<p class="muted">No evidence files captured yet.</p>'}</div></section>`;
}
function leocemTestCasesPage(){
 const plan=casePlanState.plan;const cases=plan?.cases||[];
 return `${intro('LEOCEM / TEST CASE REPORT','Test Case Report','Step-by-step planned scenarios: preconditions, actions and expected behavior. This is NOT the actual test execution result.')}
 <section class="panel"><div class="panel-head"><div><h3>Leocem — documented test case steps</h3><p class="muted small">${plan?`${cases.length} defined test cases · Saved script revision ${esc(plan.revision.slice(0,12))}`:'Reading the saved local script...'}</p></div>
 <button class="btn btn-outline btn-small" data-case-plan-refresh="true">Refresh script steps</button></div>
 ${casePlanState.error?`<div class="qa-alert">${esc(casePlanState.error)}</div>`:''}
 <p class="muted small"><strong>Test Case Report = what to test and how to test it.</strong> It lists each numbered step and its expected result. It does not mark test cases Pass or Fail; see the separate <strong>Test Execution Report</strong> for actual results, calculations, PDFs and screenshots.</p>
 <div class="form-actions"><a class="btn btn-primary" href="/api/leocem/test-case-report/html" target="_blank" rel="noopener">View Test Case Report</a>
 <a class="btn btn-outline" href="/api/leocem/test-case-report/xlsx">Download Test Case Report (11 columns)</a><button class="btn btn-outline" data-go="reports">Go to Test Execution Reports</button></div>
 <div class="qa-case-plan-list">${cases.map(c=>`<details class="qa-case-plan-item" ${cases[0]===c?'open':''}><summary><strong>${esc(c.testcase_id)}</strong> · ${esc(c.title)} <small>${esc(c.process)} · ${esc(c.category)}</small></summary>
 <div class="qa-case-plan-body"><p><strong>Precondition:</strong> ${esc(c.precondition)}</p><h4>Test steps</h4><ol>${c.steps.map(step=>`<li>${esc(step)}</li>`).join('')}</ol><p><strong>Expected result:</strong> ${esc(c.expected)}</p><p class="muted small">${c.mapped?'Script functions found. Execution not implied.':'Script mapping needs review: some expected functions are not in the saved file.'}</p></div></details>`).join('')||'<p class="muted">No plan loaded. Click Refresh script steps.</p>'}</div>
 </section>
 ${window.v636CaseHtml?window.v636CaseHtml():''}`;
}
async function loadCasePlan(){try{casePlanState.plan=await api('/leocem/test-case-report/json');casePlanState.error='';}catch(e){casePlanState.error=e.message;}finally{if(state.page==='suite')render();}}
function wsHistoryHtml(){return `<div class="suite-table"><table><thead><tr><th>Started</th><th>Project / script</th><th>Revision</th><th>Status</th><th>Report</th></tr></thead><tbody>${wsState.runs.map(r=>`<tr><td>${esc(new Date(r.started_at).toLocaleString())}</td><td><strong>${esc(r.project_id)}</strong><br>${esc(r.script_id)}</td><td><code>${esc(r.sha256.slice(0,12))}</code></td><td>${wsTag(r.status)}</td><td><a class="btn btn-outline btn-small" href="/api/script-workspace/runs/${r.id}/export/html?view=true" target="_blank" rel="noopener">View Test Execution Report</a></td></tr>`).join('')||'<tr><td colspan="5">No script runs yet. No sample results are shown.</td></tr>'}</tbody></table></div>`;}
function scriptReportsPage(){return `${intro('LEOCEM / REPORTS','Test Reports','Two different documents: Test Case Report explains the planned steps. Test Execution Report shows what the actual run did.')}
 <section class="qa-report-types"><article class="panel"><h3>1. Test Case Report</h3><p class="muted">Step-by-step test design: preconditions, test actions and expected results. No Pass/Fail claims.</p><div class="form-actions"><a class="btn btn-primary" href="/api/leocem/test-case-report/html" target="_blank" rel="noopener">View Test Case Report</a><a class="btn btn-outline" href="/api/leocem/test-case-report/xlsx">Download Test Case Excel</a></div></article>
 <article class="panel"><h3>2. Test Execution Report</h3><p class="muted">Actual performed checks and ERP results, expected versus actual values, approval status, logs and screenshot/PDF evidence for each run.</p>${wsState.runs.length?`<div class="form-actions"><a class="btn btn-primary" href="/api/script-workspace/runs/${wsState.runs[0].id}/export/html?view=true" target="_blank" rel="noopener">View Latest Execution Report</a><a class="btn btn-outline" href="/api/script-workspace/runs/${wsState.runs[0].id}/export/xlsx">Download Execution Excel</a></div>`:'<p>No automation run has been recorded.</p>'}</article></section>
 <section class="panel"><div class="panel-head"><h3>Test Execution History</h3><button class="btn btn-outline" data-script="refresh">Refresh reports</button></div>${wsHistoryHtml()}</section><div id="wsRunDetail">${wsDetailHtml()}</div><details class="legacy-reports"><summary>Recorded-workflow analytics</summary>${qaOverview()}</details>`;}
async function wsLoad(){if(wsState.loading)return;wsState.loading=true;try{
 const [cat,h,cfg]=await Promise.all([api('/script-workspace/catalog'),api('/script-workspace/runs'),api('/leocem/ready')]);
 wsState.catalog=cat.scripts;wsState.root=cat.root;wsState.runs=h.runs;wsState.active=h.active_id;
 wsState.selected='procurement/pi_lpo_grn.py';leocemState.config=cfg;wsState.error='';
 if(!wsState.detail&&h.runs.length)wsState.detail=await api('/script-workspace/runs/'+h.runs[0].id);
 }catch(e){wsState.error=e.message;leocemState.error=e.message;}
 finally{wsState.loading=false;if(['scripts','reports','suite'].includes(state.page))render();}}
async function wsAction(action){try{
 if(action==='refresh'){await wsLoad();return;}
 if(action==='copy'){const s=wsSelected();if(s){await navigator.clipboard.writeText(`code "working_scripts/${s.id}"`);notify('VS Code command copied. Run it from the extracted project root in PowerShell.');}return;}
 if(action==='stop'){if(confirm('Stop the running script? ERP records already saved are NOT rolled back.')){await api('/script-workspace/stop','POST',{});notify('Stop requested. Check the ERP before retrying.');}return;}
 const project=$('wsProject')?.value||wsProject();if(!project)throw Error('Select your TEST or STAGING ERP application first.');
 if(action==='analyze'){const s=wsSelected();if(!s)throw Error('Choose a source file');const result=await api('/script-workspace/analyze','POST',{script_id:s.id,project_id:project,reviewed_sha256:s.sha256});suiteProject=project;go('suite');notify('Saved revision analyzed. Select '+result.stored_filename+' in AI Drafts.');return;}
 if(action==='run'){
  if(!$('wsTrust')?.checked||!$('wsWrites')?.checked)throw Error('Review the local code and authorize TEST/STAGING transactions first.');
  const mode=$('wsMode').value;const role=!!$('wsRole')?.checked;
  if(mode==='existing'&&!role)throw Error('Confirm the initial logged-in account for this procurement script.');
  const cat=await api('/script-workspace/catalog');const s=cat.scripts.find(x=>x.id===wsState.selected);if(!s||!s.valid)throw Error(s?.error||'Script is unavailable.');
  if(!confirm(`Run the latest SAVED revision ${s.sha256.slice(0,12)} of ${s.filename}?\n\nThis script can create, submit and approve ERP records and change roles. Unsaved VS Code edits are not included. Review code changes before confirming.`))return;
  const r=await api('/script-workspace/run','POST',{project_id:project,script_id:s.id,reviewed_sha256:s.sha256,mode,trust_local_code:true,allow_test_transactions:true,initial_role_confirmed:role});
  wsState.active=r.id;wsState.detail=await api('/script-workspace/runs/'+r.id);wsState.catalog=cat.scripts;render();notify('Script started. Live logs and actual checks appear below.');
 }
 }catch(e){notify(e.message,true);}}
async function leocemRunClick(){
 try{
  if(wsState.active)throw Error('A script is already running. Open Reports to follow its execution.');
  // The original toggle cards are mutually exclusive; server also validates the mode.
  if(leocemState.positive===leocemState.negative)throw Error('Choose Positive or Negative, not both.');
  const negative=leocemState.negative;
  const cfg=await api(negative?'/v636-cases/negative-ready':'/leocem/ready');
  if(!cfg.ready)throw Error((cfg.issues||[]).join(' '));
  const script=cfg.script;
  if(!script||!script.valid)throw Error('The reviewed Python source is unavailable or invalid.');
  if(negative&&!script.supports_negative)throw Error('The negative script has no executable negative test function.');
  const warning=negative
   ?`Run NEGATIVE Login → PI → Approval Guard → LPO checks against the authorized ${cfg.environment.toUpperCase()} ERP?\n\nNo Purchase Indent, PO or GRN document will be saved, submitted or approved. These checks use unsaved forms and may be BLOCKED/REVIEW when a field requires Save for validation.\n\nURL: ${cfg.url}\nNegative script revision: ${script.sha256.slice(0,12)}\n\nReview the saved script and test role. Press OK to run.`
   :`Run the POSITIVE PI → LPO → GRN script against authorized ${cfg.environment.toUpperCase()} ERP?\n\nThis may CREATE, SUBMIT and APPROVE test records. Stopping will not roll back transactions.\n\nURL: ${cfg.url}\nSaved source revision: ${script.sha256.slice(0,12)}\n\nPress OK only if you reviewed the saved script.`;
  if(!confirm(warning))return;
  const run=negative
    ?await api('/v636-cases/negative-run','POST',{reviewed_sha256:script.sha256,acknowledge_test_transactions:true,acknowledge_trusted_code:true})
    :await api('/leocem/run','POST',{reviewed_sha256:script.sha256,acknowledge_test_transactions:true,acknowledge_trusted_code:true,positive_scenarios:true,negative_scenarios:false});
  wsState.active=run.id;wsState.selected=cfg.script_id;wsState.detail=await api('/script-workspace/runs/'+run.id);
  await wsLoad();go('scripts');notify((negative?'Negative Login to LPO':'Positive PI/LPO/GRN')+' automation started. See Expected vs Actual results.');
 }catch(e){notify(e.message,true);if(state.page==='scripts')render();}
}
document.addEventListener('click',event=>{
 if(event.target.closest('[data-case-plan-refresh]')){event.preventDefault();void loadCasePlan();return;}
 const proof=event.target.closest('[data-evidence-base]');
 if(proof){event.preventDefault();const overlay=document.getElementById('evidenceOverlay');
   if(!overlay)return;const base=proof.dataset.evidenceBase,title=proof.dataset.evidenceTitle,kind=proof.dataset.evidenceKind;
   document.getElementById('evidenceHeading').textContent=title;
   const area=document.getElementById('evidenceViewer');area.replaceChildren();let element;
   if(kind==='pdf'){element=document.createElement('iframe');element.title='Annotated print PDF';}
   else{element=document.createElement('img');element.alt='ERP validation evidence with recorded red annotations';}
   element.src=base+'?preview=true';area.appendChild(element);
   document.getElementById('evidenceDownload').href=base;
   document.getElementById('evidenceFullSize').href=base+'?preview=true';
   overlay.hidden=false;document.getElementById('evidenceClose').focus();return;
 }
 if(event.target.closest('[data-evidence-close]')){const overlay=document.getElementById('evidenceOverlay');overlay.hidden=true;document.getElementById('evidenceViewer').replaceChildren();return;}
 const button=event.target.closest('[data-leocem-run]');
 if(button){event.preventDefault();void leocemRunClick();}
});
document.addEventListener('click',e=>{const button=e.target.closest('[data-script]');if(button){e.preventDefault();void wsAction(button.dataset.script);return;}const module=e.target.closest('[data-script-module]');if(module){const m=module.dataset.scriptModule;wsState.modules=wsState.modules.includes(m)?wsState.modules.filter(x=>x!==m):[...wsState.modules,m];render();return;}const choice=e.target.closest('[data-script-id]');if(choice){wsState.selected=choice.dataset.scriptId;render();return;}const report=e.target.closest('[data-script-report]');if(report){void(async()=>{try{wsState.detail=await api('/script-workspace/runs/'+report.dataset.scriptReport);go('reports');}catch(err){notify(err.message,true);}})();}});
document.addEventListener('change',e=>{
 if(e.target.id==='qaPeriod'){qaPeriodState.period=e.target.value;void loadQaPeriod();return;}
 if(e.target.id==='qaAnalysisDate'){qaPeriodState.date=e.target.value;void loadQaPeriod();return;}
 if(e.target.matches('[data-leocem-scenario]')){const mode=e.target.dataset.leocemScenario;leocemState.positive=mode==='positive';leocemState.negative=mode==='negative';render();return;}if(e.target.id==='wsProject')wsState.project=e.target.value;if(e.target.id==='dashboardProject'){dashState.project=e.target.value;void dashboardLoad();}});
setInterval(async()=>{if(!['scripts','reports','overview'].includes(state.page))return;try{const h=await api('/script-workspace/runs');wsState.active=h.active_id;wsState.runs=h.runs;const id=wsState.detail?.run.id||h.active_id;if(id&&['scripts','reports'].includes(state.page)){wsState.detail=await api('/script-workspace/runs/'+id);const target=$('wsRunDetail');if(target){const oldScroll=$('scriptConsole')?.scrollTop||0;target.innerHTML=wsDetailHtml();if($('scriptConsole'))$('scriptConsole').scrollTop=oldScroll;}document.querySelectorAll('[data-script="stop"]').forEach(b=>b.disabled=!h.active_id);document.querySelectorAll('[data-script="run"]').forEach(b=>b.disabled=!!h.active_id||!wsSelected()?.valid);}}catch(e){/* keep visible report; next explicit refresh exposes errors */}},2500);
function qaPieMarkup(){
 const summary=qaPeriodState.data,period=qaPeriodState.period;
 const values=[['Passed',Number(summary?.passed)||0,'#15a979'],['Failed',Number(summary?.failed)||0,'#ec6272'],['Needs review',Number(summary?.review)||0,'#f3b65d'],['Blocked',Number(summary?.blocked)||0,'#7b90af']];
 const total=values.reduce((n,x)=>n+x[1],0);let pos=0;
 const ranges=values.filter(x=>x[1]>0).map(x=>{const start=pos;pos+=100*x[1]/total;return `${x[2]} ${start.toFixed(3)}% ${pos.toFixed(3)}%`;});
 const gradient=total?`conic-gradient(from -90deg,${ranges.join(',')})`:'conic-gradient(#d9e2f0 0 100%)';
 const r=summary?.runs||[];
 const date=qaPeriodState.date||summary?.date||'';
 return `<section class="qa-analytics-panel panel" aria-label="Time-filtered test execution analysis">
 <div class="qa-analytics-head"><div><span class="eyebrow">LIVE QA ANALYTICS · IST</span><h2>Pass / Fail Test Analysis</h2><p class="muted small">Verified script checks; unverified or blocked checks are shown separately, not counted as Pass.</p></div>
 <div class="qa-date-controls"><label>Report period<select id="qaPeriod" aria-label="Report period"><option value="day" ${period==='day'?'selected':''}>Daily report</option><option value="week" ${period==='week'?'selected':''}>Weekly report</option><option value="month" ${period==='month'?'selected':''}>Monthly report</option></select></label><label>Select date<input id="qaAnalysisDate" aria-label="Select report date" type="date" value="${esc(date)}"></label></div></div>
 <p class="qa-generated-time">${summary?`Report: ${esc(summary.start.slice(0,10))} to ${esc(new Date(new Date(summary.end_exclusive).getTime()-86400000).toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'}))} · Generated ${esc(new Date(summary.generated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'medium'}))} IST`:'Loading verified run data…'}</p>
 ${qaPeriodState.error?`<p class="qa-alert">${esc(qaPeriodState.error)}</p>`:''}
 <div class="qa-pie-layout"><div class="qa-pie-viz" role="img" aria-label="${esc(values.map(v=>v[0]+': '+v[1]).join(', '))}"><div class="qa-pie-stack" style="--qa-pie-fill:${esc(gradient)}"><div class="qa-pie-depth"></div><div class="qa-pie-top"></div></div>${total?'<span class="qa-chart-caption">Actual results</span>':'<span class="qa-chart-caption">No recorded checks for this period</span>'}</div>
 <div class="qa-pie-summary"><strong class="qa-pie-total">${total.toLocaleString()}</strong><span class="muted">Total recorded checks</span><div class="qa-pie-legend">${values.map(v=>`<div><i style="background:${v[2]}"></i><span>${v[0]}</span><strong>${v[1].toLocaleString()}</strong></div>`).join('')}</div><p class="muted small">${summary?.run_count||0} script run(s) started in this selected period.</p></div></div>
 <div class="qa-analytics-detail"><h3>Passed and Failed Report</h3><p class="muted small">Per-run results for the selected ${esc(period)}. All timestamps are India Standard Time (IST). Click to open the detailed Test Execution Report.</p><div class="qa-run-summary-wrap"><table class="qa-run-summary"><thead><tr><th>Run timestamp (IST)</th><th>Run status</th><th>Passed</th><th>Failed</th><th>Needs review</th><th>Blocked</th><th>Report</th></tr></thead><tbody>${r.map(x=>`<tr><td>${esc(new Date(x.started_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'}))}</td><td>${wsTag(x.status)}</td><td>${x.passed}</td><td>${x.failed}</td><td>${x.review}</td><td>${x.blocked}</td><td><a class="btn btn-outline btn-small" target="_blank" rel="noopener" href="/api/script-workspace/runs/${esc(x.id)}/export/html?view=true">View report</a></td></tr>`).join('')||'<tr><td colspan="7">No recorded Leocem automation runs in this date range.</td></tr>'}</tbody></table></div></div>
 </section>`;
}

function automationOverview(){
 const d=dashState.data,c=d?.latest_script_checks||{};const latest=d?.latest_script,cfg=leocemState.config;
 return `${intro('LEOCEM / QA DASHBOARD','Smart ERP QA Dashboard','Run your saved Leocem Playwright script, review testcase results and download reports. No ERP selection needed.')}
 <section class="leocem-hero dashboard-hero"><div class="eyebrow">LEOCEM PROCUREMENT • PYTHON + PLAYWRIGHT</div><h1>Run your Leocem automation</h1><p>The supplied PI → LPO → GRN script runs directly when you press the button. Edit and save it in VS Code any time; the next run picks up your changes.</p>
 <div class="leocem-actions"><button class="btn btn-white" data-leocem-run ${wsState.active?'disabled':''}>▶ Run Automation</button><button class="btn btn-hero-outline" data-go="scripts">Script Workspace</button></div>${leocemScenarioSwitches()}${wsState.active?'<div class="run-indeterminate" role="status">Running your approved script...</div>':''}
 <div class="hero-status">${wsState.active?'RUNNING — watch the Script Workspace':cfg?.ready?'CONFIGURED • TEST/STAGING': 'SETUP REQUIRED • See Script Workspace'}</div></section>
 ${dashState.error?`<div class="qa-alert">${esc(dashState.error)}</div>`:''}
 <div class="section-title-row"><div><h2 class="subheading">Latest automation execution summary</h2><p class="muted small">Real checks from your latest Leocem Playwright run. Download the 11-column Excel under Test Cases &amp; Excel.</p></div></div>
 <section class="dashboard-kpis leocem-kpis">${[['Total script runs',d?.script_run_count||0,'Recorded runs (latest 100)','neutral'],['Total test cases run',c.total||0,'Actual script checks','neutral'],['Passed',c.passed||0,'Verified checks','passed'],['Failed',c.failed||0,'Failed validations','failed'],['Needs review',c.review||0,'Unverified checks','review']].map(x=>leocemKpi(...x)).join('')}</section>
 ${qaPieMarkup()}
 <section class="leocem-simple-grid"><div class="panel"><div class="panel-head"><h3>Latest script run</h3><button class="btn btn-outline btn-small" data-go="reports">View reports</button></div>${latest?`<p><strong>${esc(latest.run.script_id)}</strong> ${wsTag(latest.run.status)}</p><p class="muted small">Saved revision ${esc(latest.run.sha256.slice(0,12))}</p><div class="mini-stats">${[['Passed',latest.run.counts.passed],['Failed',latest.run.counts.failed],['Review',latest.run.counts.review],['Blocked',latest.run.counts.blocked]].map(x=>`<div><span>${x[0]}</span><strong>${x[1]||0}</strong></div>`).join('')}</div><div class="form-actions"><a class="btn btn-outline btn-small" href="/api/script-workspace/runs/${latest.run.id}/export/html?view=true" target="_blank" rel="noopener">View Test Execution Report</a><a class="btn btn-outline btn-small" href="/api/script-workspace/runs/${latest.run.id}/export/xlsx">Download Execution Excel</a></div>`:'<p class="muted">No script execution has been recorded yet.</p>'}</div>
 <div class="panel"><div class="panel-head"><h3>Recent test cases</h3><button class="btn btn-outline btn-small" data-go="reports">View execution checks</button></div><div class="suite-table"><table><thead><tr><th>Test case</th><th>Result</th></tr></thead><tbody>${(d?.recent_script_checks||[]).slice(0,5).map(x=>`<tr><td>${esc(x.name||x.testcase_id)}<small class="muted"> · ${esc(x.testcase_id)}</small></td><td>${wsTag(x.status)}</td></tr>`).join('')||'<tr><td colspan="2">No testcases executed yet.</td></tr>'}</tbody></table></div></div></section>`;
}
async function loadQaPeriod(update=true){
 try{
  const query=new URLSearchParams({period:qaPeriodState.period});
  if(qaPeriodState.date)query.set('date',qaPeriodState.date);
  qaPeriodState.data=await api('/leocem/dashboard/summary?'+query.toString());
  qaPeriodState.date=qaPeriodState.data.date;
  qaPeriodState.error='';
 }catch(error){qaPeriodState.error=error.message;}
 if(update&&state.page==='overview')render();
}
async function dashboardLoad(){if(dashState.loading)return;dashState.loading=true;try{
 const cfg=await api('/leocem/ready');leocemState.config=cfg;
 dashState.project=cfg.project_id;
 dashState.data=await api('/automation-dashboard?leocem_only=true');dashState.error='';
 await loadQaPeriod(false);
 if(state.page==='suite') await loadCasePlan();
 }catch(e){dashState.error=e.message;}finally{dashState.loading=false;if(['overview','suite'].includes(state.page))render();}}

// Refresh latest real test totals when a running script finishes; no fake counts.
setInterval(async()=>{if(state.page!=='overview')return;try{const res=await api('/script-workspace/runs');const top=res.runs?.[0];const old=dashState.data?.latest_script?.run;const oldCount=dashState.data?.latest_script_checks?.total||0;if(top&&(top.id!==old?.id||top.status!==old?.status||res.active_id!==wsState.active)){wsState.active=res.active_id;await dashboardLoad();}else if(res.active_id&&top){await dashboardLoad();}}catch(e){}},4000);

document.addEventListener('keydown',e=>{if(e.key==='Escape'){const overlay=document.getElementById('evidenceOverlay');if(overlay&&!overlay.hidden){overlay.hidden=true;document.getElementById('evidenceViewer').replaceChildren();}}});
