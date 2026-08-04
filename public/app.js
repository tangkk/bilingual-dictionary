const input = document.querySelector('#searchInput');
const form = document.querySelector('#searchForm');
const results = document.querySelector('#results');
const state = document.querySelector('#state');
const direction = document.querySelector('#direction');
const recentSection = document.querySelector('#recentSection');
const recentList = document.querySelector('#recentList');
const clearHistory = document.querySelector('#clearHistory');
const dataVersion = document.querySelector('#dataVersion');
const cache = new Map();
const HISTORY_KEY = 'bilingual-dictionary-history';
const POS_LABELS = {
  n: '名词', noun: '名词', nr: '人名', ns: '地名', nt: '机构名', nz: '专有名词',
  v: '动词', verb: '动词', vd: '副动词', vn: '名动词',
  a: '形容词', adj: '形容词', ad: '副形词', an: '名形词',
  d: '副词', adv: '副词', r: '代词', pron: '代词', p: '介词', prep: '介词',
  c: '连词', conj: '连词', m: '数词', num: '数词', q: '量词',
  u: '助词', particle: '助词', e: '叹词', int: '叹词',
  f: '方位词', s: '处所词', t: '时间词', b: '区别词', z: '状态词',
  i: '成语', l: '习语', j: '简称', eng: '外语词', x: '其他',
  suffix: '后缀', prefix: '前缀', pn: '专有名词'
};

const escapeHTML = (value = '') => String(value).replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
})[char]);

function normalizeEnglish(value) {
  return value.normalize('NFKC').toLowerCase().replaceAll('’', "'")
    .replace(/[^a-z0-9' -]+/g, ' ').replace(/\s+/g, ' ').replace(/^[- ]+|[- ]+$/g, '');
}

function detectLanguage(value) {
  return /[\u3400-\u9fff\uf900-\ufaff]/u.test(value) ? 'zh' : 'en';
}

function shardFor(value, language) {
  if (language === 'zh') return `u${(value.codePointAt(0) % 256).toString(16).padStart(2, '0')}`;
  const safe = normalizeEnglish(value).replace(/[^a-z0-9]/g, '');
  return `${safe}__`.slice(0, 2);
}

async function loadShard(language, shard) {
  const key = `${language}/${shard}`;
  if (cache.has(key)) return cache.get(key);
  const request = fetch(`./data/${key}.json`).then(async response => {
    if (response.status === 404) return {};
    if (!response.ok) throw new Error(`数据加载失败 (${response.status})`);
    return response.json();
  });
  cache.set(key, request);
  return request;
}

async function loadExampleShard(language, shard) {
  const key = `examples/${language}/${shard}`;
  if (cache.has(key)) return cache.get(key);
  const request = fetch(`./data/${key}.json`).then(async response => {
    if (response.status === 404) return {};
    if (!response.ok) throw new Error(`例句加载失败 (${response.status})`);
    return response.json();
  });
  cache.set(key, request);
  return request;
}

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
  catch { return []; }
}

function saveHistory(term) {
  const next = [term, ...getHistory().filter(item => item !== term)].slice(0, 7);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  renderHistory();
}

function renderHistory() {
  const history = getHistory();
  recentSection.hidden = history.length === 0;
  clearHistory.hidden = history.length === 0;
  recentList.innerHTML = history.map(term => `<button class="chip" type="button" data-query="${escapeHTML(term)}">${escapeHTML(term)}</button>`).join('');
}

function sourceBadge(source) {
  return source === 'fd' ? 'FreeDict' : 'CC-CEDICT';
}

function renderPos(tags = []) {
  const labels = [...new Set(tags.map(tag => POS_LABELS[tag.toLowerCase()] || tag).filter(Boolean))];
  return labels.length ? `<div class="pos-tags">${labels.slice(0, 4).map(label => `<span class="pos-tag">${escapeHTML(label)}</span>`).join('')}</div>` : '';
}

function renderChineseCard(item) {
  const traditional = item.t && item.t !== item.s ? `<span class="traditional">${escapeHTML(item.t)}</span>` : '';
  return `<article class="card">
    <div class="card-head">
      <div><h3 class="word">${escapeHTML(item.s)}${traditional}</h3><div class="pronunciation">${escapeHTML(item.p)}</div>${renderPos(item.g)}</div>
      <span class="badge">${sourceBadge(item.x)}</span>
    </div>
    <ol class="translations">${item.d.slice(0, 12).map(text => `<li>${escapeHTML(text)}</li>`).join('')}</ol>
  </article>`;
}

function renderEnglishCard(item) {
  const translations = Array.isArray(item.z) ? item.z : [item.z];
  const pronunciation = [item.r?.slice(0, 4).join(' · '), item.p].filter(Boolean).join('  ');
  const traditional = item.t && item.t !== item.z ? ` <span class="traditional">${escapeHTML(item.t)}</span>` : '';
  return `<article class="card">
    <div class="card-head">
      <div><h3 class="word">${escapeHTML(item.e)}</h3>${pronunciation ? `<div class="pronunciation">${escapeHTML(pronunciation)}</div>` : ''}${renderPos(item.g)}</div>
      <span class="badge">${sourceBadge(item.x)}</span>
    </div>
    <ul class="translations">${translations.slice(0, 16).map((text, index) => `<li>${escapeHTML(text)}${index === 0 ? traditional : ''}</li>`).join('')}</ul>
  </article>`;
}

function renderExample(item) {
  const englishUrl = `https://tatoeba.org/en/sentences/show/${item.ei}`;
  const chineseUrl = `https://tatoeba.org/en/sentences/show/${item.zi}`;
  const authors = [item.eu, item.zu].filter(user => user && user !== '\\N');
  const credit = authors.length ? ` · ${authors.map(escapeHTML).join(' / ')}` : '';
  return `<article class="example">
    <p>${escapeHTML(item.e)}</p>
    <p class="example-zh">${escapeHTML(item.z)}</p>
    <div class="example-source">来源：<a href="${englishUrl}">英文句 #${item.ei}</a> · <a href="${chineseUrl}">中文句 #${item.zi}</a>${credit}</div>
  </article>`;
}

function renderExamples(items = []) {
  if (!items.length) return '';
  const first = renderExample(items[0]);
  const more = items.slice(1);
  return `<section class="result-group">
    <div class="result-group-head"><h2>双语例句</h2><span>Tatoeba · ${items.length} 组</span></div>
    <div class="example-list">${first}</div>
    ${more.length ? `<details class="more-examples"><summary>查看另外 ${more.length} 组例句</summary><div class="example-list">${more.map(renderExample).join('')}</div></details>` : ''}
  </section>`;
}

function rankEnglish(items, query) {
  return [...items].sort((a, b) => {
    const sourceA = a.x === 'fd' ? 0 : 1;
    const sourceB = b.x === 'fd' ? 0 : 1;
    return sourceA - sourceB || a.e.length - b.e.length;
  }).filter((item, index, list) => {
    const key = `${item.x}|${item.e}|${JSON.stringify(item.z)}`;
    return list.findIndex(other => `${other.x}|${other.e}|${JSON.stringify(other.z)}` === key) === index;
  });
}

function setState(message, error = false) {
  state.hidden = false;
  state.classList.toggle('error', error);
  state.innerHTML = `<div class="rule"></div><p>${escapeHTML(message)}</p>`;
}

async function search(rawValue, updateUrl = true) {
  const raw = rawValue.trim();
  if (!raw) {
    results.innerHTML = '';
    setState('输入词语开始查询。支持简体、繁体中文和英文单词或短语。');
    direction.textContent = '自动识别语言';
    if (updateUrl) history.replaceState(null, '', location.pathname);
    return;
  }

  const language = detectLanguage(raw);
  const query = language === 'en' ? normalizeEnglish(raw) : raw.normalize('NFKC');
  direction.textContent = language === 'zh' ? '中文 → 英文' : 'English → 中文';
  setState('正在查询…');
  results.innerHTML = '';

  try {
    const shardName = shardFor(query, language);
    const [shard, exampleShard] = await Promise.all([
      loadShard(language, shardName),
      loadExampleShard(language, shardName)
    ]);
    const exact = shard[query] || [];
    const examples = exampleShard[query] || [];
    const suggestions = Object.keys(shard).filter(term => term !== query && term.startsWith(query)).slice(0, 12);

    if (!exact.length && !suggestions.length) {
      setState(`没有找到“${raw}”。请尝试更短的词语或检查拼写。`);
    } else {
      state.hidden = true;
      const cards = language === 'zh'
        ? exact.slice(0, 30).map(renderChineseCard).join('')
        : rankEnglish(exact, query).slice(0, 30).map(renderEnglishCard).join('');
      results.innerHTML = `${exact.length ? `<section class="result-group">
        <div class="result-group-head"><h2>查询结果</h2><span>${exact.length} 条匹配</span></div>
        <div class="cards">${cards}</div>
      </section>` : ''}
      ${renderExamples(examples)}
      ${suggestions.length ? `<section class="result-group">
        <div class="result-group-head"><h2>相关词语</h2><span>继续查询</span></div>
        <div class="suggestions">${suggestions.map(term => `<button class="chip" type="button" data-query="${escapeHTML(term)}">${escapeHTML(term)}</button>`).join('')}</div>
      </section>` : ''}`;
    }
    saveHistory(raw);
    if (updateUrl) history.replaceState(null, '', `?q=${encodeURIComponent(raw)}`);
  } catch (error) {
    console.error(error);
    setState('暂时无法读取词典数据。请刷新页面后重试。', true);
  }
}

form.addEventListener('submit', event => { event.preventDefault(); search(input.value); });
document.addEventListener('click', event => {
  const button = event.target.closest('[data-query]');
  if (!button) return;
  input.value = button.dataset.query;
  search(input.value);
  input.focus();
});
clearHistory.addEventListener('click', () => { localStorage.removeItem(HISTORY_KEY); renderHistory(); });
input.addEventListener('input', () => {
  const value = input.value.trim();
  direction.textContent = value ? (detectLanguage(value) === 'zh' ? '中文 → 英文' : 'English → 中文') : '自动识别语言';
});

fetch('./data/manifest.json').then(response => response.json()).then(manifest => {
  const cc = manifest.sources.ccCedict;
  const fd = manifest.sources.freeDict;
  const examples = manifest.sources.tatoeba?.pairs || 0;
  dataVersion.textContent = `CC-CEDICT ${cc.entries.toLocaleString()} 条 · FreeDict ${fd.entries.toLocaleString()} 条 · 例句 ${examples.toLocaleString()} 组`;
}).catch(() => { dataVersion.textContent = '离线词典数据'; });

renderHistory();
const initialQuery = new URLSearchParams(location.search).get('q');
if (initialQuery) { input.value = initialQuery; search(initialQuery, false); }
