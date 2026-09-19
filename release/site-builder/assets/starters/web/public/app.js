'use strict';
const $ = (id) => document.getElementById(id);
let csrf='', records=[], pendingImport=null, operationKey=null;
const t={saved:'\u5df2\u4fdd\u5b58\uff0c\u5237\u65b0\u540e\u4ecd\u53ef\u67e5\u770b\u3002',failure:'\u64cd\u4f5c\u6ca1\u6709\u5b8c\u6210\uff1a',done:'\u5b8c\u6210',reopen:'\u6062\u590d',remove:'\u5220\u9664',confirm:'\u786e\u5b9a\u5220\u9664\u8fd9\u6761\u8bb0\u5f55\uff1f',empty:'\u8fd8\u6ca1\u6709\u8bb0\u5f55\uff0c\u5148\u6dfb\u52a0\u7b2c\u4e00\u6761\u3002',noMatch:'\u6ca1\u6709\u5339\u914d\u7684\u8bb0\u5f55\u3002'};
function message(text,kind='success'){$('message').textContent=text;$('message').dataset.kind=kind;}
async function api(path,method='GET',body){
 const headers={'Content-Type':'application/json','X-Site-Client':'1'};if(csrf)headers['X-CSRF-Token']=csrf;
 const response=await fetch(path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});
 const data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data;
}
async function action(button,fn){if(button.disabled)return;button.disabled=true;try{await fn();}catch(error){message(t.failure+(error instanceof Error?error.message:String(error)),'error');}finally{button.disabled=false;if(!pendingImport)$('import-confirm').disabled=true;}}
function child(tag,text,className){const e=document.createElement(tag);e.textContent=text;if(className)e.className=className;return e;}
function render(){
 const query=$('search').value.trim().toLowerCase(), list=records.filter(r=>r.title.toLowerCase().includes(query));
 $('records').replaceChildren();$('count').textContent=String(records.length);$('empty').hidden=Boolean(list.length);$('empty').textContent=records.length?t.noMatch:t.empty;
 for(const r of list){
  const li=child('li','','record');li.dataset.recordId=r.id;const info=child('div','');info.append(child('div',r.title,'record-title'));
  info.append(child('div',`${(r.amount_minor/100).toFixed(2)} | ${r.date||'-'} | ${r.status==='done'?t.done:'\u672a\u5b8c\u6210'}`,'record-meta'));
  if(r.notes)info.append(child('div',r.notes,'record-meta'));
  const buttons=child('div','','record-actions'), toggle=child('button',r.status==='done'?t.reopen:t.done);toggle.type='button';toggle.setAttribute('aria-label',`${toggle.textContent} ${r.title}`);
  toggle.addEventListener('click',()=>action(toggle,async()=>{await api('/api/records/'+r.id,'PATCH',{status:r.status==='done'?'open':'done'});await refresh();}));
  const remove=child('button',t.remove);remove.type='button';remove.setAttribute('aria-label',`${t.remove} ${r.title}`);
  remove.addEventListener('click',()=>{if(confirm(t.confirm))action(remove,async()=>{await api('/api/records/'+r.id,'DELETE');await refresh();});});
  buttons.append(toggle,remove);li.append(info,buttons);$('records').append(li);
 }
 // Minor-unit totals remain integers until the final display formatting.
 $('total').textContent=`\u5408\u8ba1 ${(list.reduce((n,r)=>n+r.amount_minor,0)/100).toFixed(2)}`;
 const url=new URL(location.href);if(query)url.searchParams.set('q',query);else url.searchParams.delete('q');history.replaceState(null,'',url);
}
async function refresh(){const data=await api('/api/records');records=data.records;render();}
async function workspace(){const session=await api('/api/session');csrf=session.csrf||'';$('workspace').hidden=!session.authenticated;$('login-panel').hidden=session.authenticated;$('logout').hidden=session.profile!=='shared'||!session.authenticated;if(session.authenticated)await refresh();}
$('record-form').addEventListener('input',()=>{operationKey=null;});
$('record-form').addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget;const payload=Object.fromEntries(new FormData(form));operationKey=operationKey||crypto.randomUUID();payload.idempotency_key=operationKey;action(form.querySelector('button[type=submit]'),async()=>{await api('/api/records','POST',payload);operationKey=null;form.reset();await refresh();message(t.saved);});});
$('login-form').addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget,payload=Object.fromEntries(new FormData(form));action(form.querySelector('button'),async()=>{const result=await api('/api/login','POST',payload);csrf=result.csrf;form.reset();await workspace();message('');});});
$('logout').addEventListener('click',()=>action($('logout'),async()=>{await api('/api/logout','POST',{});csrf='';records=[];await workspace();}));
$('search').value=new URL(location.href).searchParams.get('q')||'';$('search').addEventListener('input',render);
$('export').addEventListener('click',()=>action($('export'),async()=>{const data=await api('/api/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='records-backup.json';a.click();URL.revokeObjectURL(url);}));
$('import-form').addEventListener('input',()=>{pendingImport=null;$('import-confirm').disabled=true;});
$('import-form').addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget,data=Object.fromEntries(new FormData(form));action(form.querySelector('button[type=submit]'),async()=>{data.mapping=JSON.parse(data.mapping);const preview=await api('/api/import-preview','POST',data);$('import-result').textContent=JSON.stringify({count:preview.count,errors:preview.errors},null,2);pendingImport=preview.valid?data:null;$('import-confirm').disabled=!preview.valid;});});
$('import-confirm').addEventListener('click',()=>action($('import-confirm'),async()=>{if(!pendingImport)throw new Error('Preview the import first.');const result=await api('/api/import','POST',pendingImport);pendingImport=null;await refresh();$('import-result').textContent=JSON.stringify(result,null,2);message(t.saved);}));
(async()=>{try{
 const response=await fetch('content.json');if(!response.ok)throw new Error('Content unavailable.');const c=await response.json();
 document.title=c.title;$('title').textContent=c.title;$('brand').textContent=c.brand||c.title;$('description').textContent=c.description||'';$('eyebrow').textContent=c.eyebrow||'';$('footer-note').textContent=c.footer||'';
 $('mode').textContent=c.profile==='shared'?'\u767b\u5f55\u5de5\u4f5c\u533a':'\u4e2a\u4eba\u5de5\u5177';
 $('storage-note').textContent='\u6570\u636e\u4fdd\u5b58\u5728\u8fd0\u884c\u670d\u52a1\u7684\u7535\u8111\u4e0a\uff0c\u5237\u65b0\u4e0d\u4e22\u5931\u3002\u6362\u8bbe\u5907\u4e0d\u4f1a\u81ea\u52a8\u540c\u6b65\uff1b\u8bf7\u5b9a\u671f\u5bfc\u51fa\u5907\u4efd\u3002';
 await workspace();
}catch(error){message(t.failure+String(error),'error');}})();
