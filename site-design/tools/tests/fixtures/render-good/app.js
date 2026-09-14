'use strict';
const input = document.getElementById('name');
const status = document.getElementById('status');
const saved = localStorage.getItem('render-control-name');
if (saved) status.textContent = `已保存：${saved}`;
document.getElementById('save').addEventListener('click', () => {
  localStorage.setItem('render-control-name', input.value);
  status.textContent = `已保存：${input.value}`;
});
