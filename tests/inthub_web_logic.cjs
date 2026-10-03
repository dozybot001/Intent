// Pure copy/render/controller tests. No browser, screenshot or visual validation.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const root = path.join(__dirname, '../apps/inthub_web/static');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    id, value: '', innerHTML: '', textContent: '', dataset: {}, scrollTop: 0,
    classList: {add() {}, remove() {}, toggle() {}, contains() {return false;}},
    setAttribute() {}, removeAttribute() {}, addEventListener() {},
    querySelectorAll() {return [];}, querySelector() {return null;},
    focus() {}, setSelectionRange() {}, matches() {return false;},
  });
  return nodes.get(id);
}
const document = {
  body: {querySelectorAll() {return [];}}, documentElement: {},
  getElementById: node, querySelectorAll() {return [];},
  querySelector: node, createTreeWalker() {return {nextNode() {return null;}};},
  activeElement: node('focus'),
};
const context = {document, NodeFilter: {SHOW_TEXT: 4}, navigator: {language: 'zh-CN'},
  localStorage: {getItem() {return 'zh-CN';}, setItem() {}},
  window: {dispatchEvent() {}, setTimeout() {}, clearTimeout() {}},
  Event, URLSearchParams, Intl, console, assert,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'i18n.js'), 'utf8'), context);
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
vm.runInContext(app.replace(/init\(\);\s*$/, ''), context);
for (const file of ['app.js', 'help.js']) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  for (const match of source.matchAll(/\bt\("((?:[^"\\]|\\.)*)"/g)) {
    const key = JSON.parse('"' + match[1] + '"');
    assert.ok(Object.hasOwn(context.window.IntHubI18n.zh, key), 'missing translation: ' + key);
  }
}
vm.runInContext(`
  assert.equal(t('About IntHub'), '关于 IntHub');
  assert.equal(t('Load more ({count})', {count: 7}), '加载更多（7）');
  state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};
  state.overview = {active_intents: [{id:'intent-001', remote_id:'w__intent-001', what:'Next', why:'User text', status:'active', decision_ids:[]}], other_intents: []};
  renderIntentsTab();
  assert.ok(el.sidebarBody.innerHTML.includes('活跃目标'));
  assert.ok(el.sidebarBody.innerHTML.includes('>Next</strong>'));
  assert.ok(el.sidebarBody.innerHTML.includes('User text'));
  const payload = {workspace_id: 'w', snap: {id:'snap-001', what:'Verified: Original user facts. Boundary: Next. Next: Continue user work.', why:'', created_at:'2026-10-04T00:00:00Z'}, intent: {id:'intent-001', what:'Next', status:'active'}};
  const rendered = buildSnapDetailHtml(payload);
  assert.ok(rendered.includes('接续检查点'));
  assert.ok(rendered.includes('Original user facts'));
  assert.ok(rendered.includes('Continue user work'));
  state.searchQuery = 'unsent user query';
  el.tokenOutput.value = 'sensitive clipboard value';
  window.IntHubI18n.setLanguage('en');
  renderIntentsTab();
  assert.ok(el.sidebarBody.innerHTML.includes('Active objectives'));
  assert.equal(state.searchQuery, 'unsent user query');
  assert.equal(el.tokenOutput.value, 'sensitive clipboard value');
  setButtonBusy(el.tokenBtn, true, 'Creating token…', 'Access token');
  assert.equal(el.tokenBtn.disabled, true);
  assert.equal(el.tokenBtn.textContent, 'Creating token…');
  window.IntHubI18n.setLanguage('zh-CN');
  setButtonBusy(el.tokenBtn, false, 'Creating token…', 'Access token');
  assert.equal(el.tokenBtn.disabled, false);
  assert.equal(el.tokenBtn.textContent, '访问令牌');
`, context);
console.log('Bilingual rendering, user-content preservation and immediate button-state tests passed.');

async function redirectCase(destination, failure = false) {
  const elements = new Map();
  const events = new Map();
  const get = id => {
    if (!elements.has(id)) {
      const classes = new Set();
      elements.set(id, {textContent: '', href: '', disabled: false,
        classList: {add(x) {classes.add(x);}, remove(x) {classes.delete(x);}, contains(x) {return classes.has(x);}},
        addEventListener(event, fn) {events.set(id + ':' + event, fn);}, setAttribute() {},
      });
    }
    return elements.get(id);
  };
  let calls = 0;
  let moved = '';
  const cx = {
    window: {dispatchEvent() {}, addEventListener() {}}, navigator: {language: 'zh-CN'},
    document: {body: {querySelectorAll() {return [];}}, documentElement: {},
      createTreeWalker() {return {nextNode() {return null;}};}, getElementById: get, querySelector() {return get('language');}, querySelectorAll() {return [];},
    },
    localStorage: {getItem() {return 'zh-CN';}}, NodeFilter: {SHOW_TEXT: 4},
    location: {search: '?return_to=https://evil.example', replace(url) {moved = url;}},
    URL, URLSearchParams, AbortController, Event, setTimeout, clearTimeout,
    requestAnimationFrame(fn) {fn();},
    fetch: async (_, options) => {
      calls++;
      assert.equal(JSON.parse(options.body).return_to, '/');
      assert.equal(options.method, 'POST');
      if (failure) { const e = new Error('timeout'); e.name = 'AbortError'; throw e; }
      return {ok: true, json: async () => ({ok: true, result: {authorizationUrl: destination}})};
    },
  };
  vm.createContext(cx);
  vm.runInContext(fs.readFileSync(path.join(root, 'i18n.js'), 'utf8'), cx);
  vm.runInContext(fs.readFileSync(path.join(root, 'auth-redirect.js'), 'utf8'), cx);
  await new Promise(resolve => setImmediate(resolve));
  if (failure || !destination.startsWith('https://account.tenon.asia/')) {
    assert.equal(moved, '');
    assert.equal(get('transition-retry').disabled, false);
    assert.ok(get('transition-spinner').classList.contains('is-hidden'));
    assert.ok(get('transition-error').textContent.includes(failure ? '超时' : '无法准备'));
    await events.get('transition-retry:click')();
    assert.equal(calls, 2);
  } else assert.equal(moved, destination);
  assert.equal(get('transition-return').href, '/');
}
(async () => {
  await redirectCase('https://account.tenon.asia/api/auth/oauth2/authorize?state=fresh');
  await redirectCase('https://evil.example/authorize');
  await redirectCase('', true);
  console.log('Fixed transition destination, timeout, retry and safe return tests passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
