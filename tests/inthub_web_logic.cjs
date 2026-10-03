// Pure copy/render/controller tests. No browser, screenshot or visual validation.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const root = path.join(__dirname, '../apps/inthub_web/static');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) {
    const classes = new Set();
    const attributes = new Map();
    nodes.set(id, {
    id, value: '', innerHTML: '', textContent: '', dataset: {}, scrollTop: 0,
    isConnected: true,
    classList: {
      add(...names) {for (const name of names) classes.add(name);},
      remove(...names) {for (const name of names) classes.delete(name);},
      toggle(name, force) {const on = force ?? !classes.has(name); if (on) classes.add(name); else classes.delete(name); return on;},
      contains(name) {return classes.has(name);},
    },
    setAttribute(key, value) {attributes.set(key, String(value));}, removeAttribute(key) {attributes.delete(key);}, getAttribute(key) {return attributes.get(key);}, addEventListener() {},
    querySelectorAll() {return [];}, querySelector() {return null;},
    focus() {}, setSelectionRange() {}, matches() {return false;},
  });
  }
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
  window: {dispatchEvent() {}, setTimeout() {}, clearTimeout() {}, location: {pathname: '/', search: ''}, history: {replaceState() {}}},
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
  assert.equal(continuationHealth([]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Next: work.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Boundary: UI only. Next: review. Blocker: none.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: none.'}}]).ready, true);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: waiting for access.'}}]).ready, false);
  state.overview = {active_intents: [
    {id:'intent-001', workspace_id:'w1', what:'User goal one'},
    {id:'intent-001', workspace_id:'w2', what:'User goal two'},
  ]};
  const timelineSnaps = [
    {id:'snap-001', workspace_id:'w1', intent_id:'intent-001', remote_id:'w1__snap-001', what:'first'},
    {id:'snap-002', workspace_id:'w1', intent_id:'intent-001', remote_id:'w1__snap-002', what:'second'},
    {id:'snap-001', workspace_id:'w2', intent_id:'intent-001', remote_id:'w2__snap-001', what:'other workspace'},
  ];
  const filterOptions = timelineIntentOptions(timelineSnaps);
  assert.equal(filterOptions.length, 2);
  assert.equal(filterOptions[0].count, 2);
  assert.equal(filterOptions[1].label, 'User goal two');
  state.overview.recent_snaps = timelineSnaps;
  state._timelineIntentKey = 'w2__intent-001';
  renderSnapsTab();
  assert.ok(el.sidebarBody.innerHTML.includes('data-remote-id="w2__snap-001"'));
  assert.ok(!el.sidebarBody.innerHTML.includes('data-remote-id="w1__snap-001"'));
  assert.ok(el.sidebarBody.innerHTML.includes('User goal two'));
  assert.ok(detailErrorHtml(new Error('offline'), 'snap', 'w__snap-001').includes('data-retry-detail="detail"'));
  assert.ok(detailErrorHtml(new Error('offline'), 'snap', 'w__snap-001', 'drawer').includes('data-retry-detail="drawer"'));
`, context);
console.log('Bilingual rendering, user-content preservation, truthful checkpoint health and scoped timeline filter tests passed.');

async function viewControllerCases() {
  await vm.runInContext(`(async () => {
    const savedFetch = fetchJson;
    const savedRender = renderSnapDetail;
    const savedRenderTo = renderSnapDetailTo;
    const savedSidebar = renderSidebar;
    const savedSelector = renderProjectSelector;
    const savedSummary = renderProjectSummary;
    const deferred = () => {let resolve, reject; const promise = new Promise((yes, no) => {resolve=yes; reject=no;}); return {promise, resolve, reject};};
    state.config = {apiBaseUrl:''};
    state.currentProjectId = 'p';
    state.activeTab = 'snaps';
    state._workspaceProjectMap = {w:'p'};
    state.overview = {workspaces: [{workspace_id:'w'}]};
    let responses = new Map();
    fetchJson = url => responses.get(url).promise;
    renderSnapDetail = payload => {el.detailContent.innerHTML = payload.name;};
    renderSnapDetailTo = (target, payload) => {target.innerHTML = payload.name;};

    const first = deferred(), next = deferred();
    responses.set('/api/v1/snaps/w__snap-001', first);
    responses.set('/api/v1/snaps/w__snap-002', next);
    const firstRequest = openDetail('snap','w__snap-001');
    await Promise.resolve();
    const nextRequest = openDetail('snap','w__snap-002');
    await Promise.resolve();
    next.resolve({name:'newest detail'});
    await nextRequest;
    first.resolve({name:'stale detail'});
    await firstRequest;
    assert.equal(el.detailContent.innerHTML, 'newest detail');
    assert.equal(state.selectedDetail.remoteId, 'w__snap-002');

    el.shell.classList.remove('detail-open');
    responses.set('/api/v1/snaps/w__snap-002', {promise:Promise.resolve({name:'automatic preview'})});
    await openDetail('snap','w__snap-002',{reveal:false});
    assert.equal(el.shell.classList.contains('detail-open'), false);
    assert.equal(el.detailContent.innerHTML, 'automatic preview');

    const drawerPending = deferred();
    responses.set('/api/v1/snaps/w__snap-001', drawerPending);
    const drawerRequest = openInDrawer('snap','w__snap-001');
    assert.equal(el.drawer.inert, false);
    assert.equal(el.drawer.getAttribute('aria-modal'), 'true');
    closeDrawer();
    drawerPending.resolve({name:'closed drawer must stay empty'});
    await drawerRequest;
    assert.equal(el.drawer.inert, true);
    assert.equal(el.drawerContent.innerHTML, '');
    assert.equal(state._drawerPayload, null);

    state.activeTab = 'search';
    state._searchBusy = false;
    const searchPending = deferred();
    responses.set('/api/v1/search?project_id=p&q=goal', searchPending);
    const searchRequest = runSearch('goal', el.tokenBtn);
    assert.equal(el.tokenBtn.disabled, true);
    state.activeTab = 'snaps';
    beginViewRequest('search');
    state._searchBusy = false;
    el.sidebarBody.innerHTML = 'timeline stays intact';
    searchPending.resolve({matches:[{what:'late search result'}]});
    await searchRequest;
    assert.equal(el.sidebarBody.innerHTML, 'timeline stays intact');
    assert.equal(state._searchResults?.matches?.[0]?.what, undefined);

    state.activeTab = 'overview';
    state._loadedProjectId = 'p';
    state.overview = {project:{id:'p'}, workspaces:[{workspace_id:'w'}]};
    state.handoff = {intents:[]};
    renderSidebar = () => {};
    renderProjectSelector = () => {};
    renderProjectSummary = () => {el.detailContent.innerHTML = state.overview.project.id;};
    const oneOverview = deferred(), oneHandoff = deferred(), twoOverview = deferred(), twoHandoff = deferred();
    responses.set('/api/v1/projects/p1/overview', oneOverview);
    responses.set('/api/v1/projects/p1/handoff', oneHandoff);
    responses.set('/api/v1/projects/p2/overview', twoOverview);
    responses.set('/api/v1/projects/p2/handoff', twoHandoff);
    const loadOne = loadProject('p1');
    const loadTwo = loadProject('p2');
    twoOverview.resolve({project:{id:'p2',name:'second'},workspaces:[{workspace_id:'w2'}]});
    twoHandoff.resolve({intents:[]});
    await loadTwo;
    oneOverview.resolve({project:{id:'p1',name:'first'},workspaces:[{workspace_id:'w1'}]});
    oneHandoff.resolve({intents:[]});
    await loadOne;
    assert.equal(state.currentProjectId, 'p2');
    assert.equal(state.overview.project.id, 'p2');
    assert.equal(el.detailContent.innerHTML, 'p2');

    responses.set('/api/v1/projects/failing/overview', {promise:Promise.reject(new Error('offline'))});
    responses.set('/api/v1/projects/failing/handoff', {promise:Promise.resolve({intents:[]})});
    await assert.rejects(() => loadProject('failing'), /offline/);
    assert.equal(state.currentProjectId, 'p2');
    assert.equal(state.overview.project.id, 'p2');

    state.activeTab = 'search';
    state._searchBusy = false;
    responses.set('/api/v1/search?project_id=p2&q=goal', {promise:Promise.reject(new Error('offline'))});
    await runSearch('goal', el.tokenBtn);
    assert.equal(state._searchBusy, false);
    assert.equal(el.tokenBtn.disabled, false);
    assert.ok(document.getElementById('search-results').innerHTML.includes('data-retry-search'));

    fetchJson=savedFetch; renderSnapDetail=savedRender; renderSnapDetailTo=savedRenderTo;
    renderSidebar=savedSidebar; renderProjectSelector=savedSelector; renderProjectSummary=savedSummary;
  })()`, context);
  console.log('Latest-action ownership, closed-drawer cancellation, mobile preview, project rollback and search recovery tests passed.');
}

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
  await viewControllerCases();
  await redirectCase('https://account.tenon.asia/api/auth/oauth2/authorize?state=fresh');
  await redirectCase('https://evil.example/authorize');
  await redirectCase('', true);
  console.log('Fixed transition destination, timeout, retry and safe return tests passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
