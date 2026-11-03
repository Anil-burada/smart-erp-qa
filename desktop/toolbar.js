'use strict';
const $ = id => document.getElementById(id);
async function act(button, fn) {
  button.disabled = true;
  try { await fn(); }
  catch (error) { $('note').textContent = 'Error: ' + String(error?.message || error).slice(0,180); }
  finally { button.disabled = false; }
}
$('teach').addEventListener('click', () => act($('teach'), async()=> {
  await window.smartERPDesktop.startTeaching();
  $('note').textContent='Recording ON — click Workflows to finish and save JSON';
}));
$('workflows').addEventListener('click', ()=>act($('workflows'),()=>window.smartERPDesktop.navigate('workflows')));
$('close').addEventListener('click', ()=>act($('close'),()=>window.smartERPDesktop.closeERP()));
