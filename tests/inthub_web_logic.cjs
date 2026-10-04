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
    events: new Map(),
    setAttribute(key, value) {attributes.set(key, String(value));}, removeAttribute(key) {attributes.delete(key);}, getAttribute(key) {return attributes.get(key);},
    addEventListener(type, fn) {this.events.set(type, [...(this.events.get(type) || []), fn]);},
    querySelectorAll() {return [];}, querySelector() {return null;},
    focus() {document.activeElement = this;}, setSelectionRange() {}, matches() {return false;},
    contains(other) {return other === this;}, closest() {return null;},
    getClientRects() {return this.hidden || classes.has('is-hidden') ? [] : [{}];},
    showModal() {this.open=true; document.activeElement=this;},
    close() {this.open=false; for(const handler of this.events.get('close') || []) handler();},
  });
  }
  return nodes.get(id);
}
const document = {
  body: {querySelectorAll() {return [];}}, documentElement: {style: {setProperty() {}}},
  getElementById: node, querySelectorAll() {return [];},
  querySelector: node, createTreeWalker() {return {nextNode() {return null;}};},
  activeElement: node('focus'),
  events: new Map(), addEventListener(type, fn) {this.events.set(type, [...(this.events.get(type) || []), fn]);},
};
const context = {document, NodeFilter: {SHOW_TEXT: 4}, navigator: {language: 'zh-CN'},
  localStorage: {getItem() {return 'zh-CN';}, setItem() {}},
  window: {dispatchEvent() {}, addEventListener() {}, setTimeout() {}, clearTimeout() {}, location: {pathname: '/', search: ''}, history: {replaceState() {}}},
  innerHeight: 900, innerWidth: 1440, Event, URLSearchParams, Intl, console, assert,
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
  state.overview = {active_intents: [{id:'intent-001', remote_id:'p__intent-001', what:'Next', why:'User text', status:'active', decision_ids:[]}], other_intents: []};
  renderIntentsTab();
  assert.ok(el.sidebarBody.innerHTML.includes('活跃目标'));
  assert.ok(el.sidebarBody.innerHTML.includes('>Next</strong>'));
  assert.ok(el.sidebarBody.innerHTML.includes('User text'));
  const payload = {project_id: 'p', snap: {id:'snap-001', what:'Verified: Original user facts. Boundary: Next. Next: Continue user work.', why:'', created_at:'2026-10-04T00:00:00Z'}, intent: {id:'intent-001', what:'Next', status:'active'}};
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
  assert.equal(el.tokenBtn.classList.contains('action-busy'), true);
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
    {id:'intent-001', project_id:'p1', what:'User goal one'},
    {id:'intent-001', project_id:'p2', what:'User goal two'},
  ]};
  const timelineSnaps = [
    {id:'snap-001', project_id:'p1', intent_id:'intent-001', remote_id:'p1__snap-001', what:'first'},
    {id:'snap-002', project_id:'p1', intent_id:'intent-001', remote_id:'p1__snap-002', what:'second'},
    {id:'snap-001', project_id:'p2', intent_id:'intent-001', remote_id:'p2__snap-001', what:'other project'},
  ];
  const filterOptions = timelineIntentOptions(timelineSnaps);
  assert.equal(filterOptions.length, 2);
  assert.equal(filterOptions[0].count, 2);
  assert.equal(filterOptions[1].label, 'User goal two');
  state.overview.recent_snaps = timelineSnaps;
  state._timelineIntentKey = 'p2__intent-001';
  renderSnapsTab();
  assert.ok(el.sidebarBody.innerHTML.includes('data-remote-id="p2__snap-001"'));
  assert.ok(!el.sidebarBody.innerHTML.includes('data-remote-id="p1__snap-001"'));
  assert.ok(el.sidebarBody.innerHTML.includes('User goal two'));
  assert.ok(detailErrorHtml(new Error('offline'), 'snap', 'p__snap-001').includes('data-retry-detail="detail"'));
  assert.ok(detailErrorHtml(new Error('offline'), 'snap', 'p__snap-001', 'drawer').includes('data-retry-detail="drawer"'));
  const navigation = document.getElementById('navigation-card');
  navigation.matches = selector => selector.includes('.card');
  setButtonBusy(navigation, true);
  assert.notEqual(navigation.disabled, true);
  assert.equal(navigation.classList.contains('action-busy'), false);
  assert.equal(navigation.getAttribute('aria-busy'), undefined);
  setProjectPickerBusy(true);
  assert.equal(el.projectPickerTrigger.getAttribute('aria-busy'), 'true');
  assert.equal(el.projectPickerTrigger.classList.contains('action-busy'), false);
  setProjectPickerBusy(false);
  const waitingMarkup = viewLoadingHtml();
  assert.ok(waitingMarkup.includes('class="view-loading" role="status"'));
  assert.ok(waitingMarkup.includes('class="view-loading-spinner" aria-hidden="true"'));
  assert.ok(waitingMarkup.includes('<p data-view-loading-copy>正在加载…</p>'));
  const originalLoadingQuery = document.querySelectorAll;
  const loadingCaption = document.getElementById('loading-caption');
  document.querySelectorAll = selector => selector === '[data-view-loading-copy]' ? [loadingCaption] : originalLoadingQuery(selector);
  el.detailContent.innerHTML = waitingMarkup;
  window.IntHubI18n.setLanguage('en');
  localizeViewLoadingCopy();
  assert.equal(loadingCaption.textContent,'Loading…');
  assert.ok(el.detailContent.innerHTML.includes('view-loading-spinner'));
  window.IntHubI18n.setLanguage('zh-CN');
  document.querySelectorAll = originalLoadingQuery;
`, context);
console.log('Bilingual rendering, user-content preservation, truthful checkpoint health and scoped timeline filter tests passed.');

async function headerMenuCases() {
  await vm.runInContext(`(async () => {
    const originalQueryAll = document.querySelectorAll;
    const settingsTrigger = document.getElementById('settings-menu-trigger');
    const settingsPanel = document.getElementById('settings-menu');
    const authSettingsTrigger = document.getElementById('auth-settings-menu-trigger');
    const authSettingsPanel = document.getElementById('auth-settings-menu');
    const languageChinese = document.getElementById('language-chinese');
    const languageEnglish = document.getElementById('language-english');
    const aboutButton = document.getElementById('menu-about-button');
    languageChinese.dataset.languageSelect = 'zh-CN';
    languageEnglish.dataset.languageSelect = 'en';
    settingsTrigger.setAttribute('aria-controls','settings-menu');
    authSettingsTrigger.setAttribute('aria-controls','auth-settings-menu');
    settingsPanel.querySelectorAll = () => [languageChinese, languageEnglish, aboutButton];
    settingsPanel.contains = target => target === settingsPanel || target === languageChinese || target === languageEnglish || target === aboutButton;
    authSettingsPanel.querySelectorAll = () => [languageEnglish];
    document.querySelectorAll = selector => selector === '[data-settings-trigger]' ? [settingsTrigger, authSettingsTrigger] : selector === '[data-language-select]' ? [languageChinese, languageEnglish] : selector === '[data-about-open]' ? [aboutButton] : originalQueryAll(selector);
    bindEvents();
    const dispatch = (type, target, key, extra={}) => {
      let stopped=false;
      const event={target,key,preventDefault(){},stopImmediatePropagation(){stopped=true;},...extra};
      for(const listener of document.events.get(type) || []) {listener(event);if(stopped)break;}
    };
    toggleHeaderMenu(settingsTrigger);
    assert.equal(settingsPanel.classList.contains('is-open'),true);
    assert.equal(settingsPanel.inert,false);
    toggleHeaderMenu(el.accountMenuTrigger);
    assert.equal(settingsPanel.classList.contains('is-open'),false);
    assert.equal(settingsPanel.inert,true);
    assert.equal(el.accountActions.classList.contains('is-open'),true);
    toggleHeaderMenu(authSettingsTrigger);
    assert.equal(el.accountActions.classList.contains('is-open'),false);
    assert.equal(authSettingsPanel.classList.contains('is-open'),true);
    toggleProjectPicker(true);
    assert.equal(authSettingsPanel.classList.contains('is-open'),false);
    assert.equal(el.projectPickerDropdown.classList.contains('is-open'),true);

    closeHeaderMenus();
    dispatch('keydown',settingsTrigger,'ArrowDown');
    assert.equal(settingsPanel.classList.contains('is-open'),true);
    assert.equal(document.activeElement,languageChinese);
    assert.equal(el.projectPickerDropdown.classList.contains('is-open'),false);
    dispatch('keydown',languageChinese,'ArrowDown');
    assert.equal(document.activeElement,languageEnglish);
    dispatch('keydown',languageEnglish,'Escape');
    assert.equal(settingsPanel.classList.contains('is-open'),false);
    assert.equal(document.activeElement,settingsTrigger);
    toggleHeaderMenu(settingsTrigger,{focus:'first'});
    dispatch('keydown',languageChinese,'Tab',{shiftKey:true});
    assert.equal(settingsPanel.classList.contains('is-open'),true);
    document.activeElement=settingsTrigger;
    dispatch('focusin',settingsTrigger);
    assert.equal(settingsPanel.classList.contains('is-open'),true);
    dispatch('keydown',settingsTrigger,'Tab',{shiftKey:true});
    assert.equal(settingsPanel.inert,false);
    document.activeElement=el.searchTrigger;
    dispatch('focusin',el.searchTrigger);
    assert.equal(settingsPanel.classList.contains('is-open'),false);
    toggleHeaderMenu(settingsTrigger);
    dispatch('keydown',document.getElementById('outside-menu'),'Escape');
    assert.equal(settingsPanel.classList.contains('is-open'),false);
    assert.equal(document.activeElement,settingsTrigger);
    toggleHeaderMenu(settingsTrigger);
    document.activeElement=aboutButton;
    dispatch('keydown',aboutButton,'Tab');
    assert.equal(settingsPanel.inert,false);
    document.activeElement=el.accountMenuTrigger;
    dispatch('focusin',el.accountMenuTrigger);
    assert.equal(settingsPanel.inert,true);
    toggleHeaderMenu(settingsTrigger);
    dispatch('click',document.getElementById('outside-menu'));
    assert.equal(settingsPanel.classList.contains('is-open'),false);
    toggleHeaderMenu(settingsTrigger);
    aboutButton.events.get('click')[0]();
    assert.equal(el.aboutDialog.open,true);
    assert.equal(settingsPanel.inert,true);
    el.aboutDialog.close();
    assert.equal(document.activeElement,settingsTrigger);
    el.tokenDialog.showModal();
    el.tokenDialog.close();
    assert.equal(document.activeElement,el.accountMenuTrigger);

    window.IntHubI18n.setLanguage('en');
    assert.equal(languageEnglish.getAttribute('aria-pressed'),'true');
    assert.equal(languageChinese.getAttribute('aria-pressed'),'false');
    window.IntHubI18n.setLanguage('zh-CN');
    assert.equal(languageChinese.classList.contains('is-selected'),true);

    state.config={authRequired:true};
    state.account={display_name:'Actual signed-in user'};
    hideAuthGate();
    assert.equal(el.accountLabel.textContent,'Actual signed-in user');
    assert.equal(el.tokenBtn.classList.contains('is-hidden'),false);
    el.drawer.classList.add('open');
    showAuthGate();
    assert.equal(el.shell.inert,true);
    assert.equal(el.drawer.inert,true);
    assert.equal(el.drawer.classList.contains('open'),false);
    const gatedTab=state.activeTab;
    dispatch('keydown',document.getElementById('outside-menu'),'k',{ctrlKey:true});
    assert.equal(state.activeTab,gatedTab);
    dispatch('keydown',authSettingsTrigger,'ArrowDown');
    assert.equal(authSettingsPanel.classList.contains('is-open'),true);
    hideAuthGate();
    assert.equal(el.shell.inert,false);
    closeHeaderMenus();

    const originalLoadProjects=loadProjects;
    let finishRefresh;
    loadProjects=() => new Promise(resolve=>{finishRefresh=resolve;});
    const refreshRequest=el.refreshBtn.events.get('click')[0]();
    assert.equal(el.refreshBtn.disabled,true);
    assert.equal(el.refreshBtn.textContent,'正在刷新项目数据');
    assert.equal(el.refreshBtn.classList.contains('action-busy'),true);
    finishRefresh();
    await refreshRequest;
    assert.equal(el.refreshBtn.disabled,false);
    assert.equal(el.refreshBtn.textContent,'刷新项目数据');
    loadProjects=originalLoadProjects;
    document.querySelectorAll=originalQueryAll;
  })()`, context);
  console.log('Mutually exclusive settings/account/project menus, keyboard/outside dismissal and language selection tests passed.');
}

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
    state.overview = {history:{project_id:'p',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}};
    let responses = new Map();
    fetchJson = url => responses.get(url).promise;
    renderSnapDetail = payload => {el.detailContent.innerHTML = payload.name;};
    renderSnapDetailTo = (target, payload) => {target.innerHTML = payload.name;};

    const first = deferred(), next = deferred();
    responses.set('/api/v1/snaps/p__snap-001', first);
    responses.set('/api/v1/snaps/p__snap-002', next);
    const firstRequest = openDetail('snap','p__snap-001');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'true');
    assert.ok(el.detailContent.innerHTML.includes('view-loading-spinner'));
    assert.equal(state.selectedDetail.remoteId, 'p__snap-001');
    assert.equal(el.shell.classList.contains('detail-open'), true);
    await Promise.resolve();
    const nextRequest = openDetail('snap','p__snap-002');
    await Promise.resolve();
    next.resolve({name:'newest detail'});
    await nextRequest;
    first.resolve({name:'stale detail'});
    await firstRequest;
    assert.equal(el.detailContent.innerHTML, 'newest detail');
    assert.equal(state.selectedDetail.remoteId, 'p__snap-002');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');

    const stale = deferred(), pending = deferred();
    responses.set('/api/v1/snaps/p__snap-003', stale);
    responses.set('/api/v1/snaps/p__snap-004', pending);
    const staleRequest = openDetail('snap','p__snap-003');
    await Promise.resolve();
    const pendingRequest = openDetail('snap','p__snap-004');
    await Promise.resolve();
    stale.resolve({name:'old response finishes first'});
    await staleRequest;
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'true');
    assert.ok(el.detailContent.innerHTML.includes('loading'));
    pending.resolve({name:'latest finished'});
    await pendingRequest;
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');

    responses.set('/api/v1/snaps/p__snap-004', {promise:Promise.reject(new Error('offline'))});
    await assert.rejects(() => openDetail('snap','p__snap-004'), /offline/);
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');
    assert.ok(el.detailContent.innerHTML.includes('data-retry-detail="detail"'));

    el.shell.classList.remove('detail-open');
    responses.set('/api/v1/snaps/p__snap-002', {promise:Promise.resolve({name:'automatic preview'})});
    await openDetail('snap','p__snap-002',{reveal:false});
    assert.equal(el.shell.classList.contains('detail-open'), false);
    assert.equal(el.detailContent.innerHTML, 'automatic preview');

    const drawerPending = deferred();
    responses.set('/api/v1/snaps/p__snap-001', drawerPending);
    const drawerRequest = openInDrawer('snap','p__snap-001');
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'true');
    assert.ok(el.drawerContent.innerHTML.includes('view-loading-spinner'));
    assert.equal(el.drawer.inert, false);
    assert.equal(el.drawer.getAttribute('aria-modal'), 'true');
    closeDrawer();
    drawerPending.resolve({name:'closed drawer must stay empty'});
    await drawerRequest;
    assert.equal(el.drawer.inert, true);
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'false');
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
    state.overview = {project:{id:'p'}, history:{project_id:'p',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}};
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
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'true');
    state.authenticated=true;
    const pendingProjectMarkup=el.detailContent.innerHTML;
    localizeWorkspace();
    assert.equal(el.detailContent.innerHTML,pendingProjectMarkup);
    assert.ok(el.detailContent.innerHTML.includes('overview-skeleton'));
    twoOverview.resolve({project:{id:'p2',name:'second'},history:{project_id:'p2',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}});
    twoHandoff.resolve({intents:[]});
    await loadTwo;
    oneOverview.resolve({project:{id:'p1',name:'first'},history:{project_id:'p1',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}});
    oneHandoff.resolve({intents:[]});
    await loadOne;
    assert.equal(state.currentProjectId, 'p2');
    assert.equal(state.overview.project.id, 'p2');
    assert.equal(el.detailContent.innerHTML, 'p2');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');
    state.overview={project:{id:'p2'},history:{project_id:'p2',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}};
    el.detailContent.innerHTML=viewLoadingHtml();
    const pendingDetailMarkup=el.detailContent.innerHTML;
    setViewBusy('detail',true);
    localizeWorkspace();
    assert.equal(el.detailContent.innerHTML,pendingDetailMarkup);
    assert.ok(el.detailContent.innerHTML.includes('view-loading-spinner'));
    setViewBusy('detail',false);

    responses.set('/api/v1/projects/failing/overview', {promise:Promise.reject(new Error('offline'))});
    responses.set('/api/v1/projects/failing/handoff', {promise:Promise.resolve({intents:[]})});
    await assert.rejects(() => loadProject('failing'), /offline/);
    assert.equal(state.currentProjectId, 'p2');
    assert.equal(state.overview.project.id, 'p2');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');

    responses.set('/api/v1/projects/empty/overview', {promise:Promise.resolve({project:{id:'empty',name:'empty'},history:{revision:null}})});
    responses.set('/api/v1/projects/empty/handoff', {promise:Promise.resolve({intents:[]})});
    await loadProject('empty');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');
    state.currentProjectId='p2';

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
  await headerMenuCases();
  await viewControllerCases();
  await redirectCase('https://account.tenon.asia/api/auth/oauth2/authorize?state=fresh');
  await redirectCase('https://evil.example/authorize');
  await redirectCase('', true);
  console.log('Fixed transition destination, timeout, retry and safe return tests passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
