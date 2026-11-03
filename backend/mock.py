"""An intentionally harmless local ERP for recording/replay smoke tests."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix='/mock')

HTML = '''<!doctype html><html><head><meta charset="utf-8"><title>Mock ERP - Test Only</title>
<style>body{font:15px system-ui;max-width:840px;margin:50px auto;background:#f0f9f2;color:#19432c}header{background:#09754d;color:white;padding:20px;border-radius:12px}section{background:white;padding:24px;margin:16px 0;border-radius:12px}label{display:block;margin:12px 0}input,select{padding:10px;margin-left:8px}button{padding:11px 18px;background:#0a754c;color:white;border:none;border-radius:7px;margin:5px;cursor:pointer}.hidden{display:none}</style></head><body>
<header><strong>LOCAL MOCK ERP</strong> — Only for learning. No real records. <button id="logout" class="hidden">Logout</button></header>
<section id="loginPanel"><h2>Manual test login</h2><label>Username <input data-testid="mock-user" id="username" placeholder="User" autocomplete="off"></label>
<label>Password <input data-testid="mock-password" id="password" type="password" placeholder="Password"></label>
<button data-testid="mock-login" id="loginBtn">LOGIN</button><p>Any non-empty test username and password works. Do not enter real passwords.</p></section>
<section id="dashboard" class="hidden"><h2>ERP Dashboard</h2><button data-testid="indent-menu" id="menu">Purchase Indent</button><button data-testid="create-indent" id="create">Create New Indent</button><button id="viewLatest">View Last Indent / PO / GRN</button></section>
<section id="form" class="hidden"><h2>Purchase Indent</h2><label>Department <select data-testid="department" id="department"><option value="">Select</option><option value="Stores">Stores</option><option value="Maintenance">Maintenance</option></select></label>
<label>Item name <input data-testid="item" id="item" placeholder="Item name"></label>
<label>Quantity <input data-testid="quantity" id="qty" type="number" min="1" placeholder="Quantity"></label>
<button data-testid="save-indent" id="save">Save Indent</button><p id="message"></p></section>
<section id="saved" class="hidden"><h2>Saved Indent</h2><p id="saved-number"></p><p>Status: <span id="status">Created</span></p><button id="approve">Approve Indent</button><button id="createLpo">Create Local PO</button><p id="lpo-number" class="hidden"></p><p>PO Status: <span id="po-status">Not created</span></p><button id="approveLpo">Approve Local PO</button><button id="createGrn">Create GRN</button><p id="grn-number" class="hidden"></p><button id="back">Back to Dashboard</button></section>
<script>
const $=id=>document.getElementById(id);
const key='mock_procurement_state';
function state(){return JSON.parse(localStorage.getItem(key)||'{}')}
function update(value){localStorage.setItem(key,JSON.stringify({...state(),...value})); renderSaved()}
function show(id){['loginPanel','dashboard','form','saved'].forEach(x=>$(x).classList.toggle('hidden',x!==id));$('logout').classList.toggle('hidden',id==='loginPanel')}
function renderSaved(){
 const x=state();
 $('saved-number').textContent=x.pi||'';
 $('status').textContent=x.pi_status||'Created';
 $('lpo-number').textContent=x.lpo||'';
 $('lpo-number').classList.toggle('hidden',!x.lpo);
 $('po-status').textContent=x.po_status||'Not created';
 $('grn-number').textContent=x.grn||'';
 $('grn-number').classList.toggle('hidden',!x.grn);
 $('approve').classList.toggle('hidden',!x.pi||x.pi_status==='Approved');
 $('createLpo').classList.toggle('hidden',x.pi_status!=='Approved'||!!x.lpo);
 $('approveLpo').classList.toggle('hidden',!x.lpo||x.po_status==='Approved');
 $('createGrn').classList.toggle('hidden',x.po_status!=='Approved'||!!x.grn);
}
$('loginBtn').onclick=()=>{if($('username').value && $('password').value){sessionStorage.setItem('mock_logged_in','yes');show('dashboard')}};
$('logout').onclick=()=>{sessionStorage.removeItem('mock_logged_in');$('username').value='';$('password').value='';show('loginPanel')};
$('menu').onclick=()=>show('dashboard');$('create').onclick=()=>show('form');
$('viewLatest').onclick=()=>{renderSaved();show(state().pi?'saved':'dashboard')};
$('save').onclick=()=>{
 if(!$('department').value||!$('item').value||Number($('qty').value)<=0){$('message').textContent='Fill all required values';return}
 update({pi:'PI-MOCK-'+Date.now(),pi_status:'Created',lpo:null,po_status:null,grn:null,department:$('department').value,item:$('item').value,qty:Number($('qty').value)});show('saved')
};
$('approve').onclick=()=>{if(state().pi)update({pi_status:'Approved'})};
$('createLpo').onclick=()=>{if(state().pi_status==='Approved')update({lpo:'LPO-MOCK-'+Date.now(),po_status:'Created'})};
$('approveLpo').onclick=()=>{if(state().lpo)update({po_status:'Approved'})};
$('createGrn').onclick=()=>{if(state().po_status==='Approved')update({grn:'GRN-MOCK-'+Date.now()})};
$('back').onclick=()=>show('dashboard');
renderSaved();if(sessionStorage.getItem('mock_logged_in')==='yes')show('dashboard');
</script></body></html>'''


@router.get('/',response_class=HTMLResponse)
def demo():
    return HTMLResponse(HTML)
