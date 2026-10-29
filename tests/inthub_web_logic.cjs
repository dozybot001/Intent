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
const routes = [];
const history = {
  state: null,
  replaceState(state) {this.state = state; routes.push('replace');},
  pushState(state) {this.state = state; routes.push('push');},
  back() {routes.push('back');},
};
const context = {document, NodeFilter: {SHOW_TEXT: 4}, navigator: {language: 'zh-CN'},
  localStorage: {getItem() {return 'zh-CN';}, setItem() {}},
  window: {dispatchEvent() {}, addEventListener() {}, setTimeout() {}, clearTimeout() {}, location: {pathname: '/', search: ''}, history},
  innerHeight: 900, innerWidth: 1440, Event, URL, URLSearchParams, Intl, console, assert, routes,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'i18n.js'), 'utf8'), context);
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
vm.runInContext(app.replace(/init\(\);\s*$/, ''), context);
const zh = context.window.IntHubI18n.zh;
for (const file of ['app.js', 'help.js']) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  for (const match of source.matchAll(/\bt\("((?:[^"\\]|\\.)*)"/g)) {
    const key = JSON.parse('"' + match[1] + '"');
    assert.ok(Object.hasOwn(zh, key), 'missing translation: ' + key);
  }
  for (const match of source.matchAll(/\bplural\([^,]+,\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"/g)) {
    for (const key of [match[1], match[2]]) assert.ok(Object.hasOwn(zh, key), 'missing plural translation: ' + key);
  }
  for (const match of source.matchAll(/setButtonBusy\([^,]+,\s*[^,]+,\s*"([^"]+)",\s*"([^"]+)"/g)) {
    for (const key of [match[1], match[2]]) assert.ok(Object.hasOwn(zh, key), 'missing busy translation: ' + key);
  }
}
const markup = fs.readFileSync(path.join(root, 'index.html'), 'utf8').replace(/<script[\s\S]*?<\/script>/g, '');
const untranslated = new Set(['IntHub', '⌘K', 'English', '中文', 'i', 'Esc', '↑', '↓', '↵', '榫卯 Tenon AI', 'tenon.asia', 'itt auth login', 'System', 'Light', 'Dark']);
for (const match of markup.matchAll(/>([^<>]+)</g)) {
  const text = match[1].trim();
  if (text && /[A-Za-z]/.test(text) && !untranslated.has(text)) assert.ok(Object.hasOwn(zh, text), 'missing static translation: ' + text);
}
for (const match of markup.matchAll(/(?:aria-label|placeholder|title)="([^"]+)"/g)) {
  assert.ok(Object.hasOwn(zh, match[1]), 'missing attribute translation: ' + match[1]);
}
vm.runInContext(`
  const deletionUrl = 'https://account.tenon.asia/account/delete/?request=' + 'f'.repeat(43);
  const deletionExpiry = Date.now() + 300000;
  assert.equal(productDeletionDestination({url: deletionUrl, expiresAt: deletionExpiry}), deletionUrl);
  for (const url of [deletionUrl + '&request=' + 'f'.repeat(43), deletionUrl + '&extra=yes', deletionUrl.replace('f'.repeat(43), 'short'), deletionUrl.replace('account.tenon.asia', 'fake.example')]) {
    assert.throws(() => productDeletionDestination({url, expiresAt: deletionExpiry}));
  }
  setButtonBusy(el.deleteAccountBtn, true, 'Opening account management…', 'Delete account');
  assert.equal(el.deleteAccountBtn.disabled, true);
  assert.equal(el.deleteAccountBtn.getAttribute('aria-busy'), 'true');
  assert.equal(el.deleteAccountBtn.textContent, '正在打开账号管理…');
  setButtonBusy(el.deleteAccountBtn, false, 'Opening account management…', 'Delete account');
  assert.equal(t('About IntHub'), '关于 IntHub');
  assert.equal(t('Load more ({count})', {count: 7}), '加载更多（7）');
  assert.equal(highlight('<b>Pay</b> pay', 'pay'), '&lt;b&gt;<mark>Pay</mark>&lt;/b&gt; <mark>pay</mark>');
  assert.equal(highlight('a & b', ''), 'a &amp; b');
  state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};
  state.overview = {active_intents: [{id:'intent-001', remote_id:'p__intent-001', project_id:'p', what:'Next', why:'User text', status:'active', decision_ids:[], snap_ids:['snap-001']}], other_intents: [], recent_snaps: []};
  renderIntentsTab();
  assert.ok(el.detailContent.innerHTML.includes('活跃目标'));
  assert.ok(el.detailContent.innerHTML.includes('intent-entry-title">Next</strong>'));
  assert.ok(el.detailContent.innerHTML.includes('User text'));
  assert.ok(el.detailContent.innerHTML.includes('1 个 Snap'));
  const payload = {project_id: 'p', snap: {id:'snap-001', what:'Verified: Original user facts. Boundary: Next. Next: Continue user work.', why:'', created_at:'2026-10-04T00:00:00Z'}, intent: {id:'intent-001', what:'Next', status:'active'}};
  const rendered = buildSnapDetailHtml(payload);
  assert.ok(rendered.includes('接续检查点'));
  assert.ok(rendered.includes('Original user facts'));
  assert.ok(rendered.includes('Continue user work'));
  assert.ok(rendered.includes('data-detail-type="intent" data-remote-id="p__intent-001"'));
  state.searchQuery = 'unsent user query';
  el.tokenOutput.value = 'sensitive clipboard value';
  window.IntHubI18n.setLanguage('en');
  renderIntentsTab();
  assert.ok(el.detailContent.innerHTML.includes('Active objectives'));
  assert.ok(el.detailContent.innerHTML.includes('1 snap<'));
  assert.equal(state.searchQuery, 'unsent user query');
  assert.equal(el.tokenOutput.value, 'sensitive clipboard value');
  assert.equal(plural(1, '{count} blocked objective', '{count} blocked objectives'), '1 blocked objective');
  assert.equal(plural(2, '{count} blocked objective', '{count} blocked objectives'), '2 blocked objectives');
  setButtonBusy(el.tokenBtn, true, 'Creating token…', 'Access token');
  assert.equal(el.tokenBtn.disabled, true);
  assert.equal(el.tokenBtn.classList.contains('action-busy'), true);
  assert.equal(el.tokenBtn.textContent, 'Creating token…');
  window.IntHubI18n.setLanguage('zh-CN');
  setButtonBusy(el.tokenBtn, false, 'Creating token…', 'Access token');
  assert.equal(el.tokenBtn.disabled, false);
  assert.equal(el.tokenBtn.textContent, '访问令牌');
  assert.ok(statusBadge('active', 'decision').includes('有效'));
  assert.ok(statusBadge('active').includes('进行中'));
  assert.equal(continuationHealth([]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Next: work.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Boundary: UI only. Next: review. Blocker: none.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: none.'}}]).ready, true);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: waiting for access.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: waiting for access.'}}]).label, '1 个目标被阻塞');

  state.overview = {
    project: {id:'p', name:'Checkout <beta>'},
    history: {project_id:'p', revision:'b'.repeat(64), last_synced_at:'2026-10-04T00:00:00Z'},
    active_intents: [], other_intents: [], recent_snaps: [], active_decisions: [], deprecated_decisions: [],
  };
  state.handoff = {
    intents: [{id:'intent-002', remote_id:'p__intent-002', project_id:'p', status:'active', what:'Ship <Apple Pay>', why:'Mobile users convert better.',
      latest_snap: {id:'snap-004', what:'Verified: sheet confirms payments. Boundary: web only. Next: run QA. Blocker: waiting for APM access. Constraints: never trust client totals.', why:'', created_at:'2026-10-04T00:00:00Z'}}],
    suspended_intents: [{id:'intent-001', remote_id:'p__intent-001', project_id:'p', status:'suspend', what:'Port receipts', latest_snap: {id:'snap-001', what:'Next: port refund template.'}}],
    active_decisions: [{id:'decision-001', remote_id:'p__decision-001', what:'Use PaymentIntents only', why:'One SCA path.'}],
  };
  renderProjectSummary();
  const brief = el.detailContent.innerHTML;
  assert.ok(brief.includes('data-copy-brief'));
  assert.ok(brief.includes('Ship &lt;Apple Pay&gt;'));
  assert.ok(!brief.includes('<Apple Pay>'));
  assert.ok(brief.includes('checkpoint-blocker is-blocked'));
  assert.ok(brief.includes('health-pill is-warning'));
  assert.ok(brief.includes('data-detail-type="snap" data-remote-id="p__snap-004"'));
  assert.ok(brief.includes('Port receipts'));
  assert.ok(brief.includes('Use PaymentIntents only'));
  const markdown = briefMarkdown();
  assert.ok(markdown.startsWith('# Checkout <beta> · 接续简报'));
  assert.ok(markdown.includes('## Ship <Apple Pay> (intent-002)'));
  assert.ok(markdown.includes('- **下一步:** run QA'));
  assert.ok(markdown.includes('- **阻塞项:** waiting for APM access'));
  assert.ok(markdown.includes('- **约束：** never trust client totals'));
  assert.ok(markdown.includes('- Port receipts (intent-001)'));
  assert.ok(markdown.includes('- Use PaymentIntents only (decision-001)'));

  state.projects = [{id:'p', name:"Team's checkout"}];
  state.currentProjectId = 'p';
  state.config = {apiBaseUrl: 'https://inthub.example', authRequired: true};
  el.shell.classList.remove('is-empty');
  renderSetupGuide('unlinked');
  const guide = el.detailContent.innerHTML;
  assert.ok(guide.includes(INSTALL_COMMAND.replace(/&/g, '&amp;').replace(/\\|/g, '|')));
  assert.ok(guide.includes('itt init'));
  assert.ok(guide.includes('data-create-token'));
  assert.ok(guide.includes('itt auth login --api-base-url &#39;https://inthub.example&#39;'));
  assert.ok(guide.includes("--project &#39;Team&#39;\\\\&#39;&#39;s checkout&#39;"));
  assert.ok(guide.includes('itt push'));
  assert.equal(el.shell.classList.contains('is-empty'), true);
  state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};

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
  assert.ok(el.detailContent.innerHTML.includes('data-remote-id="p2__snap-001"'));
  assert.ok(!el.detailContent.innerHTML.includes('data-remote-id="p1__snap-001"'));
  assert.ok(el.detailContent.innerHTML.includes('User goal two'));
  assert.ok(el.detailContent.innerHTML.includes('1 个检查点'));
  assert.ok(detailErrorHtml(new Error('offline'), 'snap', 'p__snap-001').includes('data-retry-detail="sheet"'));
  const navigation = document.getElementById('navigation-card');
  navigation.matches = selector => selector.includes('.list-row');
  setButtonBusy(navigation, true);
  assert.notEqual(navigation.disabled, true);
  assert.equal(navigation.classList.contains('action-busy'), false);
  assert.equal(navigation.getAttribute('aria-busy'), undefined);
  setProjectPickerBusy(true);
  assert.equal(el.projectPickerTrigger.getAttribute('aria-busy'), 'true');
  assert.equal(el.projectPickerTrigger.classList.contains('action-busy'), false);
  setProjectPickerBusy(false);
  state.projects = [
    {id:'project-one', name:'项目 <draft> & "review" ' + 'very-long-name-'.repeat(20)},
    {id:'project-two', name:'Resume'},
  ];
  state.currentProjectId = 'project-one';
  renderProjectSelector();
  assert.equal(el.projectPickerLabel.textContent, state.projects[0].name);
  const projectOptions = el.projectPickerDropdown.innerHTML;
  assert.ok(projectOptions.includes('&lt;draft&gt; &amp; &quot;review&quot;'));
  assert.ok(!projectOptions.includes('<draft>'));
  assert.equal((projectOptions.match(/aria-selected="true"/g) || []).length, 1);
  assert.equal((projectOptions.match(/role="option"/g) || []).length, 2);
  assert.ok(projectOptions.includes('共享语义历史'));
  const waitingMarkup = viewLoadingHtml();
  assert.ok(waitingMarkup.includes('class="view-loading" role="status"'));
  assert.ok(waitingMarkup.includes('class="view-loading-spinner" aria-hidden="true"'));
  assert.ok(waitingMarkup.includes('<p data-view-loading-copy>正在加载…</p>'));
  const originalLoadingQuery = document.querySelectorAll;
  const loadingCaption = document.getElementById('loading-caption');
  document.querySelectorAll = selector => selector === '[data-view-loading-copy]' ? [loadingCaption] : originalLoadingQuery(selector);
  el.drawerContent.innerHTML = waitingMarkup;
  window.IntHubI18n.setLanguage('en');
  localizeViewLoadingCopy();
  assert.equal(loadingCaption.textContent,'Loading…');
  assert.ok(el.drawerContent.innerHTML.includes('view-loading-spinner'));
  window.IntHubI18n.setLanguage('zh-CN');
  document.querySelectorAll = originalLoadingQuery;
`, context);
console.log('Bilingual rendering, user-content preservation, truthful checkpoint health, copyable brief, onboarding and scoped timeline filter tests passed.');

async function headerMenuCases() {
  await vm.runInContext(`(async () => {
    const originalQueryAll = document.querySelectorAll;
    const settingsTrigger = document.getElementById('settings-menu-trigger');
    const settingsPanel = document.getElementById('settings-menu');
    const authSettingsTrigger = document.getElementById('auth-settings-menu-trigger');
    const authSettingsPanel = document.getElementById('auth-settings-menu');
    const resourcesTrigger = document.getElementById('resources-menu-trigger');
    const resourcesPanel = document.getElementById('resources-menu');
    const skillLink = document.getElementById('resource-skill-link');
    const repositoryLink = document.getElementById('resource-repository-link');
    const languageChinese = document.getElementById('language-chinese');
    const languageEnglish = document.getElementById('language-english');
    const aboutButton = document.getElementById('menu-about-button');
    languageChinese.dataset.languageSelect = 'zh-CN';
    languageEnglish.dataset.languageSelect = 'en';
    settingsTrigger.setAttribute('aria-controls','settings-menu');
    authSettingsTrigger.setAttribute('aria-controls','auth-settings-menu');
    resourcesTrigger.setAttribute('aria-controls','resources-menu');
    resourcesPanel.querySelectorAll = () => [skillLink, repositoryLink];
    resourcesPanel.contains = target => target === resourcesPanel || target === skillLink || target === repositoryLink;
    settingsPanel.querySelectorAll = () => [languageChinese, languageEnglish, aboutButton];
    settingsPanel.contains = target => target === settingsPanel || target === languageChinese || target === languageEnglish || target === aboutButton;
    authSettingsPanel.querySelectorAll = () => [languageEnglish];
    document.querySelectorAll = selector => selector === '[data-settings-trigger]' ? [settingsTrigger, authSettingsTrigger] : selector === '[data-resources-trigger]' ? [resourcesTrigger] : selector === '[data-language-select]' ? [languageChinese, languageEnglish] : selector === '[data-about-open]' ? [aboutButton] : originalQueryAll(selector);
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

    dispatch('keydown',resourcesTrigger,'ArrowDown');
    assert.equal(el.projectPickerDropdown.classList.contains('is-open'),false);
    assert.equal(resourcesPanel.inert,false);
    assert.equal(resourcesTrigger.getAttribute('aria-expanded'),'true');
    assert.equal(document.activeElement,skillLink);
    dispatch('keydown',skillLink,'End');
    assert.equal(document.activeElement,repositoryLink);
    dispatch('keydown',repositoryLink,'Escape');
    assert.equal(resourcesPanel.inert,true);
    assert.equal(document.activeElement,resourcesTrigger);
    toggleHeaderMenu(resourcesTrigger);
    toggleHeaderMenu(settingsTrigger);
    assert.equal(resourcesPanel.inert,true);
    assert.equal(settingsPanel.inert,false);
    closeHeaderMenus();

    const projectOptions = [document.getElementById('project-option-first'), document.getElementById('project-option-last')];
    const originalProjectContains = el.projectPicker.contains;
    const originalProjectOptions = el.projectPickerDropdown.querySelectorAll;
    el.projectPicker.contains = target => target === el.projectPickerTrigger || projectOptions.includes(target);
    el.projectPickerDropdown.querySelectorAll = () => projectOptions;
    el.projectPickerTrigger.focus();
    dispatch('keydown',el.projectPickerTrigger,'ArrowDown');
    assert.equal(document.activeElement,projectOptions[0]);
    dispatch('keydown',projectOptions[0],'ArrowDown');
    assert.equal(document.activeElement,projectOptions[1]);
    dispatch('keydown',projectOptions[1],'Home');
    assert.equal(document.activeElement,projectOptions[0]);
    dispatch('keydown',projectOptions[0],'End');
    assert.equal(document.activeElement,projectOptions[1]);
    dispatch('keydown',projectOptions[1],'ArrowUp');
    assert.equal(document.activeElement,projectOptions[0]);
    dispatch('keydown',projectOptions[0],'Escape');
    assert.equal(el.projectPickerDropdown.classList.contains('is-open'),false);
    assert.equal(document.activeElement,el.projectPickerTrigger);
    el.projectPicker.contains = originalProjectContains;
    el.projectPickerDropdown.querySelectorAll = originalProjectOptions;

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
    const setupTokenButton = document.getElementById('setup-token-button');
    state._tokenReturnFocus = setupTokenButton;
    el.tokenDialog.showModal();
    el.tokenDialog.close();
    assert.equal(document.activeElement,setupTokenButton);

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
    assert.notEqual(el.searchDialog.open,true);
    dispatch('keydown',authSettingsTrigger,'ArrowDown');
    assert.equal(authSettingsPanel.classList.contains('is-open'),true);
    hideAuthGate();
    assert.equal(el.shell.inert,false);
    closeHeaderMenus();
    dispatch('keydown',document.getElementById('outside-menu'),'k',{metaKey:true});
    assert.equal(el.searchDialog.open,true);
    el.searchDialog.close();

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
  console.log('Mutually exclusive resource/settings/account/project menus, keyboard/outside dismissal, gated search and language selection tests passed.');
}

async function viewControllerCases() {
  await vm.runInContext(`(async () => {
    const savedFetch = fetchJson;
    const savedBuild = buildDetailHtml;
    const savedView = renderView;
    const savedSelector = renderProjectSelector;
    const savedLoadProject = loadProject;
    const deferred = () => {let resolve, reject; const promise = new Promise((yes, no) => {resolve=yes; reject=no;}); return {promise, resolve, reject};};
    state.config = {apiBaseUrl:''};
    state.currentProjectId = 'p';
    state.projects = [{id:'p', name:'p'}];
    state.activeTab = 'snaps';
    state._detailCache = new Map();
    state.overview = {history:{project_id:'p',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}};
    let responses = new Map();
    const requested = [];
    fetchJson = url => {requested.push(url); return responses.get(url).promise;};
    buildDetailHtml = (type, payload) => payload.name;

    const first = deferred(), next = deferred();
    responses.set('/api/v1/snaps/p__snap-001', first);
    responses.set('/api/v1/snaps/p__snap-002', next);
    routes.length = 0;
    const firstRequest = openDetail('snap','p__snap-001');
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'true');
    assert.ok(el.drawerContent.innerHTML.includes('view-loading-spinner'));
    assert.equal(state.selectedDetail.remoteId, 'p__snap-001');
    assert.equal(el.drawer.classList.contains('open'), true);
    assert.equal(el.drawer.inert, false);
    assert.equal(document.activeElement, el.drawerClose);
    assert.equal(routes.join(), 'push');
    await Promise.resolve();
    const nextRequest = openDetail('snap','p__snap-002', {mode:'replace'});
    await Promise.resolve();
    next.resolve({id:'snap-002', name:'newest detail'});
    await nextRequest;
    first.resolve({id:'snap-001', name:'stale detail'});
    await firstRequest;
    assert.equal(el.drawerContent.innerHTML, 'newest detail');
    assert.equal(state.selectedDetail.remoteId, 'p__snap-002');
    assert.equal(state._sheetStack.length, 1);
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'false');
    assert.ok(!state._detailCache.has('snap:p__snap-001'));
    assert.equal(routes.join(), 'push,replace');

    const stale = deferred(), pending = deferred();
    responses.set('/api/v1/snaps/p__snap-003', stale);
    responses.set('/api/v1/snaps/p__snap-004', pending);
    const staleRequest = openDetail('snap','p__snap-003', {mode:'replace'});
    await Promise.resolve();
    const pendingRequest = openDetail('snap','p__snap-004', {mode:'replace'});
    await Promise.resolve();
    stale.resolve({name:'old response finishes first'});
    await staleRequest;
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'true');
    assert.ok(el.drawerContent.innerHTML.includes('loading'));
    pending.resolve({id:'snap-004', name:'latest finished'});
    await pendingRequest;
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'false');

    responses.set('/api/v1/snaps/p__snap-005', {promise:Promise.reject(new Error('offline'))});
    await assert.rejects(() => openDetail('snap','p__snap-005', {mode:'replace'}), /offline/);
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'false');
    assert.ok(el.drawerContent.innerHTML.includes('data-retry-detail="sheet"'));

    routes.length = 0;
    window.history.state = {inthub:'sheet'};
    closeDrawer();
    assert.equal(routes.join(), 'back');
    assert.equal(el.drawer.inert, true);
    assert.equal(el.drawer.classList.contains('open'), false);
    assert.equal(state.selectedDetail, null);

    responses.set('/api/v1/intents/p__intent-001', {promise:Promise.resolve({id:'intent-001', name:'parent intent'})});
    responses.set('/api/v1/snaps/p__snap-007', {promise:Promise.resolve({id:'snap-007', name:'child snap'})});
    routes.length = 0;
    await openDetail('intent','p__intent-001', {history:'replace'});
    assert.equal(routes.join(), 'replace');
    await openDetail('snap','p__snap-007', {mode:'push'});
    assert.equal(state._sheetStack.length, 2);
    assert.equal(el.drawerBack.classList.contains('is-hidden'), false);
    assert.equal(el.drawerContent.innerHTML, 'child snap');
    const fetchesBeforeBack = requested.length;
    await sheetBack();
    assert.equal(state._sheetStack.length, 1);
    assert.equal(el.drawerContent.innerHTML, 'parent intent');
    assert.equal(el.drawerBack.classList.contains('is-hidden'), true);
    assert.equal(requested.length, fetchesBeforeBack);
    routes.length = 0;
    window.history.state = {inthub:'sheet'};
    closeDrawer();
    assert.equal(routes.join(), 'replace');

    const drawerPending = deferred();
    responses.set('/api/v1/snaps/p__snap-006', drawerPending);
    const drawerRequest = openDetail('snap','p__snap-006');
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'true');
    assert.equal(el.drawer.getAttribute('aria-modal'), 'true');
    closeDrawer({history:'none'});
    drawerPending.resolve({name:'closed sheet must stay empty'});
    await drawerRequest;
    assert.equal(el.drawer.inert, true);
    assert.equal(el.drawerContent.getAttribute('aria-busy'), 'false');
    assert.equal(el.drawerContent.innerHTML, '');
    assert.equal(state._drawerPayload, null);

    let crossProject = null;
    loadProject = (id, options) => {crossProject = {id, options}; return Promise.resolve();};
    state.projects = [{id:'p', name:'p'}, {id:'other', name:'other'}];
    await openDetail('intent','other__intent-001');
    assert.equal(crossProject.id, 'other');
    assert.deepEqual(crossProject.options.detail, {type:'intent', remoteId:'other__intent-001'});
    loadProject = savedLoadProject;

    const searchPending = deferred();
    responses.set('/api/v1/search?project_id=p&q=goal', searchPending);
    el.searchDialog.open = true;
    const searchRequest = runSearch('goal');
    assert.equal(state._searchBusy, true);
    await runSearch('');
    searchPending.resolve({matches:[{object_type:'intent', remote_id:'p__intent-009', id:'intent-009', what:'late search result'}]});
    await searchRequest;
    assert.ok(!el.searchResults.innerHTML.includes('late search result'));
    assert.equal(state._searchResults, null);
    responses.set('/api/v1/search?project_id=p&q=pay', {promise:Promise.resolve({matches:[
      {object_type:'decision', remote_id:'p__decision-001', id:'decision-001', status:'active', what:'Pay <safely>', why:''},
      {object_type:'intent', remote_id:'p__intent-002', id:'intent-002', status:'active', what:'Add pay button', why:''},
    ]})});
    await runSearch('pay');
    const searchMarkup = el.searchResults.innerHTML;
    assert.ok(searchMarkup.indexOf('intent-002') < searchMarkup.indexOf('decision-001'));
    assert.ok(searchMarkup.includes('<mark>Pay</mark> &lt;safely&gt;'));
    assert.ok(searchMarkup.includes('role="option"'));
    responses.set('/api/v1/search?project_id=p&q=goal', {promise:Promise.reject(new Error('offline'))});
    await runSearch('goal');
    assert.equal(state._searchBusy, false);
    assert.ok(el.searchResults.innerHTML.includes('data-retry-search'));
    el.searchDialog.open = false;

    state.activeTab = 'overview';
    state._loadedProjectId = 'p';
    state.overview = {project:{id:'p'}, history:{project_id:'p',revision:'a'.repeat(64),last_synced_at:'2026-10-04T00:00:00Z'}};
    state.handoff = {intents:[]};
    renderProjectSelector = () => {};
    renderView = () => {el.detailContent.innerHTML = state.overview.project.id;};
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
    assert.ok(el.detailContent.innerHTML.includes('page-skeleton'));
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
    el.detailContent.innerHTML=viewLoadingHtml();
    const pendingDetailMarkup=el.detailContent.innerHTML;
    setViewBusy('detail',true);
    localizeWorkspace();
    assert.equal(el.detailContent.innerHTML,pendingDetailMarkup);
    setViewBusy('detail',false);

    responses.set('/api/v1/projects/failing/overview', {promise:Promise.reject(new Error('offline'))});
    responses.set('/api/v1/projects/failing/handoff', {promise:Promise.resolve({intents:[]})});
    await assert.rejects(() => loadProject('failing'), /offline/);
    assert.equal(state.currentProjectId, 'p2');
    assert.equal(state.overview.project.id, 'p2');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');

    state.projects = [{id:'empty', name:'empty'}];
    responses.set('/api/v1/projects/empty/overview', {promise:Promise.resolve({project:{id:'empty',name:'empty'},history:{revision:null}})});
    responses.set('/api/v1/projects/empty/handoff', {promise:Promise.resolve({intents:[]})});
    await loadProject('empty');
    assert.equal(el.detailPane.getAttribute('aria-busy'), 'false');
    assert.equal(el.shell.classList.contains('is-empty'), true);
    assert.ok(el.detailContent.innerHTML.includes('itt push'));

    fetchJson=savedFetch; buildDetailHtml=savedBuild; renderView=savedView; renderProjectSelector=savedSelector;
  })()`, context);
  console.log('Latest-action ownership, sheet back stack and history, closed-sheet cancellation, cross-project links, search recovery and project rollback tests passed.');
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
