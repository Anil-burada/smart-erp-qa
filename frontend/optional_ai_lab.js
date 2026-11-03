'use strict';
// Isolated, optional module. The existing PI/LPO/GRN positive/negative switches remain untouched.
const optionalLab = {project:'',provider:'rules',category:'Positive',model:'',scenario:'',expected:'',
  draft:null,stepsText:'',approved:null,comparison:null,baseline:null,targets:null,error:'',busy:false};
const labEsc = v => String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const labList = v => (v||[]).map(x=>`<li>${labEsc(x)}</li>`).join('');
const labProject=()=>optionalLab.project||(state.projects||[]).find(x=>['test','staging'].includes(x.environment))?.id||'';
function optionalAiLabPage(){
 const p=labProject();const d=optionalLab.draft;const a=optionalLab.approved;const c=optionalLab.comparison;
 const options=(state.projects||[]).filter(x=>['test','staging'].includes(x.environment)).map(x=>`<option value="${labEsc(x.id)}" ${x.id===p?'selected':''}>${labEsc(x.name)} (${labEsc(x.environment)})</option>`).join('');
 return `<div class="page-intro"><div class="eyebrow">OPTIONAL EXPERIMENT · REVIEW FIRST</div><h1 class="page-heading">AI Test Designer & Change-Aware Regression</h1><p class="muted">Separate, reversible add-on. No changes to your original Positive/Negative buttons, script login, procurement data or existing reports.</p></div>
 ${optionalLab.error?`<section class="panel lab-alert" role="alert">${labEsc(optionalLab.error)}</section>`:''}
 <section class="panel lab-panel"><div class="panel-head"><h3>Choose your TEST/STAGING ERP</h3><span class="lab-chip">Optional module</span></div>
 <label class="lab-label">ERP project<select id="labProject" class="lab-input">${options||'<option>No test/staging projects found</option>'}</select></label>
 <p class="muted small">A saved, approved locator library is required before AI can generate actual Playwright steps. Any unmapped test requires tester review.</p></section>
 <div class="lab-columns"><section class="panel lab-panel"><div class="panel-head"><h3>1 · AI Test Designer</h3><span class="lab-chip">Draft → Review → Generate → Run</span></div>
 <label class="lab-label">Provider<select id="labProvider" class="lab-input"><option value="rules" ${optionalLab.provider==='rules'?'selected':''}>Offline rules (no AI call)</option><option value="ollama" ${optionalLab.provider==='ollama'?'selected':''}>Local Ollama AI</option><option value="openai" ${optionalLab.provider==='openai'?'selected':''}>OpenAI API (opt-in)</option></select></label>
 <label class="lab-label">Model (optional)<input id="labModel" class="lab-input" value="${labEsc(optionalLab.model)}" placeholder="Use .env default"></label>
 <label class="lab-label">Scenario type<select id="labCategory" class="lab-input"><option value="Positive" ${optionalLab.category==='Positive'?'selected':''}>Positive</option><option value="Negative" ${optionalLab.category==='Negative'?'selected':''}>Negative</option></select></label>
 <label class="lab-label">New test scenario<textarea id="labScenario" class="lab-input" rows="4" maxlength="1500" placeholder="Example: Verify Purchase Indent quantity validation">${labEsc(optionalLab.scenario)}</textarea></label>
 <label class="lab-label">Expected result<textarea id="labExpected" class="lab-input" rows="3" maxlength="1000" placeholder="What exactly must the ERP show?">${labEsc(optionalLab.expected)}</textarea></label>
 <p class="muted small">OpenAI transmits only your typed scenario and sanitized target IDs/types. No saved credentials, CSS selectors, URLs or captured ERP data are sent. Offline and Ollama stay local.</p>
 <div class="lab-action-row"><button class="btn btn-primary" data-lab-action="design" ${optionalLab.busy?'disabled':''}>${optionalLab.busy?'Preparing…':'Suggest reviewed Playwright steps'}</button><button class="btn btn-outline" data-lab-action="targets" ${optionalLab.busy?'disabled':''}>Show reviewed target IDs</button></div>
 ${optionalLab.targets?`<details class="lab-result" open><summary>${optionalLab.targets.length} reviewed targets (use ID in JSON steps)</summary><div class="lab-targets">${optionalLab.targets.slice(0,150).map(t=>`<div><code>${labEsc(t.id)}</code> <span>${labEsc(t.label)} (${labEsc(t.control_type)})</span></div>`).join('')}</div></details>`:''}
 ${d?`<div class="lab-result"><h4>Review proposed steps</h4><p class="muted small">${labEsc(d.provider)} · ${labEsc(d.steps?.length||0)} allowlisted steps · ${labEsc(d.blocked?.length||0)} rejected steps</p>
 ${(d.blocked?.length)?`<div class="lab-alert"><strong>Excluded unsafe/unmapped steps:</strong><ul>${labList(d.blocked)}</ul></div>`:''}
 <label class="lab-label">Editable JSON plan (review targets and expected checks)<textarea class="lab-input lab-code" id="labSteps" rows="10">${labEsc(optionalLab.stepsText)}</textarea></label>
 <p class="muted small">Allowed actions: click, fill, assert_visible, assert_text. Save/Submit/Approve/Delete and sensitive fields are not generated. An assertion is mandatory.</p>
 <label class="lab-approval"><input type="checkbox" id="labApproveCheck"> I reviewed each step, target, and assertion; generate the script in my local working_scripts folder.</label>
 <button class="btn btn-primary" data-lab-action="approve" ${optionalLab.busy?'disabled':''}>Approve & generate Playwright script</button></div>`:''}
 ${a?`<div class="lab-result"><h4>Generated reviewed script</h4><p><code>${labEsc(a.script_id)}</code></p><p class="muted small">SHA256: ${labEsc(a.sha256.slice(0,16))}… · Saved in your existing Script Workspace.</p>
 <details><summary>View generated Python</summary><pre class="lab-code-display">${labEsc(a.source)}</pre></details>
 <button class="btn btn-primary" data-lab-action="run-script" ${optionalLab.busy?'disabled':''}>Run generated test (existing authenticated session)</button>
 <p class="muted small">Open the matching TEST/STAGING project in Browser Session, log in manually, and stop recording first. Run requires your explicit confirmation and uses your existing managed browser.</p></div>`:''}
 </section><section class="panel lab-panel"><div class="panel-head"><h3>2 · Change-Aware Regression</h3><span class="lab-chip">Read-only live ERP scan</span></div>
 <p class="muted">Open your ERP in Browser Session, log in and navigate to the exact page you want to monitor. Save a baseline once, then compare the same page after an ERP update.</p>
 <div class="lab-action-row"><button class="btn btn-outline" data-lab-action="baseline" ${optionalLab.busy?'disabled':''}>Capture baseline</button><button class="btn btn-primary" data-lab-action="compare" ${optionalLab.busy?'disabled':''}>Compare current ERP page</button></div>
 ${optionalLab.baseline?`<div class="lab-result"><strong>Baseline saved</strong><p class="muted small">${labEsc(optionalLab.baseline.page_url)} · ${labEsc(optionalLab.baseline.controls)} safe controls</p></div>`:''}
 ${c?`<div class="lab-result"><h4>${c.same?'No detected control drift':'Potential screen changes found'}</h4><p class="muted small">${labEsc(c.page_url)} · Saved baseline: ${labEsc(c.baseline_date)}</p>
 <div class="lab-counts"><span>Added: ${(c.added||[]).length}</span><span>Removed: ${(c.removed||[]).length}</span><span>Changed: ${(c.changed||[]).length}</span></div>
 ${(c.added||[]).length?`<h4>Added controls</h4><ul>${labList(c.added.map(x=>x.label||x.role||x.tag))}</ul>`:''}
 ${(c.removed||[]).length?`<h4>Removed controls</h4><ul>${labList(c.removed.map(x=>x.label||x.role||x.tag))}</ul>`:''}
 ${(c.changed||[]).length?`<h4>Selector/uniqueness changes</h4><ul>${labList(c.changed.map(x=>x.before.label))}</ul>`:''}
 <h4>Possibly affected recorded workflows</h4>${(c.affected_workflows||[]).length?`<ul>${labList(c.affected_workflows.map(x=>x.workflow+' — review and rerun'))}</ul>`:'<p class="muted small">No workflow text matched the changed control labels. Review dependencies manually.</p>'}
 <p class="muted small">Advisory only: dynamic fields, navigation and authentication may change the DOM. Never auto-repair a locator without review.</p></div>`:''}
 <p class="muted small">No credentials or input values are captured in the baseline. This feature reads the current ERP screen; it does not modify records.</p>
 </section></div>`;
}
function labReadFields(){
 optionalLab.project=document.getElementById('labProject')?.value||labProject();
 optionalLab.provider=document.getElementById('labProvider')?.value||'rules';
 optionalLab.model=document.getElementById('labModel')?.value||'';
 optionalLab.category=document.getElementById('labCategory')?.value||'Positive';
 optionalLab.scenario=document.getElementById('labScenario')?.value||'';
 optionalLab.expected=document.getElementById('labExpected')?.value||'';
}
async function labApi(path, data){
 const resp=await fetch('/api/optional-ai/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const doc=await resp.json().catch(()=>({detail:resp.statusText}));
 if(!resp.ok)throw new Error(typeof doc.detail==='string'?doc.detail:JSON.stringify(doc.detail));
 return doc;
}
document.addEventListener('click', async event=>{
 const control=event.target.closest('[data-lab-action]');if(!control)return;
 event.preventDefault();if(state.page!=='ailab'||optionalLab.busy)return;
 const action=control.dataset.labAction;labReadFields();
 if(!labProject()){optionalLab.error='Register a TEST/STAGING ERP project before running the AI Lab.';render();return;}
 optionalLab.busy=true;optionalLab.error='';render();
 try{
  if(action==='targets'){
   const response=await fetch('/api/optional-ai/projects/'+encodeURIComponent(labProject())+'/targets');
   const doc=await response.json().catch(()=>({detail:response.statusText}));
   if(!response.ok)throw Error(typeof doc.detail==='string'?doc.detail:'Unable to load approved target list');
   optionalLab.targets=doc.targets||[];
  }else if(action==='design'){
   optionalLab.approved=null;optionalLab.draft=await labApi('design',{
     project_id:labProject(),scenario:optionalLab.scenario,expected:optionalLab.expected,
     category:optionalLab.category,provider:optionalLab.provider,model:optionalLab.model});
   optionalLab.stepsText=JSON.stringify(optionalLab.draft.steps.map(x=>({action:x.action,target_id:x.target_id,value:x.value,expected:x.expected})),null,2);
  }else if(action==='approve'){
   // Preserve editable steps from DOM before asynchronous validation.
   // We store a fresh value as the render above removed the textarea, so saved below.
   let items=JSON.parse(optionalLab.stepsText);
   if(!Array.isArray(items)||!items.length)throw Error('Propose or manually review at least one step before approval.');
   if(!optionalLab.draft)throw Error('Create a design first.');
   if(!optionalLab.pendingApproval)throw Error('Tick the approval box after reviewing every step.');
   optionalLab.approved=await labApi('approve',{
      project_id:labProject(),draft_id:optionalLab.draft.id,reviewed_catalog_hash:optionalLab.draft.catalog_hash,
      steps:items,approve_code:true});
  }else if(action==='baseline'){
   optionalLab.baseline=await labApi('baseline',{project_id:labProject()});optionalLab.comparison=null;
  }else if(action==='compare'){
   optionalLab.comparison=await labApi('compare',{project_id:labProject()});
  }else if(action==='run-script'){
   const a=optionalLab.approved;if(!a)throw Error('Approve a generated script first');
   if(!confirm('Run this reviewed generated Python source in the CURRENT authenticated TEST/STAGING ERP session?\n\nDo not run against production. Inputs/clicks may change the screen. You are responsible for verifying the steps and ERP state.'))return;
   const run=await api('/script-workspace/run','POST',{project_id:labProject(),script_id:a.script_id,
        reviewed_sha256:a.sha256,mode:'existing',trust_local_code:true,allow_test_transactions:true,
        initial_role_confirmed:true,positive_scenarios:true,negative_scenarios:false});
   notify('Generated script run '+run.id.slice(0,8)+' started. View it in Test Reports.');go('reports');
  }
 }catch(err){optionalLab.error=String(err.message||err).slice(0,500);}
 finally{optionalLab.pendingApproval=false;optionalLab.busy=false;if(state.page==='ailab')render();}
});
document.addEventListener('input',event=>{
 if(event.target.id==='labSteps')optionalLab.stepsText=event.target.value;
});
document.addEventListener('change',event=>{
 if(event.target.id==='labApproveCheck')optionalLab.pendingApproval=event.target.checked;
 if(event.target.id==='labProject'){optionalLab.project=event.target.value;optionalLab.draft=null;optionalLab.approved=null;optionalLab.comparison=null;optionalLab.baseline=null;optionalLab.targets=null;}
});
