'use strict';

const items = [
  { id: 'a1', title: '清晰起步', category: '基础', summary: '适合先完成一条明确任务的简洁方案。', duration: '2 周', effort: '低', fit: '单一主任务' },
  { id: 'a2', title: '连续处理', category: '进阶', summary: '为重复查看与处理多条记录准备。', duration: '4 周', effort: '中', fit: '高频工作' },
  { id: 'a3', title: '材料优先', category: '专项', summary: '让图片、原文或数据成为页面主角。', duration: '3 周', effort: '中', fit: '内容展示' },
  { id: 'a4', title: '协作扩展', category: '进阶', summary: '保留后续多人协作的结构空间。', duration: '6 周', effort: '高', fit: '复杂流程' },
  { id: 'a5', title: '移动现场', category: '专项', summary: '针对窄屏和触屏场景组织核心操作。', duration: '3 周', effort: '中', fit: '移动使用' },
  { id: 'a6', title: '深度阅读', category: '基础', summary: '为长篇信息建立稳定的阅读节奏。', duration: '2 周', effort: '低', fit: '连续阅读' },
];

const selected = new Set();
const byId = id => document.getElementById(id);
const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

function visibleItems() {
  const query = byId('query').value.trim().toLocaleLowerCase('zh-CN');
  const category = byId('category').value;
  return items.filter(item => {
    const haystack = `${item.title} ${item.summary} ${item.fit}`.toLocaleLowerCase('zh-CN');
    return (!query || haystack.includes(query)) && (!category || item.category === category);
  });
}

function factList(item) {
  const list = element('dl', 'facts');
  for (const [label, value] of [['周期', item.duration], ['投入', item.effort]]) {
    const group = element('div');
    group.append(element('dt', '', label), element('dd', '', value));
    list.append(group);
  }
  return list;
}

function showDetail(item) {
  byId('detail-category').textContent = item.category;
  byId('detail-title').textContent = item.title;
  byId('detail-description').textContent = item.summary;
  const facts = byId('detail-facts');
  facts.replaceChildren();
  for (const [label, value] of [['适合', item.fit], ['预计周期', item.duration], ['投入程度', item.effort]]) {
    const group = element('div');
    group.append(element('dt', '', label), element('dd', '', value));
    facts.append(group);
  }
  byId('detail-dialog').showModal();
}

function toggleComparison(item, checked) {
  if (checked && selected.size >= 3) {
    byId('compare-status').textContent = '最多同时比较 3 项。';
    byId('compare-status').dataset.error = 'true';
    return false;
  }
  if (checked) selected.add(item.id);
  else selected.delete(item.id);
  byId('compare-status').textContent = selected.size ? `已选择 ${selected.size} 项` : '';
  byId('compare-status').dataset.error = 'false';
  renderComparison();
  return true;
}

function itemCard(item) {
  const card = element('article', 'result');
  const header = element('div', 'result-header');
  const titleGroup = element('div');
  titleGroup.append(element('span', 'tag', item.category), element('h3', '', item.title));
  header.append(titleGroup);
  card.append(header, element('p', '', item.summary), factList(item));

  const actions = element('div', 'result-actions');
  const compare = element('label', 'compare-control');
  const checkbox = element('input');
  checkbox.type = 'checkbox';
  checkbox.checked = selected.has(item.id);
  checkbox.setAttribute('aria-label', `比较${item.title}`);
  checkbox.addEventListener('change', () => {
    if (!toggleComparison(item, checkbox.checked)) checkbox.checked = false;
  });
  compare.append(checkbox, document.createTextNode('加入比较'));
  const detail = element('button', 'secondary', '查看详情');
  detail.type = 'button';
  detail.addEventListener('click', () => showDetail(item));
  actions.append(compare, detail);
  card.append(actions);
  return card;
}

function renderResults() {
  const visible = visibleItems();
  const results = byId('results');
  results.replaceChildren(...visible.map(itemCard));
  byId('empty').hidden = visible.length > 0;
  byId('result-count').textContent = `找到 ${visible.length} 项`;
}

function renderComparison() {
  const compared = items.filter(item => selected.has(item.id));
  const section = byId('comparison');
  section.hidden = compared.length === 0;
  if (!compared.length) return;
  const headRow = element('tr');
  headRow.append(element('th', '', '比较项'));
  for (const item of compared) headRow.append(element('th', '', item.title));
  byId('compare-head').replaceChildren(headRow);
  const rows = [['类别', 'category'], ['适合', 'fit'], ['预计周期', 'duration'], ['投入程度', 'effort']].map(([label, key]) => {
    const row = element('tr');
    row.append(element('th', '', label));
    for (const item of compared) row.append(element('td', '', item[key]));
    return row;
  });
  byId('compare-body').replaceChildren(...rows);
}

byId('filters').addEventListener('input', renderResults);
byId('filters').addEventListener('reset', () => setTimeout(renderResults));
byId('clear-empty').addEventListener('click', () => {
  byId('filters').reset();
  renderResults();
  byId('query').focus();
});
byId('clear-comparison').addEventListener('click', () => {
  selected.clear();
  renderResults();
  renderComparison();
  byId('compare-status').textContent = '';
});
byId('close-detail').addEventListener('click', () => byId('detail-dialog').close());
renderResults();
