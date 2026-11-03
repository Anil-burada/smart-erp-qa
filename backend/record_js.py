"""Capture ordinary/manual ERP interactions in the Playwright controlled browser.

The script runs on every navigation including same-origin SPA screens. It never
reads passwords, OTP, authentication tokens, or values from login forms.
"""
RECORDER_JS = r'''
(() => {
  if (window.__smartErpRecorderInstalled) return;
  window.__smartErpRecorderInstalled = true;
  window.__smartErpRecorderVersion = '6.1.7-stable-locators';
  const sensitive = /pass(word)?|token|secret|auth|otp|pin|cvv|card|account.?number|ssn|api.?key/i;
  const attr = (el, key) => (el && el.getAttribute && el.getAttribute(key) || '').trim();
  const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
  const norm = str => String(str || '').trim().replace(/\s+/g, ' ').slice(0, 120);
  const cssQuote = str => '"' + CSS.escape(String(str)).replace(/"/g, '\\"') + '"';
  const count = selector => { try { return document.querySelectorAll(selector).length; } catch (_) { return -1; } };
  const labels = el => el.labels ? [...el.labels].map(x=>norm(x.textContent)).filter(Boolean) : [];
  // Framework-generated IDs may change between login sessions or ERP deployments.
  const generatedId = id => /^:r\d+:$|^(mui|radix|react-select|headlessui)-/i.test(String(id || ''));
  const isSensitive = el => {
    if (!el) return true;
    const input = el.matches('input,textarea,select') ? el : null;
    if (input && (input.type === 'password' || [input.name,input.id,attr(input,'autocomplete'),attr(input,'placeholder')].some(v => sensitive.test(v || '')))) return true;
    // Exclude a login form and any of its controls, even when a submit button is outside it.
    const form = el.closest('form');
    return !!(form && form.querySelector('input[type=password]'));
  };
  const isLoginArea = el => {
    if (isSensitive(el)) return true;
    const box = el.closest('form,section,[role=dialog]');
    return !!(box && [...document.querySelectorAll('input[type=password]')].some(p => box.contains(p) && visible(p)));
  };
  function role(el) {
    const explicit = attr(el,'role');
    if (explicit) return explicit.split(' ')[0];
    const tag = el.tagName;
    if (tag === 'BUTTON') return 'button';
    if (tag === 'A' && el.hasAttribute('href')) return 'link';
    if (tag === 'SELECT') return 'combobox';
    if (tag === 'TEXTAREA') return 'textbox';
    if (tag === 'INPUT') {
      if (['button','submit','reset'].includes(el.type)) return 'button';
      if (el.type === 'checkbox') return 'checkbox';
      if (el.type === 'radio') return 'radio';
      return 'textbox';
    }
    return '';
  }
  // Match the accessible name that Playwright's get_by_role(name=...) expects.
  // A button's visible text takes priority over its tooltip/title. The previous
  // recorder reversed this order, so a button with text 'Purchase Requisition'
  // and title 'A department asks for material to be bought' saved the WRONG role name.
  function displayText(el) {
    const described = attr(el,'aria-labelledby').split(/\s+/).filter(Boolean)
      .map(id => document.getElementById(id)).filter(Boolean)
      .map(node => norm(node.textContent)).join(' ');
    const isEditable = el.matches('input:not([type=button]):not([type=submit]):not([type=reset]),textarea,select');
    const body = isEditable ? '' : norm(el.innerText || el.textContent || el.value);
    return norm(attr(el,'aria-label') || described || labels(el)[0] || body || attr(el,'title'));
  }
  function cssPath(el) {
    const nodes=[];
    for (let node=el, level=0; node && node.nodeType===1 && level<7; node=node.parentElement,level++) {
      if (node.id && !generatedId(node.id)) { nodes.unshift('#'+CSS.escape(node.id)); break; }
      const test=attr(node,'data-testid');
      if (test) { nodes.unshift('[data-testid='+cssQuote(test)+']'); break; }
      const tag=node.tagName.toLowerCase();
      const name=attr(node,'name');
      if (name && !sensitive.test(name)) {
        const fragment=tag+'[name='+cssQuote(name)+']';
        nodes.unshift(fragment);
        if(count(fragment)===1)break;
      } else {
        const peers=node.parentElement ? [...node.parentElement.children].filter(n=>n.tagName===node.tagName) : [];
        const pos=peers.indexOf(node)+1;
        nodes.unshift(tag+(peers.length>1 ? ':nth-of-type('+pos+')':''));
      }
      const candidate=nodes.join(' > ');
      if(count(candidate)===1) return candidate;
    }
    return nodes.join(' > ');
  }
  function candidates(el) {
    const arr=[];
    const add=(spec,num)=>{ if(num>=0)arr.push({spec,observed_count:num}); };
    const tid=attr(el,'data-testid');
    if(tid) add({kind:'test_id',value:tid},count('[data-testid='+cssQuote(tid)+']'));
    if(el.id && !generatedId(el.id)) add({kind:'css',value:'#'+CSS.escape(el.id)},count('#'+CSS.escape(el.id)));
    // Prefer stable project-defined attributes over DOM tree positions.
    for(const key of ['data-qa','data-test','aria-label']) {
      const val=attr(el,key);
      if(val && !sensitive.test(val)) {
        const css=el.tagName.toLowerCase()+'['+key+'='+cssQuote(val)+']';
        add({kind:'css',value:css},count(css));
      }
    }
    const lab=labels(el)[0];
    if(lab) add({kind:'label',value:lab},[...document.querySelectorAll('label')].filter(n=>norm(n.textContent)===lab).length);
    const name=attr(el,'name');
    if(name && !sensitive.test(name)) {
      const css=el.tagName.toLowerCase()+'[name='+cssQuote(name)+']';
      add({kind:'css',value:css},count(css));
    }
    const ph=attr(el,'placeholder');
    if(ph) add({kind:'placeholder',value:ph},count('[placeholder='+cssQuote(ph)+']'));
    const r=role(el);
    const txt=displayText(el);
    if(r && txt) {
      const native=r==='button' ? ',button,input[type=button],input[type=submit]' : r==='link' ? ',a[href]' : '';
      const matching=[...document.querySelectorAll('[role='+cssQuote(r)+']'+native)].filter(n=>displayText(n)===txt).length;
      add({kind:'role',role:r,name:txt},matching);
    }
    if(txt && ['BUTTON','A'].includes(el.tagName))
      add({kind:'text',value:txt},[...document.querySelectorAll('button,a')].filter(n=>norm(n.innerText)===txt).length);
    const path=cssPath(el);
    if(path) add({kind:'css',value:path},count(path));
    return arr;
  }
  const priority={test_id:0,role:1,label:2,placeholder:3,css:4,text:5};
  function send(el,action,value=null) {
    if(!el || isLoginArea(el)) return;
    if(typeof window.erpRecorderEvent !== 'function') return;
    const choices=candidates(el);
    const uniqueChoices=choices.filter(x=>x.observed_count===1);
    // Structural selectors may be unique today and match 9 elements tomorrow.
    // Use them only when no unique stable candidate exists; flag for review.
    const isStructural=x=>x.spec.kind==='css' && /:nth-of-type\(| > /.test(x.spec.value || '');
    const best=uniqueChoices.sort((a,b)=>{
      const fragility=Number(isStructural(a))-Number(isStructural(b));
      const idRank=x=>x.spec.kind==='css' && /^#[^ >]+$/.test(x.spec.value||'') ? -1 : (priority[x.spec.kind]??9);
      return fragility || idRank(a)-idRank(b);
    })[0];
    if(!best) return; // Ambiguous targets must not be recorded as reliable locators.
    const meta={tag:el.tagName.toLowerCase(),input_type:attr(el,'type') || (el.tagName==='SELECT'?'select':'text'),
      required:!!(el.required || attr(el,'aria-required')==='true'),min:attr(el,'min'),max:attr(el,'max'),
      minlength:attr(el,'minlength'),maxlength:attr(el,'maxlength'),pattern:attr(el,'pattern').slice(0,120)};
    const step={action,locator:best.spec,field_meta:meta,value,observed_count:best.observed_count,
      observed_candidates:choices.slice(0,15),page_url:location.href,target_text:displayText(el),
      locator_quality:isStructural(best)?'fragile_dom_path':'stable_candidate'};
    try { Promise.resolve(window.erpRecorderEvent(step)).catch(()=>{}); } catch (_) {}
  }
  // Record clicked semantic controls, including custom menus, tabs, option widgets,
  // linkish buttons, and controls with click handlers. Ignore plain text containers.
  // Prefer the real interactive control, not its child SVG/span/test-id.
  // Dynamic ERP navigation often binds a click to a custom menu or div.
  const clickControl = 'button,a[href],[role="button"],[role="link"],[role="menuitem"],'+
    '[role="option"],[role="tab"],[role="switch"],[role="checkbox"],'+
    'input[type="button"],input[type="submit"],input[type="reset"],'+
    '[aria-haspopup],[onclick],[data-testid],[data-test],[data-qa],'+
    '[tabindex]:not([tabindex="-1"])';
  function findClickControl(node) {
    if (!(node instanceof Element)) node = node?.parentElement;
    if (!node) return null;
    // First, find native/semantic control ancestors: handles SVG icon clicks.
    const semantic = node.closest('button,a[href],[role="button"],[role="link"],'+
      '[role="menuitem"],[role="option"],[role="tab"],[role="switch"],'+
      'input[type="button"],input[type="submit"],input[type="reset"],[aria-haspopup]');
    if (semantic) return semantic;
    const candidate = node.closest(clickControl);
    // Do not capture arbitrary noninteractive data-testid text containers.
    if (candidate && (candidate.matches('[onclick],[tabindex]:not([tabindex="-1"])') ||
        ['BUTTON','A','INPUT'].includes(candidate.tagName) || candidate.getAttribute('role') ||
        getComputedStyle(candidate).cursor === 'pointer')) return candidate;
    return null;
  }
  const pending = new WeakMap();
  function flushText(el) {
    const timer=pending.get(el);
    if(timer){clearTimeout(timer);pending.delete(el);}
    recordField(el);
  }
  document.addEventListener('click',event=>{
    if(!event.isTrusted) return;
    const el=findClickControl(event.target);
    if(!el || isLoginArea(el)) return;
    if(el.matches('input:not([type=button]):not([type=submit]):not([type=reset]),textarea,select')) return;
    send(el,'click');
  },true);
  const lastValue=new WeakMap();
  function recordField(el) {
    if(!el || isLoginArea(el)) return;
    if(el.tagName==='SELECT') return send(el,'select_option',el.value);
    if(el.matches('input[type="checkbox"],input[type="radio"]')) return send(el,el.checked?'check':'uncheck');
    if(el.matches('input,textarea,[contenteditable="true"]')) {
      const value=el.isContentEditable?el.innerText:el.value;
      if(typeof value!=='string' || value.length>1000 || lastValue.get(el)===value)return;
      lastValue.set(el,value);
      send(el,el.isContentEditable?'fill':'fill',value);
    }
  }
  // Some React/Vue form controls never raise a native change event until blur.
  // Debounce typing into a single fill action rather than one step per key.
  document.addEventListener('input',event=>{
    if(!event.isTrusted) return;
    const el=event.target;
    if(!el.matches || !el.matches('input:not([type="password"]),textarea,[contenteditable="true"]'))return;
    if(isLoginArea(el)) return;
    const old=pending.get(el);if(old)clearTimeout(old);
    pending.set(el,setTimeout(()=>flushText(el),450));
  },true);
  document.addEventListener('change',event=>{
    if(!event.isTrusted)return;
    const el=event.target;
    if(el && (el.matches('input,textarea,[contenteditable="true"]')))flushText(el);
    else recordField(el);
  },true);
  document.addEventListener('focusout',event=>{
    if(event.isTrusted && event.target.matches && event.target.matches('input,textarea,[contenteditable="true"]'))flushText(event.target);
  },true);
  document.addEventListener('keydown',event=>{
    if(!event.isTrusted || event.key!=='Enter' || isLoginArea(event.target))return;
    if(event.target.matches('input,textarea,[role="combobox"]'))send(event.target,'press','Enter');
  },true);
})();
'''
