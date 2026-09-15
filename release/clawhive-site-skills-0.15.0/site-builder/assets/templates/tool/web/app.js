'use strict';
const key = 'site-tool.{{PROJECT_ID}}.entries.v1';
const $ = selector => document.querySelector(selector);
let entries = [];
let pending = null;
let writable = true;
function message(text, error = false) {
  $('#message').textContent = text;
  $('#message').dataset.error = String(error);
}
function validate(value) {
  if (!Array.isArray(value) || value.length > 10000) throw new Error('备份格式不正确，或记录数量超过 10000 条。');
  const ids = new Set();
  return value.map(row => {
    if (!row || typeof row.id !== 'string' || !row.id || row.id.length > 100 || ids.has(row.id) || typeof row.text !== 'string' || !row.text.trim() || row.text.length > 200 || typeof row.createdAt !== 'string' || !Number.isFinite(Date.parse(row.createdAt))) throw new Error('备份包含无效或重复记录，原有内容未更改。');
    ids.add(row.id);
    return {id: row.id, text: row.text, createdAt: row.createdAt};
  });
}
function persist(next) {
  if (!writable) { message('原有数据无法读取。请先保留浏览器数据并让助手检查，当前不会覆盖记录。', true); return false; }
  try { localStorage.setItem(key, JSON.stringify(validate(next))); entries = next; render(); return true; }
  catch { message('保存失败。输入仍保留，请导出已有记录并检查浏览器存储。', true); return false; }
}
function render() {
  $('#entries').replaceChildren();
  $('#empty').hidden = entries.length > 0;
  $('#count').textContent = `${entries.length} 条`;
  for (const entry of entries) {
    const li = document.createElement('li');
    const text = document.createElement('span'); text.textContent = entry.text;
    const time = document.createElement('time'); time.dateTime = entry.createdAt; time.textContent = new Date(entry.createdAt).toLocaleDateString();
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'secondary'; remove.textContent = '删除'; remove.setAttribute('aria-label', `删除记录：${entry.text}`);
    remove.addEventListener('click', () => {
      if (confirm(`删除“${entry.text}”？此操作无法撤销。`) && persist(entries.filter(row => row.id !== entry.id))) message('记录已删除。');
    });
    li.append(text, time, remove); $('#entries').append(li);
  }
}
try { entries = validate(JSON.parse(localStorage.getItem(key) || '[]')); }
catch { writable = false; message('已有数据无法读取，已停止写入以保护原记录。请让助手检查。', true); }
render();
$('#entry-form').addEventListener('submit', event => {
  event.preventDefault(); const text = $('#entry').value.trim();
  if (!text) { message('请填写记录内容。', true); return; }
  if (persist([...entries, {id: crypto.randomUUID(), text, createdAt: new Date().toISOString()}])) { $('#entry').value = ''; $('#entry').focus(); message('已保存。'); }
});
$('#export').addEventListener('click', () => {
  if (!writable) { message('原数据读取异常，请先让助手恢复；不会导出一个假空备份。', true); return; }
  const link = document.createElement('a'); const url = URL.createObjectURL(new Blob([JSON.stringify({schema_version: 1, entries}, null, 2)], {type:'application/json'}));
  link.href = url; link.download = '记录备份.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); message('已生成备份文件，请保留下载的文件。');
});
$('#import').addEventListener('change', async () => {
  pending = null; $('#import-review').hidden = true;
  try {
    const file = $('#import').files[0]; if (!file) return;
    if (file.size > 5 * 1024 * 1024) throw new Error('备份文件超过 5 MB，未导入。');
    const data = JSON.parse(await file.text()); if (data.schema_version !== 1) throw new Error('不支持这个备份版本。');
    pending = validate(data.entries); $('#import-summary').textContent = `读取到 ${pending.length} 条记录。合并会保留当前记录，跳过已有的相同编号。`;
    $('#import-review').hidden = false;
  } catch (error) { message(error.message || '无法读取备份，原记录未更改。', true); }
  finally { $('#import').value = ''; }
});
$('#apply-import').addEventListener('click', () => {
  if (!pending) return;
  const ids = new Set(entries.map(row => row.id));
  if (persist([...entries, ...pending.filter(row => !ids.has(row.id))])) { pending = null; $('#import-review').hidden = true; message('已合并备份，原有记录保留。'); }
});
$('#cancel-import').addEventListener('click', () => { pending = null; $('#import-review').hidden = true; });
