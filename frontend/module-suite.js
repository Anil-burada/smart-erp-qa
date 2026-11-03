'use strict';
// v6.2.8: project -> module chips -> process chips -> test cases -> run.
let suiteCatalog={workflows:[],scripts:[]},suiteCases=[],suiteMetrics={};
let suiteProject='',suiteModules=[],suiteProcesses=[],suiteChosenCases=[];
let suiteMostRecent=null;
const suiteCode=v=>encodeURIComponent(v||'');
function suiteProjects(){return state.projects||[];}
function suiteModulesFound(){return [...new Set([...suiteCatalog.workflows.map(x=>x.module),...suiteCatalog.scripts.map(x=>x.module),...suiteCases.map(x=>x.module)].filter(x=>x&&x!=='Unassigned'))].sort();}
function suiteProcessesFound(){return [...new Set([...suiteCatalog.workflows,...suiteCatalog.scripts,...suiteCases].filter(x=>suiteModules.includes(x.module)&&x.process&&x.process!=='Unassigned').map(x=>x.process))].sort();}
function suiteMatchingCases(){return suiteCases.filter(c=>(!suiteModules.length||suiteModules.includes(c.module))&&(!suiteProcesses.length||suiteProcesses.includes(c.process)));}
function suiteChip(name,kind,checked){return `<label class="suite-chip ${checked?'active':''}"><input class="suite-chip-input" type="checkbox" data-suite-kind="${kind}" value="${esc(name)}" ${checked?'checked':''}><span class="suite-check">${checked?'✓':'+'}</span>${esc(name)}</label>`;}
function suiteStatus(c){return c==='PASSED'?'<span class="suite-status ok">PASS</span>':c==='FAILED'?'<span class="suite-status error">FAIL</span>':c==='BLOCKED'?'<span class="suite-status warn">BLOCKED</span>':'<span class="suite-status muted">NOT RUN</span>';}
function suitePage(){
 const proj=suiteProject||state.session.project_id||suiteProjects()[0]?.id||'';
 const modules=suiteModulesFound(),processes=suiteProcessesFound(),shown=suiteMatchingCases();
 const selectedShown=shown.filter(c=>suiteChosenCases.includes(c.testcase_id));
 const projectsOptions=suiteProjects().map(p=>`<option value="${esc(p.id)}" ${proj===p.id?'selected':''}>${esc(p.name)} — ${esc(p.environment)}</option>`).join('');
 const assigned=suiteCatalog.workflows.filter(x=>x.module!=='Unassigned');
 return `${intro('MODULES / AI / EXCEL','Module Tests & Test Case Manager','One ERP project at a time. Select multiple modules and processes using skills-style chips, then run all approved cases or only the cases you checked.')}
 <div class="suite-top panel">
   <div class="suite-title-row"><div><h3>1. Select one ERP project</h3><p class="muted">Only modules belonging to this ERP are shown.</p></div><span class="suite-accent">APPROVED TEST CASES</span></div>
   <div class="project-tools"><select class="search" id="suiteProject"><option value="">Select ERP project</option>${projectsOptions}</select><button class="btn btn-outline" data-action="suite-refresh">Refresh</button><button class="btn btn-primary" data-go="projects">Open ERP / Login</button></div>
   <p class="suite-note">Current live browser: <strong>${esc(state.session.open?state.session.project_id:'Not open')}</strong> · The automation uses that same authenticated session and does not restart login.</p>
 </div>
 <div class="metrics suite-metrics">
  ${[['Total cases',suiteMetrics.total||0,'◫'],['Passed',suiteMetrics.passed||0,'✓'],['Failed',suiteMetrics.failed||0,'!'],['Blocked / Not run',(suiteMetrics.blocked||0)+(suiteMetrics.not_run||0),'•']].map(x=>`<div class="metric"><span class="metric-dot">${x[2]}</span><div class="metric-label">${x[0]}</div><div class="metric-value">${x[1]}</div></div>`).join('')}
 </div>
 <section class="panel suite-section"><div class="suite-title-row"><div><h3>2. Select modules</h3><p class="muted">Select one or several modules, similar to skills selection.</p></div><span class="tag">${suiteModules.length} chosen</span></div>
 <div class="suite-chip-wrap">${modules.length?modules.map(m=>suiteChip(m,'module',suiteModules.includes(m))).join(''):'<span class="muted">No module assignments yet. Assign an approved workflow below.</span>'}</div>
 <div class="suite-title-row"><div><h3>3. Select processes</h3><p class="muted">Leave all processes unchecked to run all processes in selected modules.</p></div><span class="tag">${suiteProcesses.length} selected</span></div>
 <div class="suite-chip-wrap">${suiteModules.length?processes.map(x=>suiteChip(x,'process',suiteProcesses.includes(x))).join('')||'<span class="muted">No processes for selected modules.</span>':'<span class="muted">Choose a module first.</span>'}</div></section>
 <section class="panel suite-section"><div class="suite-title-row"><div><h3>4. Excel test cases</h3><p class="muted">Your exact 11 columns are preserved. Choose all approved cases or only checked rows.</p></div><span class="tag">${shown.length} shown</span></div>
 <div class="form-actions"><a class="btn btn-outline" href="/api/suite/excel/${suiteCode(proj)}?template=true">Download Excel Template</a><a class="btn btn-outline" href="/api/suite/excel/${suiteCode(proj)}">Download Test Cases</a><input type="file" id="suiteExcelFile" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" class="suite-file"><button class="btn btn-primary" data-action="suite-import">Upload Edited Excel</button></div>
 <div class="suite-table"><table><thead><tr><th><input id="suiteAllCases" type="checkbox" title="Select displayed test cases"></th><th>Test case ID</th><th>Module / Process</th><th>Scenario / Testcase</th><th>Type</th><th>Approved</th><th>Status</th></tr></thead><tbody>
 ${shown.length?shown.map(c=>`<tr><td><input class="suite-case-check" data-suite-id="${esc(c.testcase_id)}" type="checkbox" ${suiteChosenCases.includes(c.testcase_id)?'checked':''}></td><td><strong>${esc(c.testcase_id)}</strong></td><td>${esc(c.module)}<div class="muted">${esc(c.process)}</div></td><td>${esc(c.scenario)}<div class="muted">${esc(c.title)}</div></td><td>${esc(c.category)}</td><td>${c.approved?'<span class="suite-status ok">Approved</span>':'<span class="suite-status warn">Needs review</span>'}</td><td>${suiteStatus(c.status)}</td></tr>`).join(''):'<tr><td colspan="7" class="muted">Upload Excel or generate testcase drafts from a script to populate this table.</td></tr>'}</tbody></table></div>
 <div class="form-actions"><button class="btn btn-outline" data-action="suite-approve">Approve Checked</button><button class="btn btn-outline" data-action="suite-revoke">Revoke Approval</button><button class="btn btn-primary" data-action="suite-run-all" ${!suiteModules.length?'disabled':''}>Run All Approved in Selection</button><button class="btn btn-primary" data-action="suite-run-selected" ${!selectedShown.length?'disabled':''}>Run Checked Cases (${selectedShown.length})</button></div>
 <label class="suite-check-confirm"><input type="checkbox" id="suiteWrites"> I authorize record-changing actions on TEST/STAGING ERP (Save, Submit, Approve).</label>
 <p class="suite-note">Negative, boundary, and role scenarios are not treated as passed simply because a happy-path script completed. They need specific reviewed test data and assertions; unsupported cases show Blocked.</p></section>
 <section class="panel suite-section"><div class="suite-title-row"><div><h3>5. Assign workflows to modules and processes</h3><p class="muted">Existing reviewed JSON workflows are the executable automation. Names are configurable; no code rewrite for basic grouping.</p></div><span class="tag">${assigned.length} assigned</span></div>
 <div class="form-grid"><div class="field"><label>Existing workflow</label><select id="suiteMapWorkflow">${suiteCatalog.workflows.map(w=>`<option value="${esc(w.workflow_name)}">${esc(w.workflow_name)} ${w.reviewed?'✓ reviewed':'· draft'}</option>`).join('')}</select></div>
 <div class="field"><label>Module name</label><input id="suiteMapModule" placeholder="Procurement" value="Procurement"></div>
 <div class="field"><label>Process name</label><input id="suiteMapProcess" placeholder="Purchase Requisition" value="Purchase Requisition"></div></div>
 <button class="btn btn-primary top-note" data-action="suite-map">Save Workflow Assignment</button>
 <div class="suite-chip-wrap">${assigned.map(w=>`<span class="suite-map-tag">${esc(w.module)} · ${esc(w.process)} → ${esc(w.workflow_name)}</span>`).join('')}</div></section>
 <section class="panel suite-section"><div class="suite-title-row"><div><h3>6. AI test-case drafts from Python</h3><p class="muted">For executable local Python, use Script Workspace. This upload is analyzed without executing its code. AI/rule drafts require manual review and an approved workflow mapping before replay.</p></div><span class="suite-accent">SCRIPT LIBRARY</span></div>
 <div class="form-grid"><div class="field"><label>Python .py script</label><input type="file" id="suiteScriptFile" accept=".py,text/x-python"></div><div class="field"><label>Module</label><input id="suiteScriptModule" value="Procurement"></div><div class="field"><label>Process</label><input id="suiteScriptProcess" value="Purchase Requisition"></div></div>
 <button class="btn btn-outline top-note" data-action="suite-script-upload">Analyze & Store Script</button>
 <div class="form-grid"><div class="field"><label>Analyzed script</label><select id="suiteScriptSelect">${suiteCatalog.scripts.map(s=>`<option value="${esc(s.filename)}">${esc(s.module)} / ${esc(s.process)} · ${esc(s.filename)}</option>`).join('')}</select></div><div class="field"><label>Testcase suggestions provider</label><select id="suiteProvider"><option value="rules">Offline rules (no API)</option><option value="openai">OpenAI API</option><option value="ollama">Local Ollama</option></select></div></div>
 <button class="btn btn-primary top-note" data-action="suite-generate">Generate Testcase Drafts</button></section>
 <section class="panel suite-section"><div class="suite-title-row"><div><h3>Recent test case results</h3><p class="muted">Only actual recorded executions can be Pass or Fail.</p></div><span class="tag">${(suiteMetrics.recent||[]).length} recent</span></div>
 ${suiteMostRecent?`<div class="suite-note"><strong>Run #${suiteMostRecent.run_id}: ${esc(suiteMostRecent.status)}</strong> · Passed ${suiteMostRecent.passed}, Failed ${suiteMostRecent.failed}, Blocked ${suiteMostRecent.blocked}</div>`:''}
 <div class="suite-table"><table><thead><tr><th>Case ID</th><th>Workflow</th><th>Result</th><th>Evidence</th></tr></thead><tbody>${(suiteMetrics.recent||[]).map(r=>`<tr><td>${esc(r.testcase_id)}</td><td>${esc(r.workflow_name)}</td><td>${suiteStatus(r.status)}<div class="muted">${esc(r.actual).slice(0,170)}</div></td><td>${r.screenshot?`<a target="_blank" rel="noopener" href="/api/suite/evidence/${r.id}/screenshot">Screenshot</a>`:''} ${r.trace?`<a href="/api/suite/evidence/${r.id}/trace">Trace</a>`:''} ${r.report_path?`<a href="/api/suite/evidence/${r.id}/report_path">JSON Report</a>`:''}</td></tr>`).join('')||'<tr><td colspan="4" class="muted">No suite executions yet.</td></tr>'}</tbody></table></div></section>`;
}
async function loadSuite(){
 const chosen=suiteProject||state.session.project_id||suiteProjects()[0]?.id||'';
 if(!chosen){render();return;}
 suiteProject=chosen;
 try{
  const [cat,cases,metrics]=await Promise.all([api('/suite/catalog/'+suiteCode(chosen)),api('/suite/cases/'+suiteCode(chosen)),api('/suite/metrics/'+suiteCode(chosen))]);
  suiteCatalog=cat;suiteCases=cases;suiteMetrics=metrics;
  suiteModules=suiteModules.filter(m=>suiteModulesFound().includes(m));
  suiteProcesses=suiteProcesses.filter(p=>suiteProcessesFound().includes(p));
  suiteChosenCases=suiteChosenCases.filter(id=>suiteCases.some(c=>c.testcase_id===id));
  if(state.page==='suite')render();
 }catch(e){notify('Module Runner: '+e.message,true);}
}
async function suiteMultipart(path,form){
 const response=await fetch('/api'+path,{method:'POST',body:form});
 const data=await response.json().catch(()=>({detail:'Request failed'}));
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
 return data;
}
async function suiteAction(action){
 const pid=suiteProject;
 if(!pid)throw new Error('Select an ERP project first');
 if(action==='suite-refresh'){await loadSuite();return;}
 if(action==='suite-map'){
  const name=$('suiteMapWorkflow')?.value;
  if(!name)throw new Error('No workflow exists for this ERP. Record/save one first.');
  await api(`/suite/catalog/${suiteCode(pid)}/${suiteCode(name)}`,'PUT',{module:$('suiteMapModule').value,process:$('suiteMapProcess').value});
  suiteModules=[];suiteProcesses=[];await loadSuite();notify('Module and process assignment saved');return;
 }
 if(action==='suite-import'){
  const f=$('suiteExcelFile')?.files?.[0];if(!f)throw new Error('Choose a .xlsx workbook');
  const form=new FormData();form.append('workbook',f);
  const result=await suiteMultipart(`/suite/excel/${suiteCode(pid)}/import`,form);
  suiteChosenCases=[];await loadSuite();notify(`Imported ${result.imported} test cases. Review and approve before running.`);return;
 }
 if(action==='suite-script-upload'){
  const f=$('suiteScriptFile')?.files?.[0];if(!f)throw new Error('Choose your existing .py Playwright script');
  const form=new FormData();form.append('script',f);form.append('project_id',pid);
  form.append('module',$('suiteScriptModule').value);form.append('process',$('suiteScriptProcess').value);
  const res=await suiteMultipart('/suite/scripts/upload',form);
  await loadSuite();notify(`Script analyzed: ${res.analysis.action_count} Playwright-related calls; no script executed`);return;
 }
 if(action==='suite-generate'){
  const filename=$('suiteScriptSelect')?.value;if(!filename)throw new Error('Upload a Python script first');
  const provider=$('suiteProvider').value;
  if(provider==='openai'&&!confirm('Send only sanitized Python action names (not code, credentials, DOM, URLs or values) to the configured OpenAI model?'))return;
  const res=await api('/suite/scripts/generate','POST',{project_id:pid,filename,provider});
  await loadSuite();notify(`${res.draft_ids.length} ${provider} test case drafts created. Review and approve.`);return;
 }
 if(['suite-approve','suite-revoke'].includes(action)){
  if(!suiteChosenCases.length)throw new Error('Select test case checkboxes first');
  const approved=action==='suite-approve';
  const r=await api('/suite/cases/approve','POST',{project_id:pid,testcase_ids:suiteChosenCases,approve:approved});
  suiteChosenCases=[];await loadSuite();notify(`${r.updated} test cases ${approved?'approved':'returned to review'}`);return;
 }
 if(action==='suite-run-all'||action==='suite-run-selected'){
  if(!suiteModules.length)throw new Error('Select one or more module chips first');
  const selected=action==='suite-run-selected'?suiteChosenCases:[];
  if(action==='suite-run-selected'&&!selected.length)throw new Error('Check one or more test cases');
  if(!state.session.open||state.session.project_id!==pid)throw new Error(`Open ERP ${pid} and log in manually first; the browser session will be reused.`);
  const allowWrites=!!$('suiteWrites')?.checked;
  if(!confirm(`Execute ${selected.length?selected.length+' checked cases':'all approved cases'} for ${suiteModules.join(', ')} in CURRENT logged-in ERP?\n\nThis will not open a new login page.${allowWrites?'\nTEST/STAGING transactions are enabled.':''}`))return;
  const result=await api('/suite/run','POST',{project_id:pid,modules:suiteModules,processes:suiteProcesses,testcase_ids:selected,allow_test_transactions:allowWrites});
  suiteMostRecent=result;await refresh();await loadSuite();notify(`Suite #${result.run_id}: ${result.passed} Pass / ${result.failed} Fail / ${result.blocked} Blocked`,result.failed>0);return;
 }
}
document.addEventListener('change',async e=>{
 if(e.target.id==='suiteProject'){
  suiteProject=e.target.value;suiteModules=[];suiteProcesses=[];suiteChosenCases=[];suiteMostRecent=null;await loadSuite();return;
 }
 if(e.target.dataset.suiteKind==='module'){
  const m=e.target.value;suiteModules=e.target.checked?[...suiteModules,m]:suiteModules.filter(x=>x!==m);
  suiteProcesses=suiteProcesses.filter(x=>suiteProcessesFound().includes(x));suiteChosenCases=[];render();return;
 }
 if(e.target.dataset.suiteKind==='process'){
  const m=e.target.value;suiteProcesses=e.target.checked?[...suiteProcesses,m]:suiteProcesses.filter(x=>x!==m);
  suiteChosenCases=[];render();return;
 }
 if(e.target.classList?.contains('suite-case-check')){
  const id=e.target.dataset.suiteId;
  suiteChosenCases=e.target.checked?[...new Set([...suiteChosenCases,id])]:suiteChosenCases.filter(x=>x!==id);
  // Only rerender when needed; values outside selection are retained.
  render();return;
 }
 if(e.target.id==='suiteAllCases'){
  const ids=suiteMatchingCases().map(x=>x.testcase_id);
  suiteChosenCases=e.target.checked?[...new Set([...suiteChosenCases,...ids])]:suiteChosenCases.filter(x=>!ids.includes(x));
  render();return;
 }
});
