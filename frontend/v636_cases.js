'use strict';
// Works only with reviewed actions already present in the saved local Playwright script.
const v636State={cases:[],actions:[],ready:false,issues:[],revision:'',negative_ready:false,negative_issues:[],negative_revision:'',selected:'',message:'',loaded:false,loading:false};
const caseSafe=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.v636CaseHtml=function(){
 const s=v636State;
 return `<section class="panel" id="v636CaseRunner" aria-label="Excel and manually typed case runner">
  <div class="panel-head"><div><h3>Run an Excel or manually typed test case</h3><p class="muted">v6.3.6 direct add-on · original PI → LPO → GRN script is unchanged</p></div><button class="btn btn-outline btn-small" data-v636-refresh>Refresh</button></div>
  <p class="muted small">Positive runs saved PI to GRN actions; Negative runs Login, PI, PI approval and LPO UI checks on unsaved forms. Excel and typed text do <strong>not</strong> become executable Python. Review the matched action below. Cases marked Needs mapping cannot run until their Playwright code is reviewed and linked.</p>
  <div class="form-actions"><a class="btn btn-primary" href="/api/v636-cases/template">Download editable Excel (.xlsx)</a><label>Upload edited Excel<br><input id="v636Upload" type="file" accept=".xlsx" aria-label="Choose Excel test cases"></label><button class="btn btn-outline" data-v636-upload>Upload Excel</button></div>
  <hr><h4>Write your own scenario</h4>
  <div class="v636-case-form"><fieldset class="v636-category"><legend>Test type (choose one)</legend><label><input type="radio" name="v636-case-category" value="Positive" checked> Positive</label><label><input type="radio" name="v636-case-category" value="Negative"> Negative (PI → LPO, unsaved)</label></fieldset><label>Test Case ID<input id="v636Id" placeholder="CUSTOM-PI-001" maxlength="60"></label>
   <label>Test Case / Scenario<input id="v636Title" placeholder="Create Purchase Indent" maxlength="180"></label>
   <label>Test Steps<textarea id="v636Steps" rows="3" placeholder="1. Login\n2. Open Purchase Indent Creation\n3. Save a new indent"></textarea></label>
   <label>Expected Result<textarea id="v636Expected" rows="2" placeholder="New PI number appears on the detail page"></textarea></label>
   <label>Mapped reviewed action<select id="v636Map"><option value="">Needs mapping (do not run)</option>${s.actions.map(x=>`<option value="${caseSafe(x.id)}">${caseSafe(x.category)} · ${caseSafe(x.title)}</option>`).join('')}</select></label>
   <div class="form-actions"><button class="btn btn-outline" data-v636-suggest>Suggest matching script action</button><button class="btn btn-primary" data-v636-save>Save typed test case</button></div>
  </div>
  ${s.message?`<p class="qa-alert" role="status">${caseSafe(s.message)}</p>`:''}
  ${s.issues.length?`<p class="muted small">Configuration: ${caseSafe(s.issues.join(' '))}</p>`:''}
  <h4>Select one executable test case</h4>
  <div class="suite-table"><table><thead><tr><th>Test Case ID</th><th>Test Case</th><th>Source</th><th>Type</th><th>Reviewed script action</th><th>Mapping</th><th>Select</th></tr></thead><tbody>
   ${s.cases.map(c=>`<tr><td>${caseSafe(c.testcase_id)}</td><td>${caseSafe(c.title)}</td><td>${caseSafe(c.source)}</td><td>${caseSafe(c.category)}</td><td>${caseSafe(c.action||'—')}</td><td>${caseSafe(c.mapping)}</td><td><button class="btn btn-outline btn-small" data-v636-select="${caseSafe(c.testcase_id)}">${s.selected===c.testcase_id?'Selected':'Select'}</button></td></tr>`).join('')||'<tr><td colspan="7">Loading cases...</td></tr>'}
   </tbody></table></div>
  ${s.selected?(()=>{const c=s.cases.find(x=>x.testcase_id===s.selected);return c?`<p><strong>${caseSafe(c.testcase_id)}:</strong> ${caseSafe(c.title)}<br><strong>Expected:</strong> ${caseSafe(c.expected)}<br><strong>Type:</strong> ${caseSafe(c.category)}<br><strong>Action:</strong> ${caseSafe(c.action||'Needs mapping')}</p>`:'';})():''}
  <div class="form-actions"><button class="btn btn-primary" data-v636-run ${(!s.selected||!!s.loading||!s.cases.find(x=>x.testcase_id===s.selected&&x.mapping==='Ready'))?'disabled':''}>▶ Run selected test case</button><button class="btn btn-outline" data-go="reports">View execution reports</button></div>
 </section>`;
};
async function v636Load(){if(v636State.loading)return;v636State.loading=true;try{
 const resp=await fetch('/api/v636-cases/catalog');const payload=await resp.json();if(!resp.ok)throw Error(payload.detail||'Unable to load case catalog');
 Object.assign(v636State,{cases:payload.cases,actions:payload.actions,ready:payload.ready,issues:payload.issues||[],revision:payload.revision,negative_ready:payload.negative_ready,negative_issues:payload.negative_issues||[],negative_revision:payload.negative_revision||'',loaded:true});
 }catch(e){v636State.message=e.message;}finally{v636State.loading=false;if(typeof state!=='undefined'&&state.page==='suite'&&typeof render==='function')render();}}
// Test Case Report is rendered dynamically; load catalog once when this page is first opened.
setInterval(()=>{if(document.getElementById('v636CaseRunner')&&!v636State.loaded&&!v636State.loading)void v636Load();},1000);
function manualInput(){return {testcase_id:document.getElementById('v636Id')?.value.trim()||'',title:document.getElementById('v636Title')?.value.trim()||'',steps:document.getElementById('v636Steps')?.value.trim()||'',expected:document.getElementById('v636Expected')?.value.trim()||'',action:document.getElementById('v636Map')?.value||'',category:document.querySelector('[name="v636-case-category"]:checked')?.value||'Positive'};}
async function v636Request(endpoint,body){const res=await fetch('/api/v636-cases/'+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok)throw Error(data.detail||'Request failed');return data;}
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-v636-refresh],[data-v636-upload],[data-v636-suggest],[data-v636-save],[data-v636-run],[data-v636-select]');if(!button)return;
 event.preventDefault();try{
  if(button.hasAttribute('data-v636-select')){
    v636State.selected=button.dataset.v636Select;
    const chosen=v636State.cases.find(x=>x.testcase_id===v636State.selected);
    if(chosen&&typeof leocemState!=='undefined'){
      leocemState.negative=chosen.category==='Negative';leocemState.positive=!leocemState.negative;
    }
    render();return;
  }
  if(button.hasAttribute('data-v636-refresh')){v636State.loaded=false;await v636Load();return;}
  if(button.hasAttribute('data-v636-upload')){
    const file=document.getElementById('v636Upload')?.files?.[0];if(!file)throw Error('Select an Excel .xlsx file first.');if(!file.name.toLowerCase().endsWith('.xlsx'))throw Error('Only .xlsx files are accepted.');
    const form=new FormData();form.append('file',file);const res=await fetch('/api/v636-cases/upload',{method:'POST',body:form});const data=await res.json();if(!res.ok)throw Error(data.detail||'Upload failed');
    v636State.message=`Uploaded ${data.uploaded} case(s). Executable: ${data.executable}; Needs mapping: ${data.needs_mapping}.`;await v636Load();return;
  }
  if(button.hasAttribute('data-v636-suggest')){
    const input=manualInput();const res=await v636Request('suggest',input);
    document.getElementById('v636Map').value=res.suggested_action||'';
    v636State.message=res.suggested_action?`Suggested: ${res.suggested_action}. Review the steps and mapping before saving.`:res.description;
    const note=document.querySelector('#v636CaseRunner .qa-alert');if(note)note.textContent=v636State.message;
    else alert(v636State.message);return;
  }
  if(button.hasAttribute('data-v636-save')){
    const result=await v636Request('manual',manualInput());v636State.selected=result.case.testcase_id;
    v636State.message=result.mapping==='Ready'?'Scenario saved and mapped; review it before running.':'Scenario saved as Needs mapping; cannot run without reviewed Playwright steps.';
    await v636Load();return;
  }
  if(button.hasAttribute('data-v636-run')){
    const c=v636State.cases.find(x=>x.testcase_id===v636State.selected);if(!c)throw Error('Select a case first.');
    if(c.mapping!=='Ready')throw Error('Needs mapping: this case cannot run yet.');
    const isNegative=c.category==='Negative';
    if(isNegative&&!v636State.negative_ready)throw Error((v636State.negative_issues||[]).join(' '));
    if(!isNegative&&!v636State.ready)throw Error((v636State.issues||[]).join(' '));
    const sourceSha=isNegative?v636State.negative_revision:v636State.revision;
    if(!confirm(`Run ${c.testcase_id}: ${c.title}?\n\nReviewed action: ${c.action}\nExpected: ${c.expected}\n\nAuthorized TEST/STAGING ERP only. Positive tests may create/submit/approve records. Negative Login-to-LPO checks use UNSAVED PI/LPO forms, never document Save/Submit/Approve. Excel text will NOT become Python instructions. Stop cannot undo saved transactions.\n\nSource revision: ${sourceSha.slice(0,12)}\n\nPress OK only if you reviewed the script, the mapping and transaction consequences.`))return;
    const run=await v636Request('run',{testcase_id:c.testcase_id,reviewed_source_sha256:sourceSha,acknowledge_trusted_code:true,acknowledge_test_transactions:true});
    v636State.message='Started selected case '+c.testcase_id; if(typeof wsLoad==='function')await wsLoad();if(typeof go==='function')go('scripts');
    if(typeof notify==='function')notify('Test case started. Check live log and Expected vs Actual report.');return;
  }
 }catch(e){v636State.message=e.message;const note=document.querySelector('#v636CaseRunner .qa-alert');if(note)note.textContent=e.message;else alert(e.message);}
});
