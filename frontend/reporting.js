'use strict';
// Read-only analytics extension. Deliberately reuses the existing app.js project
// state, event delegation, browser/open and browser/close API actions.
const qaReports = {
  days: 30, project: '', data: null, loading: true, error: '', requestId: 0,
  lastUpdated: null
};
const qaReportColors = {passed:'#18a568',failed:'#e85f63',error:'#9b69ca',skipped:'#e7b24e',other:'#9aafbd'};
const qaStatuses = ['passed','failed','error','skipped','other'];
const qaStatusLabels = {passed:'Passed',failed:'Failed',error:'Error',skipped:'Skipped',other:'Other / warnings'};
const qaNum = n => Number(n || 0).toLocaleString('en-IN');
function qaLabel(status) {
  const s = String(status || '').toUpperCase();
  return ({PASSED:'passed',FAILED:'failed',ERROR:'error',SKIPPED:'skipped'})[s] || 'other';
}
function qaBadge(status) {
  const key=qaLabel(status);
  return `<span class="qa-status qa-${key}">${esc(status||'UNKNOWN')}</span>`;
}
function qaKpi(label, value, footer, kind) {
  return `<article class="qa-kpi"><div class="qa-kpi-top"><span>${esc(label)}</span><span class="qa-kpi-indicator qa-${kind||'neutral'}"></span></div><strong>${value}</strong><small>${esc(footer)}</small></article>`;
}
function qaDonut(d) {
  const total=d?.total||0, c=d?.counts||{};
  if (!total) return `<div class="qa-no-data">No executions in the selected period</div>`;
  let progress=0;
  const stops=[];
  for (const key of qaStatuses) {
    const pct=100*(c[key]||0)/total;
    if (pct) {stops.push(`${qaReportColors[key]} ${progress.toFixed(4)}% ${(progress+pct).toFixed(4)}%`);progress+=pct;}
  }
  return `<div class="qa-donut-row"><div class="qa-donut" role="img" aria-label="Run result distribution: ${qaStatuses.map(k=>`${qaStatusLabels[k]} ${c[k]||0}`).join(', ')}" style="background:conic-gradient(${stops.join(',')})"><div class="qa-donut-core"><span>Total runs</span><strong>${qaNum(total)}</strong></div></div><div class="qa-legend">${qaStatuses.map(k=>`<div><i style="background:${qaReportColors[k]}"></i><span>${qaStatusLabels[k]}</span><strong>${qaNum(c[k])}</strong></div>`).join('')}</div></div>`;
}
function qaTrend(d) {
  const series=d?.trend||[];
  if (!series.length || !series.some(x=>qaStatuses.some(k=>x[k]))) return `<div class="qa-no-data">No execution activity in the recent days</div>`;
  const w=740, h=220, left=34, top=18, bottom=37, right=8;
  const innerH=h-top-bottom, innerW=w-left-right;
  const maxVal=Math.max(1,...series.map(x=>qaStatuses.reduce((n,k)=>n+(x[k]||0),0)));
  const barWidth=Math.max(8,Math.min(29,innerW/series.length*.48));
  const step=innerW/series.length;
  let bars='';
  for (let i=0; i<series.length; i++) {
    const day=series[i], x=left+(i+.5)*step-barWidth/2;
    let y=top+innerH;
    const label=Object.keys(day).filter(k=>k!=='day').map(k=>`${k}: ${day[k]}`).join(', ');
    for (const k of qaStatuses) {
      const v=day[k]||0, bh=innerH*v/maxVal;
      if (v) {y-=bh;bars+=`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth}" height="${bh.toFixed(1)}" rx="2" fill="${qaReportColors[k]}"><title>${esc(day.day)} — ${esc(label)}</title></rect>`;}
    }
    if(i===0||i===series.length-1||i%Math.ceil(series.length/5)===0) {
      bars+=`<text x="${(left+(i+.5)*step).toFixed(1)}" y="${h-12}" font-size="10" text-anchor="middle" fill="#82918c">${esc(day.day.slice(5))}</text>`;
    }
  }
  const grid=[0,.25,.5,.75,1].map(fr=>{
    const gy=top+innerH*(1-fr),v=Math.round(maxVal*fr);
    return `<line x1="${left}" x2="${w-right}" y1="${gy}" y2="${gy}" stroke="#e7eef0" stroke-dasharray="3 4"/><text x="${left-7}" y="${gy+4}" text-anchor="end" font-size="10" fill="#91a29b">${v}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" aria-label="Daily workflow execution outcomes, stacked bars">${grid}${bars}</svg>`;
}
function qaProjectRow(p) {
  const active=state.session?.open && state.session.project_id===p.id;
  return `<div class="qa-project"><div class="qa-project-symbol">${esc((p.name||'E').charAt(0).toUpperCase())}</div><div class="qa-project-meta"><strong>${esc(p.name)}</strong><span>${esc(p.id)} · ${esc(p.environment||'')}</span><small title="${esc(p.url)}">${esc(p.url)}</small></div><span class="qa-session-badge ${active?'is-open':''}">${active?'Browser open':'Registered'}</span><div class="qa-project-buttons"><button class="btn btn-outline btn-small" data-action="open-project" data-id="${esc(p.id)}">${active?'Reopen':'Open ERP'}</button>${active?`<button class="btn btn-danger btn-small" data-action="close">Close Browser</button>`:''}</div></div>`;
}
function qaRecent(d) {
  const recent=d?.recent||[];
  if (!recent.length) return `<div class="qa-no-data">No saved runs match these filters. Run a reviewed workflow to see results.</div>`;
  return `<div class="qa-table-wrap"><table class="qa-runs-table"><thead><tr><th>Run</th><th>ERP project</th><th>Workflow</th><th>Result</th><th>Started (UTC)</th><th>Message</th></tr></thead><tbody>${recent.slice(0,15).map(r=>`<tr><td>#${Number(r.id)||0}</td><td>${esc(r.project_id)}</td><td><strong>${esc(r.workflow_name)}</strong></td><td>${qaBadge(r.status)}</td><td>${esc(r.started_at||'—')}</td><td title="${esc(r.message||'')}"><span class="qa-message">${esc(r.message||'—')}</span></td></tr>`).join('')}</tbody></table></div>`;
}
function qaOverview() {
  const d=qaReports.data, loading=qaReports.loading;
  const counts=d?.counts||{};
  const selected=qaReports.project;
  const filterProjects=`<option value="">All ERP projects</option>${state.projects.map(p=>`<option value="${esc(p.id)}" ${selected===p.id?'selected':''}>${esc(p.name)}</option>`).join('')}`;
  const status=state.session?.open;
  return `${intro('QA ANALYTICS / OVERVIEW','Smart ERP Test Reports','Monitor saved workflow run outcomes, browse registered ERPs, and control your live Playwright browser.')} 
  <section class="qa-toolbar"><div class="qa-toolbar-heading"><span class="qa-live-dot"></span><strong>Execution insights</strong><small>${qaReports.lastUpdated?'Updated '+qaReports.lastUpdated:'Local SQLite reports'}</small></div><div class="qa-filters"><label>ERP <select id="qaProjectFilter">${filterProjects}</select></label><label>Period <select id="qaDaysFilter"><option value="7" ${qaReports.days===7?'selected':''}>Last 7 days</option><option value="30" ${qaReports.days===30?'selected':''}>Last 30 days</option><option value="90" ${qaReports.days===90?'selected':''}>Last 90 days</option><option value="0" ${qaReports.days===0?'selected':''}>All time</option></select></label><button class="btn btn-outline" id="qaRefresh" ${loading?'disabled':''}>↻ Refresh</button><button class="btn btn-outline" id="qaExportCSV" ${!d?.recent?.length?'disabled':''}>Export CSV</button></div></section>
  ${qaReports.error?`<div class="qa-alert" role="alert">Unable to load reports: ${esc(qaReports.error)} <button class="btn btn-outline btn-small" id="qaRetry">Retry</button></div>`:''}
  <section class="qa-kpi-grid" aria-label="Workflow execution metrics">
    ${qaKpi('Total runs',loading?'…':qaNum(d?.total), 'Saved workflow executions','neutral')}
    ${qaKpi('Passed',loading?'…':qaNum(counts.passed),'Completed successfully','passed')}
    ${qaKpi('Failed',loading?'…':qaNum(counts.failed),'Failed workflow runs','failed')}
    ${qaKpi('Error',loading?'…':qaNum(counts.error),'Run errors','error')}
    ${qaKpi('Skipped / other',loading?'…':qaNum((counts.skipped||0)+(counts.other||0)),'Includes warnings / blocked','skipped')}
  </section>
  <section class="qa-main-grid"><article class="qa-report-card qa-trend"><div class="qa-card-head"><div><h3>Execution Results Trend</h3><p>Daily passed, failed and other run outcomes · UTC</p></div><span class="qa-card-chip">${Math.min(qaReports.days||14,14)} days</span></div>${loading?'<div class="qa-no-data">Loading trend…</div>':qaTrend(d)}</article>
  <article class="qa-report-card qa-distribution"><div class="qa-card-head"><div><h3>Results Distribution</h3><p>Saved workflow runs by status</p></div></div>${loading?'<div class="qa-no-data">Loading…</div>':qaDonut(d)}<div class="qa-pass-rate"><span>Overall pass rate</span><strong>${loading?'…':d?.pass_rate===null?'—':d?.pass_rate+'%'}</strong></div></article></section>
  <section class="qa-main-grid qa-lower-grid"><article class="qa-report-card"><div class="qa-card-head"><div><h3>ERP Projects</h3><p>Open an application directly, or close the current browser</p></div><button class="btn btn-outline btn-small" data-go="projects">Manage all</button></div><div class="qa-projects">${state.projects.length?state.projects.slice(0,5).map(qaProjectRow).join(''):'<div class="qa-no-data">No ERP projects registered.</div>'}</div></article>
  <article class="qa-report-card"><div class="qa-card-head"><div><h3>Playwright Browser</h3><p>Current local automation session</p></div><span class="qa-session-badge ${status?'is-open':''}">${status?'● OPEN':'○ CLOSED'}</span></div><div class="qa-browser-state"><span>Active project</span><strong>${esc(state.session?.project_id||'No browser open')}</strong><span>Current URL</span><code title="${esc(state.session?.url||'')}">${esc(state.session?.url||'—')}</code><span>Recorder</span><strong>${state.session?.recording?'Recording · '+qaNum(state.session.step_count)+' actions':state.session?.paused?'Paused':'Stopped'}</strong></div><div class="qa-browser-actions"><button class="btn btn-primary" data-go="browser">Browser Session</button><button class="btn btn-danger" data-action="close" ${!status?'disabled':''}>Close Browser</button></div></article></section>
  <section class="qa-report-card qa-recent"><div class="qa-card-head"><div><h3>Recent Test Run Reports</h3><p>Actual persisted results, not simulated test case counts</p></div><button class="btn btn-outline btn-small" data-go="workflows">Workflows</button></div>${loading?'<div class="qa-no-data">Loading execution history…</div>':qaRecent(d)}</section>
  <p class="qa-report-note"><strong>Data scope:</strong> One saved execution = one workflow run. Excel test-case totals and Script Workspace checks are reported in their own sections. Failed runs shown here do not necessarily mean individual assertions failed. Only TEST/STAGING actions should be replayed.</p>`;
}
// Override only the Overview renderer; all existing recorder and workflow pages
// continue to use their original functionality and event handlers.
overview = qaOverview;
async function qaLoadReports() {
  const requestId=++qaReports.requestId;
  qaReports.loading=true;qaReports.error='';
  if (state.page==='overview') render();
  try {
    const url=`/reporting/summary?days=${qaReports.days}&project_id=${encodeURIComponent(qaReports.project)}`;
    const data=await api(url);
    if(requestId!==qaReports.requestId)return;
    qaReports.data=data;qaReports.loading=false;
    qaReports.lastUpdated=new Date().toLocaleTimeString();
  } catch(e) {
    if(requestId!==qaReports.requestId)return;
    qaReports.error=e.message;qaReports.data=null;qaReports.loading=false;
  }
  if(state.page==='overview')render();
}
function qaExportCsv(){
  const rows=qaReports.data?.recent||[];
  const keys=['id','project_id','workflow_name','status','step_number','started_at','ended_at','message'];
  const csv=[keys.join(','),...rows.map(row=>keys.map(k=>`"${String(row[k]??'').replace(/"/g,'""')}"`).join(','))].join('\r\n');
  const blob=new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');
  a.href=url;a.download='smart_erp_recent_runs.csv';document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
document.addEventListener('change',e=>{
  if(e.target.id==='qaDaysFilter'){qaReports.days=Number(e.target.value);void qaLoadReports();}
  if(e.target.id==='qaProjectFilter'){qaReports.project=e.target.value;void qaLoadReports();}
});
document.addEventListener('click',e=>{
  if(e.target.closest('#qaRefresh')||e.target.closest('#qaRetry')) void qaLoadReports();
  if(e.target.closest('#qaExportCSV'))qaExportCsv();
});
// Initial load and periodic refresh only when Overview is visible. No automatic
// re-render of the recorder/forms on other pages.
void qaLoadReports();
setInterval(()=>{if(state.page==='overview'&&!state.busy&&!qaReports.loading)void qaLoadReports();},45000);
