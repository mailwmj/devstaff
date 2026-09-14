'use strict';

const key = 'site-form.{{PROJECT_ID}}.draft.v1';
const form = document.getElementById('request-form');
const fields = ['title', 'category', 'description'];
let step = 1;

function field(id) {
  return document.getElementById(id);
}

function data() {
  return Object.fromEntries(fields.map(id => [id, field(id).value.trim()]));
}

function saveDraft() {
  try {
    localStorage.setItem(key, JSON.stringify(data()));
    field('draft-status').textContent = '草稿已保存在当前浏览器';
  } catch {
    field('draft-status').textContent = '草稿暂时无法保存';
  }
}

function restoreDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(key) || '{}');
    for (const id of fields) if (typeof saved[id] === 'string') field(id).value = saved[id];
    if (fields.some(id => field(id).value)) field('draft-status').textContent = '已恢复上次草稿';
  } catch {
    field('draft-status').textContent = '旧草稿无法读取，当前输入不会覆盖它';
  }
}

function errorFor(id) {
  const input = field(id);
  const value = input.value.trim();
  if (!value) return id === 'category' ? '请选择事项类别。' : `请填写${id === 'title' ? '事项名称' : '详细说明'}。`;
  if (id === 'description' && value.length < 10) return '详细说明至少需要 10 个字。';
  return '';
}

function validate() {
  const errors = fields.map(id => ({ id, message: errorFor(id) })).filter(item => item.message);
  const list = field('error-list');
  list.replaceChildren();
  for (const item of errors) {
    const link = document.createElement('a');
    link.href = `#${item.id}`;
    link.textContent = item.message;
    const li = document.createElement('li');
    li.append(link);
    list.append(li);
  }
  for (const id of fields) {
    const error = errors.find(item => item.id === id)?.message || '';
    field(`${id}-error`).textContent = error;
    field(id).setAttribute('aria-invalid', String(Boolean(error)));
    if (error) field(id).setAttribute('aria-describedby', `${id}-error`);
    else if (id !== 'description') field(id).removeAttribute('aria-describedby');
    else field(id).setAttribute('aria-describedby', 'description-help');
  }
  field('error-summary').hidden = errors.length === 0;
  if (errors.length) {
    field('error-summary').focus();
    return false;
  }
  return true;
}

function showStep(nextStep) {
  step = nextStep;
  field('entry-step').hidden = step !== 1;
  field('review-step').hidden = step !== 2;
  field('back').hidden = step !== 2;
  field('next').hidden = step !== 1;
  field('submit').hidden = step !== 2;
  for (const item of document.querySelectorAll('.steps li')) {
    if (Number(item.dataset.step) === step) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  }
  if (step === 2) {
    const values = data();
    field('review-title-value').textContent = values.title;
    field('review-category-value').textContent = values.category;
    field('review-description-value').textContent = values.description;
    field('review-title').focus?.();
  } else {
    field('title').focus();
  }
}

let draftTimer;
form.addEventListener('input', () => {
  clearTimeout(draftTimer);
  field('draft-status').textContent = '正在保存草稿…';
  draftTimer = setTimeout(saveDraft, 250);
});
window.addEventListener('pagehide', () => {
  clearTimeout(draftTimer);
  if (!form.hidden && step === 1) saveDraft();
});
field('next').addEventListener('click', () => {
  if (validate()) {
    field('error-summary').hidden = true;
    saveDraft();
    showStep(2);
  }
});
field('back').addEventListener('click', () => showStep(1));
form.addEventListener('submit', event => {
  event.preventDefault();
  if (step !== 2 || !validate()) return;
  localStorage.removeItem(key);
  form.hidden = true;
  document.querySelector('.steps').hidden = true;
  field('error-summary').hidden = true;
  field('reference').textContent = `REQ-${new Date().getFullYear()}-${String(Date.now()).slice(-6)}`;
  field('success').hidden = false;
  field('success').focus();
});
field('new-request').addEventListener('click', () => {
  form.reset();
  form.hidden = false;
  document.querySelector('.steps').hidden = false;
  field('success').hidden = true;
  field('draft-status').textContent = '';
  showStep(1);
});

restoreDraft();
