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
  body: {querySelectorAll() {return [];}}, documentElement: {style: {setProperty() {}}, dataset: {}},
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
  for (const match of source.matchAll(/\btHtml\("((?:[^"\\]|\\.)*)"/g)) {
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
  const deleteAccountButton = document.getElementById('delete-account-btn');
  setButtonBusy(deleteAccountButton, true, 'Opening account management…', 'Delete account');
  assert.equal(deleteAccountButton.disabled, true);
  assert.equal(deleteAccountButton.getAttribute('aria-busy'), 'true');
  assert.equal(deleteAccountButton.textContent, '正在打开账号管理…');
  setButtonBusy(deleteAccountButton, false, 'Opening account management…', 'Delete account');
  assert.equal(t('About IntHub'), '关于 IntHub');
  assert.equal(relativeDate(new Date(Date.now() + 90000).toISOString()), '刚刚');
  assert.equal(t('Synced {time}', {time: relativeDate(new Date().toISOString())}), '刚刚同步');
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
  window.IntHubI18n.setLanguage('en');
  renderIntentsTab();
  assert.ok(el.detailContent.innerHTML.includes('Active objectives'));
  assert.ok(el.detailContent.innerHTML.includes('1 snap<'));
  assert.equal(state.searchQuery, 'unsent user query');
  assert.equal(plural(1, '{count} blocked objective', '{count} blocked objectives'), '1 blocked objective');
  assert.equal(plural(2, '{count} blocked objective', '{count} blocked objectives'), '2 blocked objectives');
  const labelled = document.getElementById('labelled-button');
  const label = document.getElementById('labelled-button-label');
  labelled.querySelector = (selector) => selector === ':scope > .button-label' ? label : null;
  setButtonBusy(labelled, true, 'Creating team…', 'Create team');
  assert.equal(label.textContent, 'Creating team…', 'only the label changes, so the icon stays');
  assert.equal(labelled.textContent, '');
  setButtonBusy(labelled, false, 'Creating team…', 'Create team');
  assert.equal(label.textContent, 'Create team');
  assert.ok(iconLabel('plus', 'A <b>').startsWith('<svg') && iconLabel('plus', 'A <b>').endsWith('<span class="button-label">A &lt;b&gt;</span>'));
  const busyButton = document.getElementById('busy-button');
  setButtonBusy(busyButton, true, 'Creating team…', 'Create team');
  assert.equal(busyButton.disabled, true);
  assert.equal(busyButton.classList.contains('action-busy'), true);
  assert.equal(busyButton.textContent, 'Creating team…');
  window.IntHubI18n.setLanguage('zh-CN');
  setButtonBusy(busyButton, false, 'Creating team…', 'Create team');
  assert.equal(busyButton.disabled, false);
  assert.equal(busyButton.textContent, '创建团队');
  assert.ok(statusBadge('active', 'decision').includes('有效'));
  assert.ok(statusBadge('active').includes('进行中'));
  assert.equal(continuationHealth([]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Next: work.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Boundary: UI only. Next: review. Blocker: none.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: none.'}}]).ready, true);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: waiting for access.'}}]).ready, false);
  assert.equal(continuationHealth([{latest_snap: {what: 'Verified: done. Boundary: UI only. Next: review. Blocker: waiting for access.'}}]).label, '1 个目标被阻塞');

  const recordedSnap = {id:'snap-009', what:'Made publication atomic', why:'Consumers must not see partial releases. Next: prose that must be ignored.', created_at:'2026-10-05T00:00:00Z',
    checkpoint: {verified:' Release suite passes ', boundary:'Publisher <only>', next:'Switch staging', blocker:'none', constraints:'Keep rollback'}};
  const recorded = parseCheckpoint(recordedSnap);
  assert.equal(recorded.verified, 'Release suite passes');
  assert.equal(recorded.next, 'Switch staging');
  assert.equal(recorded.constraints, 'Keep rollback');
  assert.equal(recorded.context, recordedSnap.why);
  assert.equal(conciseSnapTitle(recordedSnap), 'Made publication atomic');
  assert.equal(conciseSnapTitle({what: 'Verified: legacy title. Next: step.'}), 'legacy title');
  const partial = parseCheckpoint({what:'Shipped receipts', why:'Boundary: prose boundary. Blocker: prose blocker.', checkpoint:{next:'Port refunds'}});
  assert.deepEqual([partial.verified, partial.boundary, partial.next, partial.blocker], ['Shipped receipts', '', 'Port refunds', '']);
  for (const checkpoint of [null, [], 'Next: x', {}, {next: '  '}, {next: 7}]) {
    assert.equal(parseCheckpoint({what:'Verified: legacy. Next: legacy step.', checkpoint}).next, 'legacy step');
  }
  const cells = {verified:'v', boundary:'b', next:'n', blocker:'none'};
  assert.equal(continuationHealth([{latest_snap: {what:'w', checkpoint: cells}}]).ready, true);
  assert.equal(continuationHealth([{latest_snap: {what:'w', checkpoint: {...cells, blocker:'waiting for access'}}}]).label, '1 个目标被阻塞');
  assert.equal(continuationHealth([{latest_snap: {what:'Verified: prose.', why:'', checkpoint: {boundary:'b', next:'n', blocker:'none'}}}]).label, '1 个检查点待补充');
  assert.equal(continuationHealth([{latest_snap: {what:'Verified: done. Boundary: UI only. Next: review. Blocker: none.', checkpoint: {}}}]).ready, true);
  const recordedDetail = buildSnapDetailHtml({project_id: 'p', snap: recordedSnap, intent: {id:'intent-001', what:'Ship', status:'active'}});
  const cellValue = (html, key) => html.split('checkpoint-' + key)[1].split('<p class="checkpoint-value">')[1].split('</p>')[0];
  assert.equal(cellValue(recordedDetail, 'next'), 'Switch staging');
  assert.equal(cellValue(recordedDetail, 'boundary'), 'Publisher &lt;only&gt;');
  assert.equal(cellValue(recordedDetail, 'blocker'), 'none');
  assert.ok(!recordedDetail.includes('Publisher <only>'));
  assert.ok(recordedDetail.includes('Keep rollback'));
  assert.ok(recordedDetail.includes('detail-title-snap" tabindex="-1">Made publication atomic</h2>'));
  assert.ok(recordedDetail.includes(formatText(recordedSnap.why)));

  state.overview = {
    project: {id:'p', name:'Checkout <beta>'},
    history: {project_id:'p', revision:'b'.repeat(64), last_synced_at:'2026-10-04T00:00:00Z'},
    active_intents: [], other_intents: [], recent_snaps: [], active_decisions: [], deprecated_decisions: [],
  };
  state.handoff = {
    intents: [{id:'intent-002', remote_id:'p__intent-002', project_id:'p', status:'active', what:'Ship <Apple Pay>', why:'Mobile users convert better.',
      latest_snap: {id:'snap-004', what:'Verified: sheet confirms payments. Boundary: web only. Next: run QA. Blocker: waiting for APM access. Constraints: never trust client totals.', why:'', created_at:'2026-10-04T00:00:00Z'}}],
    suspended_intents: [{id:'intent-001', remote_id:'p__intent-001', project_id:'p', status:'suspend', what:'Port receipts', latest_snap: {id:'snap-001', what:'Next: port refund template.'}},
      {id:'intent-003', remote_id:'p__intent-003', project_id:'p', status:'suspend', what:'Refund exports', latest_snap: {id:'snap-005', what:'Mapped refund rows', checkpoint: {next:'export CSV for finance'}}}],
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
  assert.ok(brief.includes('<b>下一步</b> export CSV for finance'));
  assert.ok(brief.includes('Use PaymentIntents only'));
  const markdown = briefMarkdown();
  assert.ok(markdown.startsWith('# Checkout <beta> · 接续简报'));
  assert.ok(markdown.includes('## Ship <Apple Pay> (intent-002)'));
  assert.ok(markdown.includes('- **下一步:** run QA'));
  assert.ok(markdown.includes('- **阻塞项:** waiting for APM access'));
  assert.ok(markdown.includes('- **约束：** never trust client totals'));
  assert.ok(markdown.includes('- Port receipts (intent-001)'));
  assert.ok(markdown.includes('- Use PaymentIntents only (decision-001)'));

  state.projects = [{id:'p', name:"Team's checkout", full_name:"Team's checkout"}];
  state.currentProjectId = 'p';
  state.config = {apiBaseUrl: 'https://inthub.example', authRequired: true};
  el.shell.classList.remove('is-empty');
  renderSetupGuide('unlinked');
  const guide = el.detailContent.innerHTML;
  assert.ok(guide.includes('data-copy="' + INSTALL_COMMAND.replace(/&/g, '&amp;') + '"'));
  assert.ok(guide.includes('itt init'));
  assert.ok(guide.includes('在浏览器里批准') && !guide.includes('data-create-token'));
  assert.ok(guide.includes('data-copy="itt auth login --api-base-url &#39;https://inthub.example&#39;"'));
  assert.ok(guide.includes("--project &#39;Team&#39;\\\\&#39;&#39;s checkout&#39;"));
  assert.ok(guide.includes('itt push'));
  assert.equal(el.shell.classList.contains('is-empty'), true);
  // The Skill comes right after the CLI, for two agents only: --all would create about 50 agent folders in the home directory.
  assert.ok(guide.includes('npx skills add dozybot001/Intent -g -a claude-code -a codex'));
  assert.ok(!guide.includes('--all'));
  assert.ok(guide.indexOf('curl -fsSL') < guide.indexOf('npx skills add') && guide.indexOf('npx skills add') < guide.indexOf('itt init'));
  assert.ok(guide.includes('--host codex / claude-code'));
  assert.ok(guide.includes('<p class="setup-resume">'));
  // Any endpoint but the CLI default needs its URL at login and the remote before the push.
  assert.ok(guide.includes('data-copy="itt remote add origin &#39;https://inthub.example&#39; --project &#39;Team&#39;\\\\&#39;&#39;s checkout&#39;\\nitt push"'));
  assert.ok(!guide.includes('setup-step-note'));
  state.config = {apiBaseUrl: 'https://inthub.tenon.asia/', authRequired: true};
  renderSetupGuide('unlinked');
  const hostedGuide = el.detailContent.innerHTML;
  assert.ok(hostedGuide.includes('<pre class="command-snippet">itt auth login</pre>'));
  assert.ok(!hostedGuide.includes('--api-base-url'));
  assert.ok(hostedGuide.includes('<pre class="command-snippet">itt push</pre>'));
  assert.ok(hostedGuide.includes('<p class="setup-step-note">可选：如需使用其他项目名，请先关联。</p><div class="snippet"><pre class="command-snippet">itt remote add origin'));
  // An existing hosted project still links first: its directory need not carry the project's name.
  renderSetupGuide('unsynced');
  assert.ok(el.detailContent.innerHTML.includes('--project &#39;Team&#39;\\\\&#39;&#39;s checkout&#39;\\nitt push"'));
  // IntHub Local has no login and always needs the remote.
  state.config = {apiBaseUrl: 'http://127.0.0.1:7317', authRequired: false};
  renderSetupGuide('unlinked');
  const localGuide = el.detailContent.innerHTML;
  assert.ok(!localGuide.includes('itt auth login') && !localGuide.includes('setup-step-note'));
  assert.ok(localGuide.includes('data-copy="itt remote add origin &#39;http://127.0.0.1:7317&#39; --project &#39;Team&#39;\\\\&#39;&#39;s checkout&#39;\\nitt push"'));
  // The copy button is the pre's sibling inside the wrapper the stylesheet positions it against.
  assert.match(commandSnippet(['itt init', 'itt push']), /^<div class="snippet"><pre class="command-snippet">itt init\\nitt push<\\/pre><button class="icon-button copy-button" type="button" data-copy="itt init\\nitt push" aria-label="复制命令">/);
  // A hyphenated word is one unbreakable block on screen; the copied command stays plain text.
  const flagged = commandSnippet(['itt intent relate ID --depends-on OTHER', 'itt auth login --api-base-url &#39;x&#39;'.replace(/&#39;/g, "'")]);
  assert.ok(flagged.includes('itt intent relate ID <span class="command-word">--depends-on</span> OTHER\\nitt auth login <span class="command-word">--api-base-url</span> &#39;x&#39;</pre>'));
  assert.ok(flagged.includes('data-copy="itt intent relate ID --depends-on OTHER\\nitt auth login --api-base-url &#39;x&#39;"'));
  state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};

  // Timeline filter choices come from the Intents (every Intent with Snaps), most recently active first.
  const filterOptions = timelineIntentOptions([
    {id:'intent-001', project_id:'p', what:'User goal one', snap_ids:['snap-001', 'snap-004'], latest_snap_id:'snap-004'},
    {id:'intent-002', project_id:'p', what:'User goal two', snap_ids:['snap-009'], latest_snap_id:'snap-009'},
    {id:'intent-003', project_id:'p', what:'No snaps yet', snap_ids:[]},
  ]);
  assert.deepEqual(filterOptions.map(option => option.key), ['intent-002', 'intent-001']);
  assert.equal(filterOptions[1].count, 2);
  assert.equal(filterOptions[0].label, 'User goal two');
  assert.equal(snapPageUrl('p'), '/api/v1/projects/p/snaps?offset=0&limit=50');
  assert.equal(snapPageUrl('team space', {offset: 50, intentId: 'intent-002'}), '/api/v1/projects/team%20space/snaps?offset=50&limit=50&intent_id=intent-002');
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
    {id:'project-one', name:'draft', full_name:'项目 <draft> & "review" ' + 'very-long-name-'.repeat(20)},
    {id:'project-two', name:'Resume', full_name:'acme/Resume'},
  ];
  state.currentProjectId = 'project-one';
  state.config.defaultProjectId = 'project-one';
  renderProjectSelector();
  assert.equal(el.projectPickerLabel.textContent, state.projects[0].full_name);
  const projectOptions = el.projectPickerDropdown.innerHTML;
  assert.ok(projectOptions.includes('&lt;draft&gt; &amp; &quot;review&quot;'));
  assert.ok(!projectOptions.includes('<draft>'));
  assert.equal((projectOptions.match(/aria-selected="true"/g) || []).length, 1);
  assert.equal((projectOptions.match(/role="option"/g) || []).length, 2);
  assert.ok(projectOptions.includes('共享语义历史'));
  assert.ok(projectOptions.includes('acme/Resume'), 'a team project shows its full name');
  delete state.config.defaultProjectId;
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
    const preferencesTrigger = document.getElementById('preferences-menu-trigger');
    const preferencesPanel = document.getElementById('preferences-menu');
    const authPreferencesTrigger = document.getElementById('auth-preferences-menu-trigger');
    const authPreferencesPanel = document.getElementById('auth-preferences-menu');
    const resourcesTrigger = document.getElementById('resources-menu-trigger');
    const resourcesPanel = document.getElementById('resources-menu');
    const skillLink = document.getElementById('resource-skill-link');
    const repositoryLink = document.getElementById('resource-repository-link');
    const languageChinese = document.getElementById('language-chinese');
    const languageEnglish = document.getElementById('language-english');
    const aboutButton = document.getElementById('menu-about-button');
    languageChinese.dataset.languageSelect = 'zh-CN';
    languageEnglish.dataset.languageSelect = 'en';
    preferencesTrigger.setAttribute('aria-controls','preferences-menu');
    authPreferencesTrigger.setAttribute('aria-controls','auth-preferences-menu');
    resourcesTrigger.setAttribute('aria-controls','resources-menu');
    resourcesPanel.querySelectorAll = () => [skillLink, repositoryLink];
    resourcesPanel.contains = target => target === resourcesPanel || target === skillLink || target === repositoryLink;
    preferencesPanel.querySelectorAll = () => [languageChinese, languageEnglish, aboutButton];
    preferencesPanel.contains = target => target === preferencesPanel || target === languageChinese || target === languageEnglish || target === aboutButton;
    authPreferencesPanel.querySelectorAll = () => [languageEnglish];
    document.querySelectorAll = selector => selector === '[data-preferences-trigger]' ? [preferencesTrigger, authPreferencesTrigger] : selector === '[data-resources-trigger]' ? [resourcesTrigger] : selector === '[data-language-select]' ? [languageChinese, languageEnglish] : selector === '[data-about-open]' ? [aboutButton] : originalQueryAll(selector);
    bindEvents();
    const dispatch = (type, target, key, extra={}) => {
      let stopped=false;
      const event={target,key,preventDefault(){},stopImmediatePropagation(){stopped=true;},...extra};
      for(const listener of document.events.get(type) || []) {listener(event);if(stopped)break;}
    };
    // The focus ring follows the input: a shortcut or a bare modifier moves no focus.
    dispatch('pointerdown', document.body);
    assert.equal(document.documentElement.dataset.input, 'pointer');
    dispatch('keydown', document.body, 'Meta', {metaKey: true});
    dispatch('keydown', document.body, '4', {metaKey: true, shiftKey: true});
    assert.equal(document.documentElement.dataset.input, 'pointer');
    dispatch('keydown', document.body, 'Tab');
    assert.equal(document.documentElement.dataset.input, 'keyboard');
    toggleHeaderMenu(preferencesTrigger);
    assert.equal(preferencesPanel.classList.contains('is-open'),true);
    assert.equal(preferencesPanel.inert,false);
    toggleHeaderMenu(el.accountMenuTrigger);
    assert.equal(preferencesPanel.classList.contains('is-open'),false);
    assert.equal(preferencesPanel.inert,true);
    assert.equal(el.accountActions.classList.contains('is-open'),true);
    toggleHeaderMenu(authPreferencesTrigger);
    assert.equal(el.accountActions.classList.contains('is-open'),false);
    assert.equal(authPreferencesPanel.classList.contains('is-open'),true);
    toggleProjectPicker(true);
    assert.equal(authPreferencesPanel.classList.contains('is-open'),false);
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
    toggleHeaderMenu(preferencesTrigger);
    assert.equal(resourcesPanel.inert,true);
    assert.equal(preferencesPanel.inert,false);
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
    dispatch('keydown',preferencesTrigger,'ArrowDown');
    assert.equal(preferencesPanel.classList.contains('is-open'),true);
    assert.equal(document.activeElement,languageChinese);
    assert.equal(el.projectPickerDropdown.classList.contains('is-open'),false);
    dispatch('keydown',languageChinese,'ArrowDown');
    assert.equal(document.activeElement,languageEnglish);
    dispatch('keydown',languageEnglish,'Escape');
    assert.equal(preferencesPanel.classList.contains('is-open'),false);
    assert.equal(document.activeElement,preferencesTrigger);
    toggleHeaderMenu(preferencesTrigger,{focus:'first'});
    dispatch('keydown',languageChinese,'Tab',{shiftKey:true});
    assert.equal(preferencesPanel.classList.contains('is-open'),true);
    document.activeElement=preferencesTrigger;
    dispatch('focusin',preferencesTrigger);
    assert.equal(preferencesPanel.classList.contains('is-open'),true);
    dispatch('keydown',preferencesTrigger,'Tab',{shiftKey:true});
    assert.equal(preferencesPanel.inert,false);
    document.activeElement=el.searchTrigger;
    dispatch('focusin',el.searchTrigger);
    assert.equal(preferencesPanel.classList.contains('is-open'),false);
    toggleHeaderMenu(preferencesTrigger);
    dispatch('keydown',document.getElementById('outside-menu'),'Escape');
    assert.equal(preferencesPanel.classList.contains('is-open'),false);
    assert.equal(document.activeElement,preferencesTrigger);
    toggleHeaderMenu(preferencesTrigger);
    document.activeElement=aboutButton;
    dispatch('keydown',aboutButton,'Tab');
    assert.equal(preferencesPanel.inert,false);
    document.activeElement=el.accountMenuTrigger;
    dispatch('focusin',el.accountMenuTrigger);
    assert.equal(preferencesPanel.inert,true);
    toggleHeaderMenu(preferencesTrigger);
    dispatch('click',document.getElementById('outside-menu'));
    assert.equal(preferencesPanel.classList.contains('is-open'),false);
    toggleHeaderMenu(preferencesTrigger);
    aboutButton.events.get('click')[0]();
    assert.equal(el.aboutDialog.open,true);
    assert.equal(preferencesPanel.inert,true);
    el.aboutDialog.close();
    assert.equal(document.activeElement,preferencesTrigger);

    window.IntHubI18n.setLanguage('en');
    assert.equal(languageEnglish.getAttribute('aria-pressed'),'true');
    assert.equal(languageChinese.getAttribute('aria-pressed'),'false');
    window.IntHubI18n.setLanguage('zh-CN');
    assert.equal(languageChinese.classList.contains('is-selected'),true);

    state.config={authRequired:true};
    state.account={display_name:'Actual signed-in user'};
    hideAuthGate();
    assert.equal(el.accountLabel.textContent,'Actual signed-in user');
    el.drawer.classList.add('open');
    el.detailContent.innerHTML = 'private project brief';
    el.searchResults.innerHTML = 'private search result';
    showAuthGate();
    assert.equal(el.detailContent.innerHTML, '');
    assert.equal(el.searchResults.innerHTML, '');
    assert.equal(el.accountLabel.textContent, '');
    assert.equal(el.shell.inert,true);
    assert.equal(el.drawer.inert,true);
    assert.equal(el.drawer.classList.contains('open'),false);
    const gatedTab=state.activeTab;
    dispatch('keydown',document.getElementById('outside-menu'),'k',{ctrlKey:true});
    assert.equal(state.activeTab,gatedTab);
    assert.notEqual(el.searchDialog.open,true);
    dispatch('keydown',authPreferencesTrigger,'ArrowDown');
    assert.equal(authPreferencesPanel.classList.contains('is-open'),true);
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
    state.projects = [{id:'p', name:'p', full_name:'p'}];
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
    closeDrawer();
    assert.equal(routes.join(), 'back');
    // A sheet entry restored by Forward is still one this page pushed.
    window.history.state = {inthub:'sheet', sheetPushed:true};
    responses.set('/api/v1/snaps/p__snap-008', {promise:Promise.resolve({id:'snap-008', name:'forward'})});
    await openDetail('snap','p__snap-008', {history:'none'});
    routes.length = 0;
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
    state.projects = [{id:'p', name:'p', full_name:'p'}, {id:'other', name:'other', full_name:'other'}];
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
    assert.ok(searchMarkup.includes('role="group" aria-labelledby="search-group-intent"'));
    assert.equal(el.searchStatus.innerHTML, '2 个结果');
    assert.equal(el.searchStatus.classList.contains('visually-hidden'), true);
    // Enter right after typing searches the typed text first instead of opening a stale highlight.
    el.searchInput.value = 'button';
    let opened = null;
    const savedActivate = activateSearchOption;
    activateSearchOption = option => {opened = option;};
    responses.set('/api/v1/search?project_id=p&q=button', {promise:Promise.resolve({matches:[]})});
    await submitSearch();
    assert.equal(state._searchResultQuery, 'button');
    assert.equal(opened, null);
    activateSearchOption = savedActivate;
    responses.set('/api/v1/search?project_id=p&q=goal', {promise:Promise.reject(new Error('offline'))});
    await runSearch('goal');
    assert.equal(state._searchBusy, false);
    assert.ok(el.searchStatus.innerHTML.includes('data-retry-search'));
    assert.equal(el.searchResults.innerHTML, '');
    assert.equal(el.searchInput.getAttribute('aria-expanded'), 'false');
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

    state.projects = [{id:'empty', name:'empty', full_name:'empty'}];
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

// Relations, the Flow layout, paged timeline and truncated search.
// INTHUB_RELATION_STATES (set by the pytest runner) carries relations.state() from the CLI for parity.
context.relationParity = JSON.parse(process.env.INTHUB_RELATION_STATES || '[]');
async function flowAndPagingCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    let focusedOn001;
    window.IntHubI18n.setLanguage('zh-CN');

    // Derived relation states, subject (rows) against target (columns): active, suspend, done, cancelled.
    const statuses = ['active', 'suspend', 'done', 'cancelled'];
    const open = ['in_progress', 'in_progress', 'orphaned', 'orphaned'];
    const expected = {
      part_of: [open, open, Array(4).fill('done'), Array(4).fill('dropped')],
      derived_from: Array(4).fill(Array(4).fill(null)),
      succeeds: Array(4).fill(['pending', 'pending', 'handed_over', 'handed_over']),
      depends_on: Array(4).fill(['blocked', 'blocked', 'satisfied', 'broken']),
      conflicts_with: [['unresolved', 'unresolved', 'resolved', 'resolved'], ['unresolved', 'unresolved', 'resolved', 'resolved'], Array(4).fill('resolved'), Array(4).fill('resolved')],
    };
    for (const [kind, table] of Object.entries(expected)) {
      statuses.forEach((subject, row) => statuses.forEach((target, column) => {
        assert.equal(relationState(kind, {status: subject}, {status: target}), table[row][column], kind + ' ' + subject + ' → ' + target);
      }));
    }
    for (const [kind, subject, target, want] of relationParity) {
      assert.equal(relationState(kind, {status: subject}, {status: target}), want, 'parity ' + kind + ' ' + subject + ' → ' + target);
    }
    assert.deepEqual([...ATTENTION_STATES].sort(), ['blocked', 'broken', 'orphaned', 'pending', 'unresolved']);

    const at = minute => new Date(Date.UTC(2026, 9, 30, 8, minute)).toISOString();
    const rel = (type, intent, extra = {}) => ({type, intent, created_at: at(50), ...extra});
    const flowIntents = [
      {id:'intent-001', what:'Checkout revamp', status:'active', created_at: at(1), snap_ids:['snap-001', 'snap-002']},
      {id:'intent-002', what:'Apple Pay', status:'done', created_at: at(2), relations:[rel('part_of', 'intent-001')]},
      {id:'intent-003', what:'Google Pay', status:'active', created_at: at(3), relations:[rel('part_of', 'intent-001')]},
      {id:'intent-004', what:'PaymentIntents migration', status:'active', created_at: at(4), relations:[rel('derived_from', 'intent-001')]},
      {id:'intent-005', what:'Receipts v1', status:'cancelled', created_at: at(5)},
      {id:'intent-006', what:'Receipts v2', status:'active', created_at: at(6), relations:[rel('succeeds', 'intent-005')]},
      {id:'intent-007', what:'Launch to 10%', status:'active', created_at: at(7), relations:[rel('depends_on', 'intent-003'), rel('conflicts_with', 'intent-004', {removed_at: at(51)})]},
      {id:'intent-008', what:'Server <totals>', status:'suspend', created_at: at(8), relations:[rel('conflicts_with', 'intent-006')]},
      {id:'intent-009', what:'Unrelated cleanup', status:'done', created_at: at(9)},
    ].map(intent => ({snap_ids: [], decision_ids: [], ...intent, project_id: 'p', remote_id: 'p__' + intent.id}));
    const flowDecisions = [
      {id:'decision-001', what:'Project rule', status:'active', created_at: at(2), project_id:'p', remote_id:'p__decision-001'},
      {id:'decision-002', what:'Old payment rule', status:'deprecated', created_at: at(3), source_intent_id:'intent-001', project_id:'p', remote_id:'p__decision-002'},
      {id:'decision-003', what:'Lost source', status:'active', created_at: at(4), source_intent_id:'intent-404', project_id:'p', remote_id:'p__decision-003'},
    ];

    // Both directions, outgoing first; withdrawn relations are ignored.
    const view = relationView(flowIntents, 'intent-007');
    assert.deepEqual(view.map(row => [row.type, row.direction, row.intent.id, row.state]), [['depends_on', 'out', 'intent-003', 'blocked']]);
    assert.deepEqual(relationView(flowIntents, 'intent-001').map(row => row.type + ':' + row.direction + ':' + row.intent.id),
      ['part_of:in:intent-002', 'part_of:in:intent-003', 'derived_from:in:intent-004']);
    assert.equal(relationLabel('part_of', 'out'), '属于');
    assert.equal(relationLabel('part_of', 'in'), '组成部分');
    assert.equal(relationLabel('succeeds', 'in'), '被继承');
    assert.equal(relationLabel('depends_on', 'in'), '被依赖');
    assert.ok(relationBadge('broken').includes('rel-danger') && relationBadge('broken').includes('依赖已失效'));
    assert.ok(relationBadge('blocked').includes('<span class="status-dot" aria-hidden="true"></span>被阻塞</span>'));

    const layout = flowLayout(flowIntents, flowDecisions);
    const place = id => layout.nodes.find(node => node.id === id);
    const grid = Object.fromEntries(layout.nodes.map(node => [node.id, [node.col, node.lane]]));
    assert.deepEqual(grid, {
      'intent-001': [0, 0], 'intent-002': [1, 1], 'intent-003': [1, 2], 'intent-004': [1, 3],
      'intent-005': [1, 4], 'intent-006': [2, 4], 'intent-007': [2, 5], 'intent-008': [2, 6],
    });
    assert.deepEqual(layout.standalone.map(intent => intent.id), ['intent-009']);
    assert.equal(layout.hasRelations, true);
    // Left to right by creation time; parts below their parent; the successor right of its predecessor on its lane.
    const created = [...layout.nodes].sort((left, right) => left.intent.created_at.localeCompare(right.intent.created_at));
    created.forEach((node, index) => { if (index) assert.ok(created[index - 1].col <= node.col); });
    for (const part of ['intent-002', 'intent-003', 'intent-004']) assert.ok(place(part).lane > place('intent-001').lane && place(part).x > place('intent-001').x);
    assert.equal(place('intent-006').y, place('intent-005').y);
    assert.equal(place('intent-006').placement, 'continue');
    const kinds = layout.lines.map(line => line.kind + ':' + line.subject + ':' + (line.state || ''));
    assert.deepEqual(kinds.sort(), [
      'branch:intent-002:done', 'branch:intent-003:in_progress', 'branch:intent-004:', 'conflict:intent-008:unresolved',
      'depends:intent-007:blocked', 'flow:intent-006:handed_over', 'rejoin:intent-002:done',
    ]);
    const rejoin = layout.lines.find(line => line.kind === 'rejoin');
    assert.equal(rejoin.points.at(-1)[1], place('intent-001').cy);
    const succession = layout.lines.find(line => line.kind === 'flow');
    assert.deepEqual(succession.points, [[place('intent-005').x + layout.geometry.nodeW, place('intent-005').cy], [place('intent-006').x, place('intent-006').cy]]);
    // Each part leaves its parent's side on its own strand: nearer children leave higher and turn
    // further out, so the strands nest instead of sharing a trunk or crossing.
    const strands = ['intent-002', 'intent-003', 'intent-004'].map(id => layout.lines.find(line => line.kind === 'branch' && line.subject === id));
    for (const strand of strands) {
      assert.equal(strand.points[0][0], place('intent-001').x + layout.geometry.nodeW);
      assert.deepEqual(strand.points.at(-1), [place(strand.subject).x, place(strand.subject).cy]);
    }
    assert.ok(strands[0].points[0][1] < strands[1].points[0][1] && strands[1].points[0][1] < strands[2].points[0][1]);
    assert.ok(strands[0].points[1][0] > strands[1].points[1][0] && strands[1].points[1][0] > strands[2].points[1][0]);
    // Between adjacent columns a line is one S: horizontal tangents, control points half way across the gap.
    for (const strand of strands) {
      assert.equal(strand.curve.segments.length, 1);
      const [segment] = strand.curve.segments;
      assert.deepEqual([segment.c1[1], segment.c2[1]], [strand.points[0][1], strand.points.at(-1)[1]]);
      assert.equal(segment.c1[0] - strand.points[0][0], layout.geometry.gapX / 2);
      assert.equal(strand.points.at(-1)[0] - segment.c2[0], layout.geometry.gapX / 2);
    }
    // A parent's lane runs on exactly as far as its ended part comes back; other lanes stop at their card.
    assert.deepEqual(layout.laneLines.map(line => [line.row, line.x2]), [[place('intent-001').lane, rejoin.points[2][0]]]);
    // Lines meeting one side of a node never share a height.
    const sides = new Map();
    for (const line of layout.lines.filter(line => !['branch', 'rejoin'].includes(line.kind))) {
      const [x, y] = line.points.at(-1);
      const key = Math.round(x) + ':' + Math.round(y);
      assert.ok(!sides.has(key), 'two lines end at ' + key);
      sides.set(key, line);
    }
    // Decisions: the sourceless one and the one whose source is gone are chips in the Project band,
    // at the column of their time; a sourced one hangs as a pin under its card, whose row grows for it.
    assert.deepEqual(layout.band.chips.map(chip => [chip.decision.id, chip.col, chip.row]), [['decision-001', 1, 0], ['decision-003', 1, 1]]);
    for (const chip of layout.band.chips) assert.ok(chip.y + 22 < place('intent-001').y);
    assert.deepEqual(place('intent-001').decisions.map(decision => decision.id), ['decision-002']);
    assert.ok(place('intent-001').box.y2 > place('intent-001').y + layout.geometry.nodeH);
    assert.ok(place('intent-002').y >= place('intent-001').box.y2 + layout.geometry.gapY);
    // Every route stays in the gaps, and so does every curve drawn from it, pins included.
    for (const line of layout.lines) {
      for (const [x, y] of flowSamples(line.curve)) for (const node of layout.nodes) {
        assert.ok(!(x > node.box.x1 + 0.5 && x < node.box.x2 - 0.5 && y > node.box.y1 + 0.5 && y < node.box.y2 - 0.5), line.kind + ' ' + line.subject + ' clips ' + node.id);
      }
    }
    // The quiet time axis labels a column only when the day changes; the view opens on the latest open card.
    assert.deepEqual(layout.axis.map(tick => tick.col), [0]);
    assert.equal(flowTarget(layout).id, 'intent-008');
    const days = flowLayout([
      {id:'intent-041', status:'active', created_at:'2026-10-01T10:00:00Z'},
      {id:'intent-042', status:'active', created_at:'2026-10-01T10:02:00Z', relations:[rel('part_of', 'intent-041')]},
      {id:'intent-043', status:'active', created_at:'2026-10-03T10:00:00Z', relations:[rel('succeeds', 'intent-042')]},
      {id:'intent-044', status:'done', created_at:'2026-10-03T10:02:00Z', relations:[rel('succeeds', 'intent-043')]},
    ]);
    assert.deepEqual(days.axis.map(tick => tick.col), [0, 2]);
    assert.equal(flowTarget(days).id, 'intent-043');
    // A frame smaller than the graph opens with the target fully in view, over as much card area as it can.
    const opening = flowViewport(layout, 360, 600);
    const latest = place('intent-008');
    assert.ok(opening.left <= latest.box.x1 && opening.left + 360 >= latest.box.x2 && opening.top <= latest.box.y1 && opening.top + 600 >= latest.box.y2);
    assert.ok(opening.left >= 0 && opening.top >= 0 && opening.left <= layout.width - 360 && opening.top <= layout.height - 600);
    assert.deepEqual(flowViewport(days, 4000, 4000), {left: 0, top: 0});
    // On a phone the frame hugs the rows of the cards it opens on, keeping the target's direct relations.
    const partsView = flowLayout(flowIntents, flowDecisions, {focus: 'intent-001'});
    const focusSpan = flowVisibleSpan(partsView, 0, 360);
    for (const id of ['intent-002', 'intent-003', 'intent-004']) assert.ok(focusSpan.bottom >= partsView.nodes.find(node => node.id === id).box.y2);
    const span = flowVisibleSpan(layout, opening.left, 360);
    assert.ok(span.top <= latest.box.y1 && span.bottom >= latest.box.y2);
    for (const node of layout.nodes) {
      const across = Math.min(node.box.x2, opening.left + 360) - Math.max(node.box.x1, opening.left);
      if (across >= layout.geometry.nodeW / 2) assert.ok(node.box.y1 >= span.top && node.box.y2 <= span.bottom);
    }
    // A longer route keeps its waypoints; each bend becomes a cubic whose tangents follow the legs.
    const blocked = [{x1: 100, y1: 40, x2: 300, y2: 260}];
    const bendy = flowCurve([[0, 0], [40, 0], [40, 300], [400, 300]], blocked);
    assert.deepEqual(bendy.segments.map(segment => (segment.c1 ? 'C' : 'L')), ['L', 'C', 'L', 'C', 'L']);
    assert.deepEqual([bendy.segments[1].c1[1], bendy.segments[1].c2[0], bendy.segments[3].c1[0], bendy.segments[3].c2[1]], [0, 40, 40, 300]);
    assert.deepEqual(bendy.segments[1].to, [40, 84]);
    // A bend shrinks rather than clip a card standing in its way.
    const squeezed = [...blocked, {x1: 44, y1: 200, x2: 120, y2: 280}];
    for (const [x, y] of flowSamples(flowCurve([[0, 0], [40, 0], [40, 300], [400, 300]], squeezed))) {
      for (const box of squeezed) assert.ok(!(x > box.x1 + 0.5 && x < box.x2 - 0.5 && y > box.y1 + 0.5 && y < box.y2 - 0.5));
    }
    assert.deepEqual(flowCurveEnd(flowCurve([[0, 0], [72, 0], [72, 80], [144, 80]])), {x: 144, y: 80, ux: 1, uy: 0, length: 72});

    // Hidden partners do not make an Intent standalone: intent-006 keeps its place in the flow.
    const hidden = flowLayout(flowIntents, flowDecisions, {hideEnded: true});
    assert.deepEqual(hidden.nodes.map(node => node.id).sort(), ['intent-001', 'intent-003', 'intent-004', 'intent-006', 'intent-007', 'intent-008']);
    assert.equal(hidden.nodes.find(node => node.id === 'intent-006').placement, 'root');
    assert.deepEqual(hidden.standalone, []);
    assert.ok(!hidden.relations.some(link => link.subject === 'intent-002' || link.target === 'intent-005'));
    const node001 = renderFlowSvg(focusedOn001 = flowLayout(flowIntents, flowDecisions, {focus: 'intent-001'}));
    assert.ok(node001.includes('aria-label="intent-001: Checkout revamp. 进行中. 2 个 Snap. 1 条决策. 组成部分 intent-002 (已完成). 组成部分 intent-003 (进行中). 衍生出 intent-004"'));
    const focused = flowLayout(flowIntents, flowDecisions, {focus: 'intent-003'});
    assert.deepEqual(focused.nodes.map(node => node.id).sort(), ['intent-001', 'intent-003', 'intent-007']);
    assert.equal(focused.band, null);
    assert.equal(focused.focus, 'intent-003');
    assert.equal(flowTarget(focused).id, 'intent-003');

    // Convergence and branching of succession: two Intents merge into one, which then splits.
    const merge = flowLayout([
      {id:'intent-011', status:'cancelled', created_at: at(11)},
      {id:'intent-012', status:'cancelled', created_at: at(12)},
      {id:'intent-013', status:'active', created_at: at(13), relations:[rel('succeeds', 'intent-011'), rel('succeeds', 'intent-012')]},
      {id:'intent-014', status:'active', created_at: at(14), relations:[rel('succeeds', 'intent-013')]},
      {id:'intent-015', status:'active', created_at: at(15), relations:[rel('succeeds', 'intent-013')]},
    ]);
    assert.deepEqual(Object.fromEntries(merge.nodes.map(node => [node.id, [node.col, node.lane, node.placement]])), {
      'intent-011': [0, 0, 'root'], 'intent-013': [1, 0, 'continue'], 'intent-014': [2, 0, 'continue'],
      'intent-015': [2, 1, 'branch'], 'intent-012': [0, 2, 'root'],
    });
    const intoMerge = merge.lines.find(line => line.target === 'intent-012');
    assert.equal(intoMerge.points.at(-1)[0], merge.nodes.find(node => node.id === 'intent-013').x);
    assert.equal(merge.lines.filter(line => line.kind === 'flow').length, 4);
    // A cycle across relation families still places every Intent.
    const cycle = flowLayout([
      {id:'intent-021', status:'active', created_at: at(21), relations:[rel('succeeds', 'intent-022')]},
      {id:'intent-022', status:'active', created_at: at(22), relations:[rel('part_of', 'intent-021')]},
    ]);
    assert.equal(cycle.nodes.length, 2);
    assert.deepEqual(flowLayout([{id:'intent-031', status:'active'}]).nodes, []);

    // Property check over seeded random histories that respect the relation rules: every Intent placed once,
    // no two nodes share a cell, parents and predecessors sit to the left, creation order never runs
    // backwards, and no route or rendered curve (sampled 12 times per cubic) enters a card or its pins.
    let seed = 7;
    const random = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
    const relationKinds = ['part_of', 'derived_from', 'succeeds', 'depends_on', 'conflicts_with'];
    const familyOf = kind => (kind === 'part_of' || kind === 'derived_from') ? 'parent' : kind;
    const inside = (box, x, y) => x > box.x1 + 0.5 && x < box.x2 - 0.5 && y > box.y1 + 0.5 && y < box.y2 - 0.5;
    const crosses = (box, [x1, y1], [x2, y2]) => {
      if (y1 === y2) return y1 > box.y1 + 0.5 && y1 < box.y2 - 0.5 && Math.max(x1, x2) > box.x1 + 0.5 && Math.min(x1, x2) < box.x2 - 0.5;
      if (x1 === x2) return x1 > box.x1 + 0.5 && x1 < box.x2 - 0.5 && Math.max(y1, y2) > box.y1 + 0.5 && Math.min(y1, y2) < box.y2 - 0.5;
      return true;
    };
    for (let round = 0; round < 120; round++) {
      const count = 4 + Math.floor(random() * 22);
      const graph = Array.from({length: count}, (_, index) => ({
        id: 'intent-' + String(index + 1).padStart(3, '0'),
        status: ['active', 'active', 'suspend', 'done', 'cancelled'][Math.floor(random() * 5)],
        created_at: at(Math.floor(index * 2 + random() * 2)), relations: [],
      }));
      const graphDecisions = graph.flatMap((intent, index) => Array.from({length: random() < 0.6 ? 0 : 1 + Math.floor(random() * 3)}, (_, number) => ({
        id: 'decision-' + index + '-' + number, status: random() < 0.3 ? 'deprecated' : 'active', created_at: intent.created_at,
        ...(random() < 0.8 ? {source_intent_id: intent.id} : {}),
      })));
      const edges = {parent: new Map(), succeeds: new Map(), depends_on: new Map()};
      const order = new Map();  // parent and succeeds together must stay acyclic for the column rule
      const reaches = (map, from, goal) => { const stack = [from], seen = new Set(); while (stack.length) { const id = stack.pop(); if (id === goal) return true; if (!seen.has(id)) { seen.add(id); stack.push(...(map.get(id) || [])); } } return false; };
      const add = (map, from, to) => map.set(from, [...(map.get(from) || []), to]);
      const pairs = new Set();
      for (let attempt = 0; attempt < count * 2; attempt++) {
        const subject = graph[Math.floor(random() * count)];
        const target = graph[Math.floor(random() * count)];
        const kind = relationKinds[Math.floor(random() * relationKinds.length)];
        const pair = [subject.id, target.id].sort().join();
        if (subject === target || pairs.has(pair)) continue;
        const family = familyOf(kind);
        if (family === 'parent' && subject.relations.some(entry => familyOf(entry.type) === 'parent')) continue;
        if (edges[family] && reaches(edges[family], target.id, subject.id)) continue;
        if ((family === 'parent' || family === 'succeeds') && reaches(order, target.id, subject.id)) continue;
        pairs.add(pair);
        subject.relations.push(rel(kind, target.id));
        if (edges[family]) add(edges[family], subject.id, target.id);
        if (family === 'parent' || family === 'succeeds') add(order, subject.id, target.id);
      }
      for (const options of [{}, {hideEnded: true}, {focus: graph[0].id}]) {
        const result = flowLayout(graph, graphDecisions, options);
        const ids = [...result.nodes.map(node => node.id), ...result.standalone.map(intent => intent.id)];
        assert.equal(new Set(ids).size, ids.length, 'placed once');
        if (!options.hideEnded && !options.focus) assert.equal(ids.length, count, 'every Intent shown');
        const cells = new Set(result.nodes.map(node => node.col + ':' + node.lane));
        assert.equal(cells.size, result.nodes.length, 'one node per cell, round ' + round);
        const cellOf = new Map(result.nodes.map(node => [node.id, node]));
        for (const link of result.relations) {
          if (link.type === 'part_of' || link.type === 'derived_from' || link.type === 'succeeds') {
            assert.ok(cellOf.get(link.subject).col > cellOf.get(link.target).col, link.subject + ' ' + link.type + ' ' + link.target + ' sits right, round ' + round);
          }
        }
        const olderFirst = result.relations.every(link => link.type === 'depends_on' || link.type === 'conflicts_with' || link.subject > link.target);
        if (olderFirst) {
          const byTime = [...result.nodes].sort((left, right) => byCreation(left.intent, right.intent));
          byTime.forEach((node, index) => { if (index) assert.ok(byTime[index - 1].col <= node.col, 'creation order, round ' + round); });
        }
        for (const line of result.lines) {
          const label = line.kind + ' ' + line.subject + '→' + line.target;
          for (let index = 1; index < line.points.length; index++) {
            for (const node of result.nodes) assert.ok(!crosses(node.box, line.points[index - 1], line.points[index]), label + ' route crosses ' + node.id + ', round ' + round);
          }
          for (const [x, y] of flowSamples(line.curve, 12)) {
            for (const node of result.nodes) assert.ok(!inside(node.box, x, y), label + ' curve clips ' + node.id + ', round ' + round);
          }
        }
      }
    }

    const lines = flowLines('Make checkout payments go through PaymentIntents only, everywhere, always', 164, 13, 2);
    assert.equal(lines.length, 2);
    assert.ok(lines[1].endsWith('…'));
    for (const line of lines) assert.ok(flowTextWidth(line, 13) <= 164);
    assert.deepEqual(flowLines('接入 Apple Pay', 164, 13, 2), ['接入 Apple Pay']);
    assert.ok(flowLines('超长的中文目标标题需要在两行之内被截断并且加上省略号才能放进节点里面去', 164, 13, 2)[1].endsWith('…'));

    const svg = renderFlowSvg(layout);
    assert.ok(!/\\sstyle=/.test(svg), 'no inline style attributes under the CSP');
    assert.equal((svg.match(/class="flow-node /g) || []).length, 8);
    assert.ok(svg.includes('role="button" tabindex="0" data-detail-type="intent" data-remote-id="p__intent-003"'));
    assert.ok(svg.includes('aria-label="intent-007: Launch to 10%. 进行中. 0 个 Snap. 依赖 intent-003 (被阻塞)"'));
    assert.ok(svg.includes('Server &lt;totals&gt;') && !svg.includes('Server <totals>'));
    assert.ok(svg.includes('>vs</text>'));
    assert.ok(svg.includes('class="flow-decision flow-pin is-deprecated" role="button" tabindex="0" data-detail-type="decision" data-remote-id="p__decision-002"'));
    assert.ok(svg.includes('class="flow-pin-stem"'));
    assert.ok(svg.includes('>项目</text>'));
    assert.ok(svg.includes('class="flow-decision flow-chip" role="button" tabindex="0" data-detail-type="decision" data-remote-id="p__decision-001"'));
    assert.ok(svg.includes('>Project rule</text>'));
    assert.ok(svg.includes('class="flow-line flow-depends flow-type-depends_on tone-attention"'));
    assert.ok(svg.indexOf('data-remote-id="p__decision-001"') < svg.indexOf('data-remote-id="p__intent-001"'));
    // Curves rather than corners, a status pill sized after drawing, no accent bar, a time axis.
    assert.ok(/class="flow-stroke" d="M[^"]*C/.test(svg));
    assert.ok(svg.includes('<g class="flow-pill" data-fit="25">'));
    assert.ok(!svg.includes('accent') && !svg.includes('flow-card-clip'));
    assert.ok(svg.includes('class="flow-axis-label"'));
    assert.ok(svg.includes('<circle class="flow-terminal"'));

    state.currentProjectId = 'p';
    state.activeTab = 'flow';
    state._flow = null;
    state.overview = {project:{id:'p', name:'p'}, history:{project_id:'p', revision:'a'.repeat(64), last_synced_at: at(30)},
      active_intents: [{id:'intent-041', project_id:'p', remote_id:'p__intent-041', status:'active', what:'Lonely', created_at: at(1)}],
      other_intents: [], active_decisions: [], deprecated_decisions: [], recent_snaps: [], total_snaps: 0};
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('flow-empty'));
    assert.ok(el.detailContent.innerHTML.includes('itt intent relate ID --depends-on OTHER'));
    assert.ok(el.detailContent.innerHTML.includes('itt decision create &quot;Rule&quot; --why &quot;Reason&quot; --from ID'));
    assert.ok(el.detailContent.innerHTML.includes('意图之间还没有关系。'));
    state.overview = {...state.overview, active_intents: flowIntents.filter(intent => intent.status === 'active'),
      other_intents: flowIntents.filter(intent => intent.status !== 'active'),
      active_decisions: flowDecisions.filter(decision => decision.status === 'active'), deprecated_decisions: flowDecisions.filter(decision => decision.status === 'deprecated')};
    renderFlowTab();
    let page = el.detailContent.innerHTML;
    assert.ok(page.includes('class="flow-canvas"') && page.includes('class="flow-legend"'));
    assert.ok(page.includes('data-flow-hide-ended aria-pressed="false"'));
    assert.ok(page.includes('data-flow-focus="intent-003"'));
    assert.ok(page.includes('6 条关系') && page.includes('2 条需要处理'));
    assert.ok(page.includes('class="flow-card status-done" data-detail-type="intent" data-remote-id="p__intent-009"'));
    assert.ok(page.includes('data-help="flow"'));
    state._flow.hideEnded = true;
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('data-flow-hide-ended aria-pressed="true"'));
    assert.ok(!el.detailContent.innerHTML.includes('p__intent-009'));
    state._flow = {hideEnded: false, focus: 'intent-003', standalone: 30};
    renderFlowTab();
    page = el.detailContent.innerHTML;
    assert.ok(page.includes('聚焦于 intent-003'));
    assert.ok(page.includes('class="flow-node status-active is-focus"'));
    assert.ok(!page.includes('flow-standalone'));
    window.IntHubI18n.setLanguage('en');
    renderFlowTab();
    assert.ok(el.detailContent.innerHTML.includes('Focused on intent-003'));
    assert.ok(el.detailContent.innerHTML.includes('Depends on'));
    window.IntHubI18n.setLanguage('zh-CN');
    state._flow = null;

    // Brief: the parent line and attention badges, each paired with text, also in the copied Markdown.
    state.handoff = {
      intents: [flowIntents[2], flowIntents[6]].map(intent => ({...intent, latest_snap: {id:'snap-100', what:'Verified: ok. Boundary: web. Next: ship. Blocker: none.', created_at: at(20)}})),
      suspended_intents: [{...flowIntents[7], latest_snap: null}],
      active_decisions: [],
    };
    renderProjectSummary();
    const brief = el.detailContent.innerHTML;
    assert.ok(brief.includes('class="brief-relations"'));
    assert.ok(brief.includes('<span class="brief-relation-label">属于</span>'));
    assert.ok(brief.includes('data-detail-type="intent" data-remote-id="p__intent-001">Checkout revamp</button>'));
    assert.ok(brief.includes('被阻塞</span>\\n      <span class="brief-relation-label">依赖</span>'));
    // The prerequisite's side says it is blocking someone, not that it is blocked itself.
    assert.ok(brief.includes('阻塞中</span>\\n      <span class="brief-relation-label">被依赖</span>'));
    assert.ok(brief.includes('对立未解决') && brief.includes('对立 intent-006'));
    assert.ok(brief.includes('health-pill is-warning'));
    assert.equal(continuationHealth(state.handoff.intents).label, '1 个目标被阻塞');
    const markdown = briefMarkdown();
    assert.ok(markdown.includes('- **属于:** Checkout revamp (intent-001)'));
    assert.ok(markdown.includes('- **依赖:** Google Pay (intent-003) · 被阻塞'));
    assert.ok(markdown.includes('- Server <totals> (intent-008); 对立 Receipts v2 (intent-006) · 对立未解决'));

    // Intent sheet: both directions with readable labels and states; Decision sheet: its source.
    const intentSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[0], snaps: [], decisions: []});
    assert.ok(intentSheet.includes('<h4 class="relation-group-label">组成部分</h4>'));
    assert.ok(intentSheet.includes('<h4 class="relation-group-label">衍生出</h4>'));
    assert.ok(intentSheet.includes('data-detail-type="intent" data-remote-id="p__intent-002"'));
    // Parts carry their own status already; their relation state only shows when it needs attention.
    assert.ok(!intentSheet.includes('rel-state'));
    const successorSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[5], snaps: [], decisions: []});
    assert.ok(successorSheet.includes('<h4 class="relation-group-label">继承自</h4>'));
    assert.ok(successorSheet.includes('rel-state rel-settled') && successorSheet.includes('已交接'));
    const blockedSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[6], snaps: [], decisions: []});
    assert.ok(blockedSheet.includes('rel-state rel-attention') && blockedSheet.includes('被阻塞'));
    assert.ok(intentSheet.includes('data-flow-focus="intent-001"'));
    assert.ok(intentSheet.includes('源自此意图的决策') && intentSheet.includes('data-remote-id="p__decision-002"'));
    const partSheet = buildIntentDetailHtml({project_id:'p', intent: flowIntents[2], snaps: [], decisions: []});
    assert.ok(partSheet.indexOf('>属于</h4>') < partSheet.indexOf('>被依赖</h4>'));
    assert.ok(buildIntentDetailHtml({project_id:'p', intent: flowIntents[8], snaps: [], decisions: []}).includes('与其他意图没有关系。'));
    const sourced = buildDecisionDetailHtml({project_id:'p', decision: flowDecisions[1], intents: []});
    assert.ok(sourced.includes('来源') && sourced.includes('data-detail-type="intent" data-remote-id="p__intent-001"'));
    const projectLevel = buildDecisionDetailHtml({project_id:'p', decision: flowDecisions[0], intents: []});
    assert.ok(projectLevel.includes('<span class="chip">项目级</span>'));

    // Timeline pages come from /snaps; Load more asks for the next offset; the filter goes to the server.
    const savedFetch = fetchJson;
    const requested = [];
    const responses = new Map();
    fetchJson = url => { requested.push(url); return responses.get(url) || Promise.reject(new Error('unexpected ' + url)); };
    const snapPage = (offset, count, total, more, intentId = 'intent-001') => ({project_id:'p', total, offset, limit:50, has_more: more,
      snaps: Array.from({length: count}, (_, index) => {
        const id = 'snap-' + String(500 - offset - index).padStart(3, '0');
        return {id, project_id:'p', remote_id:'p__' + id, intent_id: intentId, what:'Checkpoint ' + (offset + index), created_at: at(40)};
      })});
    state.activeTab = 'snaps';
    state._timeline = null;
    state.overview = {...state.overview, total_snaps: 75, active_intents: [{...flowIntents[0], snap_ids: Array(60).fill('snap-001'), latest_snap_id: 'snap-500'}, {...flowIntents[2], snap_ids: ['snap-101'], latest_snap_id: 'snap-101'}], other_intents: []};
    const first = '/api/v1/projects/p/snaps?offset=0&limit=50';
    responses.set(first, Promise.resolve(snapPage(0, 50, 75, true)));
    renderSnapsTab();
    assert.equal(requested.at(-1), first);
    assert.ok(el.detailContent.innerHTML.includes('view-loading'));
    await flush();
    assert.equal(state._timeline.snaps.length, 50);
    assert.ok(el.detailContent.innerHTML.includes('data-remote-id="p__snap-500"'));
    assert.ok(el.detailContent.innerHTML.includes('id="load-more-snaps"><svg') && el.detailContent.innerHTML.includes('<span class="button-label">加载更多（25）</span></button>'));
    assert.ok(el.detailContent.innerHTML.includes('75 个检查点'));
    responses.set('/api/v1/projects/p/snaps?offset=50&limit=50', Promise.resolve(snapPage(50, 25, 75, false)));
    await loadTimelinePage();
    assert.equal(requested.at(-1), '/api/v1/projects/p/snaps?offset=50&limit=50');
    assert.equal(state._timeline.snaps.length, 75);
    assert.ok(!el.detailContent.innerHTML.includes('load-more-snaps'));
    assert.ok(state._snapCache.has('p__snap-451'));
    // A slow page for an older filter cannot replace the newer one.
    let releaseSlow;
    responses.set(first + '&intent_id=intent-003', new Promise(resolve => { releaseSlow = resolve; }));
    resetTimeline('intent-003');
    renderSnapsTab();
    assert.equal(requested.at(-1), first + '&intent_id=intent-003');
    assert.ok(el.detailContent.innerHTML.includes('Google Pay'));
    responses.set(first, Promise.resolve(snapPage(0, 3, 3, false)));
    resetTimeline('');
    renderSnapsTab();
    await flush();
    releaseSlow(snapPage(0, 1, 1, false, 'intent-003'));
    await flush();
    assert.equal(state._timeline.intentId, '');
    assert.equal(state._timeline.snaps.length, 3);
    responses.set(first, Promise.reject(new Error('offline')));
    resetTimeline('');
    renderSnapsTab();
    await flush();
    assert.ok(el.detailContent.innerHTML.includes('data-retry-timeline'));

    // A latest Snap outside the overview window is fetched once and its label refreshed in place.
    state.activeTab = 'intents';
    state._snapCache = new Map();
    state._snapFailed = new Set();
    state._detailCache = new Map();
    state.overview = {...state.overview, recent_snaps: [], active_intents: [{...flowIntents[0], snap_ids:['snap-007'], latest_snap_id:'snap-007'}], other_intents: []};
    const label = document.getElementById('latest-snap-label');
    label.dataset.latestSnap = 'p__snap-007';
    const savedQuery = el.detailContent.querySelectorAll;
    el.detailContent.querySelectorAll = selector => selector === '[data-latest-snap]' ? [label] : [];
    responses.set('/api/v1/snaps/p__snap-007', Promise.resolve({remote_id:'p__snap-007', project_id:'p', id:'snap-007', snap:{id:'snap-007', intent_id:'intent-001', what:'old', created_at: new Date().toISOString()}, intent:{}}));
    renderIntentsTab();
    assert.ok(el.detailContent.innerHTML.includes('data-latest-snap="p__snap-007">检查点 snap-007</span>'));
    await flush();
    assert.equal(requested.filter(url => url === '/api/v1/snaps/p__snap-007').length, 1);
    assert.equal(label.textContent, '刚刚更新');
    assert.ok(state._detailCache.has('snap:p__snap-007'));
    renderIntentsTab();
    await flush();
    assert.equal(requested.filter(url => url === '/api/v1/snaps/p__snap-007').length, 1);
    assert.ok(el.detailContent.innerHTML.includes('data-latest-snap="p__snap-007">刚刚更新</span>'));
    el.detailContent.querySelectorAll = savedQuery;
    fetchJson = savedFetch;

    // Search: at most 50 matches, and the reader is told when there are more.
    const fifty = Array.from({length: 50}, (_, index) => ({object_type:'intent', remote_id:'p__intent-' + index, id:'intent-' + index, status:'active', what:'Pay ' + index, why:''}));
    assert.deepEqual(searchSummary({matches: fifty, total: 132, truncated: true}), {text: '显示前 50 条，共 132 条，请细化搜索', visible: true});
    assert.deepEqual(searchSummary({matches: fifty.slice(0, 2), total: 2, truncated: false}), {text: '2 个结果', visible: false});
    el.searchDialog.open = true;
    renderSearchResults({matches: fifty, total: 132, truncated: true, query: 'pay'});
    assert.equal(el.searchStatus.innerHTML, '显示前 50 条，共 132 条，请细化搜索');
    assert.equal(el.searchStatus.classList.contains('visually-hidden'), false);
    assert.equal(el.searchStatus.classList.contains('is-note'), true);
    window.IntHubI18n.setLanguage('en');
    assert.equal(searchSummary({matches: fifty, total: 132, truncated: true}).text, 'Showing 50 of 132 — refine the search');
    renderSearchResults({matches: fifty.slice(0, 3), total: 3, truncated: false, query: 'pay'});
    assert.equal(el.searchStatus.classList.contains('visually-hidden'), true);
    assert.equal(el.searchStatus.classList.contains('is-note'), false);
    window.IntHubI18n.setLanguage('zh-CN');
    el.searchDialog.open = false;
  })()`, context);
  console.log('Relation state parity, Flow layout and rendering, brief and sheet relations, paged timeline, Snap fallback and truncated search tests passed.');
}

async function settingsCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    window.IntHubI18n.setLanguage('zh-CN');
    const saved = {fetchJson, loadProject, downloadFile};
    const calls = [];
    let reply = () => ({});
    const track = async (url, options = {}) => { calls.push({url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null}); return reply(url, options); };
    fetchJson = track;
    const now = Date.now();
    const iso = (offset) => new Date(now + offset).toISOString();
    const day = 86400000;
    const at = (pathname, search = '') => { window.location.pathname = pathname; window.location.search = search; return readRoute(); };

    // Routes: each account and team pane has its own path; project routes stay on / and keep their tab.
    assert.equal([at('/account').page, at('/account').pane].join(), 'account,profile');
    assert.equal(at('/account/danger').pane, 'danger');
    assert.equal([at('/settings').page, at('/settings').pane].join(), 'settings,tokens');
    assert.equal(at('/settings/teams/').pane, 'teams', 'a trailing slash is the same page');
    assert.equal([at('/teams/acme').page, at('/teams/acme').team, at('/teams/acme').pane].join(), 'team,acme,members');
    assert.equal(at('/teams/acme/projects').pane, 'projects');
    assert.equal(at('/teams/acme/settings').pane, 'settings');
    assert.equal([at('/invite', '?token=abc').page, at('/invite', '?token=abc').token].join(), 'invite,abc');
    assert.equal(at('/account/tokens').page, 'project', 'these shipped for a day and have no alias');
    assert.equal(at('/settings/other').page, 'project');
    assert.equal(at('/account/other').page, 'project');
    const settingsRoute = at('/', '?project=p&tab=settings&section=danger');
    assert.equal([settingsRoute.page, settingsRoute.tab, settingsRoute.section].join(), 'project,settings,danger');
    at('/');

    // IntHub Local has no accounts: those paths are ordinary project routes there.
    state.config = {authRequired: false, authMode: 'none', apiBaseUrl: 'http://127.0.0.1:7317'};
    assert.equal(isDialogRoute({page: 'account'}), false);
    assert.equal(isSiteRoute({page: 'team'}), false);
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: 'https://inthub.tenon.asia'};
    assert.equal(isDialogRoute({page: 'account'}), true);
    assert.equal(isDialogRoute({page: 'settings'}), true);
    assert.equal(isSiteRoute({page: 'team'}), true);
    assert.equal(isSiteRoute({page: 'project'}), false);

    // A Tenon hub: Account opens in a dialog over the untouched project view.
    state.account = {id: 'acct_1', login: 'dozy', display_name: 'Dozy <QA>'};
    state.projects = [{id: 'p', name: 'checkout', full_name: 'checkout'}, {id: 'q', name: 'docs', full_name: 'docs'}];
    state.currentProjectId = 'p';
    state._loadedProjectId = 'p';
    state.activeTab = 'overview';
    state.overview = {history: {project_id: 'p', revision: 'a'.repeat(64), last_synced_at: iso(0)}, project: {id: 'p', name: 'checkout', full_name: 'checkout', permission: 'admin', visibility: 'private', owner: {type: 'account', name: 'Dozy'}}};
    el.detailContent.innerHTML = 'project view';
    routes.length = 0;
    openSettingsDialog('account', 'profile');
    assert.equal(routes.join(), 'push', 'one history entry, so Back closes it');
    assert.equal(state._dialog, 'account');
    assert.equal(state.page, 'project', 'the page stays where it was, under the dialog');
    assert.equal(el.settingsDialog.open, true);
    assert.equal(el.settingsDialogTitle.textContent, '账号');
    assert.equal(el.shell.classList.contains('is-site'), false);
    assert.equal(el.detailContent.innerHTML, 'project view');
    assert.equal(document.title, '账号 · IntHub');
    assert.equal(routeUrl(), '/account');
    let page = el.settingsDialogBody.innerHTML;
    assert.ok(!page.includes('<h1') && !page.includes('eyebrow'), 'the dialog header carries the title');
    assert.ok(page.includes('class="settings-nav-item" href="/account" data-route aria-current="page"><svg') && page.includes('<span>个人资料</span></a>'));
    assert.ok(page.includes('href="/account/danger" data-route><svg') && page.includes('<span>危险操作</span></a>'));
    assert.ok(!page.includes('访问令牌') && !page.includes('/settings'), 'tokens and teams are settings, not the account');
    assert.ok(page.includes('Dozy &lt;QA&gt;') && page.includes('@dozy') && !page.includes('<QA>'));
    assert.ok(page.includes('href="https://account.tenon.asia/account/"') && page.includes('在 Tenon 中修改'));
    assert.ok(page.includes('class="monogram"') && !page.includes('data-delete-account'));
    routes.length = 0;
    openSettingsDialog('account', 'danger');
    assert.equal(routes.join(), 'replace', 'moving between panes adds no entry');
    assert.equal(routeUrl(), '/account/danger');
    page = el.settingsDialogBody.innerHTML;
    assert.ok(page.includes('data-delete-account') && page.includes('button button-danger') && page.includes('<span class="button-label">删除账号</span>'));

    // Closing steps back over the entry the dialog added; a dialog restored by a link only drops its URL.
    routes.length = 0;
    window.history.state = {inthub: 'dialog'};
    closeSettingsDialog();
    assert.deepEqual([routes.join(), el.settingsDialog.open, state._dialog, el.settingsDialogBody.innerHTML], ['back', false, null, '']);
    assert.equal(document.title, 'checkout · IntHub');
    assert.equal(document.activeElement, el.accountMenuTrigger, 'focus returns to what opened it');
    routes.length = 0;
    openSettingsDialog('account', 'profile', {history: 'none'});
    closeSettingsDialog();
    assert.equal(routes.join(), 'replace');
    assert.equal(routeUrl(), '/?project=p');

    // Usage: each owner's allowance, in the units a person reads.
    assert.equal(formatBytes(512), '512 B');
    assert.equal(formatBytes(1536), '1.5 KB');
    assert.equal(formatBytes(1024 ** 3), '1.0 GB');
    assert.equal(formatBytes(300 * 1024 ** 2), '300 MB');
    reply = (url) => url === '/api/v1/usage' ? {owners: [
      {type: 'account', name: null, projects: 3, projects_limit: 100, storage_bytes: 1536, storage_limit: 1024 ** 3},
      {type: 'team', name: 'Acme <Inc>', projects: 1, projects_limit: 100, storage_bytes: 0, storage_limit: 1024 ** 3},
    ]} : {};
    openSettingsDialog('settings', 'usage');
    await flush();
    assert.equal(routeUrl(), '/settings/usage');
    page = el.settingsDialogBody.innerHTML;
    assert.ok(page.includes('个人') && page.includes('3 / 100 个项目') && page.includes('历史存储 1.5 KB / 1.0 GB') && page.includes('Acme &lt;Inc&gt;'));
    assert.ok(page.includes('href="/settings/usage" data-route aria-current="page"><svg'));
    closeSettingsDialog({history: 'none'});
    assert.equal(state._usage, null);

    reply = (url) => url === '/api/v1/auth/tokens' ? {tokens: [
      {id: 'pat_used', name: 'laptop', created_at: iso(-day), expires_at: iso(80 * day), last_used_at: iso(-3600000), revoked_at: null},
      {id: 'pat_idle', name: 'ci-runner', created_at: iso(-2 * day), expires_at: iso(20 * day), last_used_at: null, revoked_at: null},
      {id: 'pat_gone', name: 'old-macbook', created_at: iso(-9 * day), expires_at: iso(50 * day), last_used_at: null, revoked_at: iso(-day)},
      {id: 'pat_late', name: 'stale-runner', created_at: iso(-40 * day), expires_at: iso(-60000), last_used_at: null, revoked_at: null},
    ]} : {};
    routes.length = 0;
    openSettingsDialog('settings', 'tokens');
    await flush();
    assert.equal(routes.join(), 'push');
    assert.equal(routeUrl(), '/settings');
    assert.equal(document.title, '设置 · IntHub');
    assert.equal(el.settingsDialogTitle.textContent, '设置');
    page = el.settingsDialogBody.innerHTML;
    assert.ok(page.includes('href="/settings" data-route aria-current="page"><svg') && page.includes('<span>访问令牌</span>') && page.includes('href="/settings/teams" data-route><svg'));
    // A listbox of our own: the value sits in a hidden input and every option is a button.
    assert.ok(page.includes('value="itt"') && !page.includes('<select') && !page.includes('<option'));
    assert.ok(page.includes('<input type="hidden" name="token-days" value="90">'));
    assert.ok(page.includes('id="token-days" type="button" role="combobox" aria-haspopup="listbox" aria-expanded="false" aria-controls="token-days-options"'));
    assert.ok(page.includes('<span class="select-value">90 天</span>') && page.includes('id="token-days-options" role="listbox" popover="manual"'));
    assert.ok(page.includes('data-value="90" aria-selected="true"') && page.includes('data-value="365" aria-selected="false"') && page.includes('<span>365 天</span>'));
    assert.ok(page.includes('laptop') && page.includes('ci-runner') && page.includes('从未使用') && page.includes('最近使用'));
    assert.ok(!page.includes('old-macbook') && !page.includes('stale-runner'), 'revoked and expired tokens are not listed');
    assert.equal((page.match(/class="settings-list"/g) || []).length, 1, 'one list');
    assert.ok(page.indexOf('data-token-form') < page.indexOf('class="settings-list"'), 'the form sits on top of the list');
    routes.length = 0;
    window.location.pathname = '/settings';
    openSettingsDialog('settings', 'tokens');
    assert.equal(routes.join(), 'replace', 'the same pane adds no history entry');
    window.location.pathname = '/';
    routes.length = 0;

    // Generating: a trimmed name, one of the offered lifetimes, and the secret once, under its row.
    reply = (url, options) => options.method === 'POST' ? {id: 'pat_fresh', token: 'ith_pat_SECRET', name: 'release-bot', created_at: iso(0), expires_at: iso(30 * day)} : {};
    await assert.rejects(generateAccessToken({name: '   ', days: 30}), (error) => error.message === '请输入令牌名称。' && error.code === 'INVALID_INPUT');
    calls.length = 0;
    await generateAccessToken({name: '  release-bot ', days: '30'});
    assert.deepEqual(calls[0], {url: '/api/v1/auth/tokens', method: 'POST', body: {name: 'release-bot', ttl_seconds: 30 * 86400}});
    page = el.settingsDialogBody.innerHTML;
    assert.ok(page.indexOf('ith_pat_SECRET') > 0 && page.indexOf('ith_pat_SECRET') < page.indexOf('laptop'));
    assert.ok(page.includes('release-bot') && page.indexOf('release-bot') < page.indexOf('ith_pat_SECRET'));
    assert.ok(page.includes('class="secret-box"') && page.includes('data-copy-new-token') && page.includes('请立即复制，此后不会再显示。'));
    calls.length = 0;
    await generateAccessToken({name: 'x', days: 7});
    assert.equal(calls[0].body.ttl_seconds, 90 * 86400, 'only 30, 90 or 365 days');

    // Revoking asks first; afterwards the row and its secret are gone and a toast says so.
    calls.length = 0;
    reply = () => ({revoked: true});
    confirmRevokeToken('pat_idle');
    assert.equal(el.confirmDialog.open, true);
    assert.equal(el.confirmTitle.textContent, '作废 ci-runner？');
    assert.equal(el.confirmField.hidden, true);
    assert.equal(el.confirmOk.disabled, false);
    assert.ok(el.confirmOk.innerHTML.includes('<svg') && el.confirmOk.innerHTML.includes('<span class="button-label">作废令牌</span>'), 'the action keeps its icon');
    assert.equal(document.activeElement, el.confirmCancel);
    await runConfirm();
    assert.deepEqual(calls.map((call) => call.method + ' ' + call.url), ['POST /api/v1/auth/tokens/pat_idle/revoke']);
    assert.equal(el.confirmDialog.open, false);
    assert.ok(!el.settingsDialogBody.innerHTML.includes('ci-runner'));
    assert.equal(el.statusLine.textContent, '令牌已作废。');
    fetchJson = async () => { throw new ApiRequestError('gone', 404, 'OBJECT_NOT_FOUND'); };
    await revokeAccessToken('pat_fresh');
    assert.ok(!el.settingsDialogBody.innerHTML.includes('ith_pat_SECRET'), 'already revoked is gone too');
    fetchJson = track;

    // Moving to another pane or closing the dialog drops a new secret; the project view never left.
    reply = (url, options) => options.method === 'POST' ? {id: 'pat_again', token: 'ith_pat_AGAIN', name: 'again', created_at: iso(0), expires_at: iso(90 * day)} : {teams: [], tokens: []};
    await generateAccessToken({name: 'again', days: 90});
    assert.ok(el.settingsDialogBody.innerHTML.includes('ith_pat_AGAIN'));
    openSettingsDialog('account', 'profile');
    assert.equal(state._newToken, null);
    openSettingsDialog('settings', 'tokens');
    await flush();
    assert.ok(!el.settingsDialogBody.innerHTML.includes('ith_pat_AGAIN'));
    await generateAccessToken({name: 'again', days: 90});
    closeSettingsDialog({history: 'none'});
    assert.equal(state._newToken, null);
    assert.equal(state._tokens, null);
    assert.equal(el.settingsDialogBody.innerHTML, '');
    switchTab('settings');
    assert.equal(state.page, 'project');
    assert.equal(el.detailContent.classList.contains('is-hidden'), false);
    assert.equal(document.title, 'checkout · IntHub');
    assert.equal(routeUrl(), '/?project=p&tab=settings');

    // The project Settings tab uses the same layout: no title of its own, one pane per URL.
    let html = el.detailContent.innerHTML;
    assert.ok(html.includes('class="settings-layout"') && !html.includes('<h1'));
    assert.ok(html.includes('class="settings-nav-item" href="/?project=p&amp;tab=settings" data-route aria-current="page"><svg') && html.includes('<span>常规</span></a>'));
    assert.ok(html.includes('href="/?project=p&amp;tab=settings&amp;section=danger" data-route><svg') && html.includes('<span>危险操作</span></a>'));
    assert.ok(!html.includes('section=members'), 'a personal project has no members section');
    assert.ok(html.includes('id="project-name"') && html.includes('value="checkout"') && html.includes('data-rename-submit disabled'));
    assert.ok(html.includes('<code>REMOTE_CHANGED</code>') && !html.includes('itt remote add'));
    assert.ok(html.includes('data-export-project') && html.includes('data-change-visibility="public"') && !html.includes('data-delete-project'));
    assert.equal(projectNameProblem(''), '请输入项目名称。');
    assert.equal(projectNameProblem('a/b'), '项目名称不能包含斜杠或控制字符。');
    assert.equal(projectNameProblem('a\\\\b'), '项目名称不能包含斜杠或控制字符。');
    assert.equal(projectNameProblem('tab\\there'), '项目名称不能包含斜杠或控制字符。');
    assert.equal(projectNameProblem('..'), '名称不能是 . 或 ..');
    assert.equal(projectNameProblem('x'.repeat(121)), '最多 120 个字符。');
    assert.equal(projectNameProblem('支'.repeat(120)), '');
    assert.equal(projectNameProblem('😀'.repeat(120)), '', 'counted in code points, like the hub');
    state._renameDraft = {projectId: 'p', value: 'docs', error: '已有名为 docs 的项目。'};
    renderView();
    assert.ok(el.detailContent.innerHTML.includes('aria-invalid="true"') && el.detailContent.innerHTML.includes('已有名为 docs 的项目。'));
    state._renameDraft = null;

    // Sections are links with their own URL; an unknown one, or Members on a personal project, is General.
    window.location.pathname = '/';
    window.location.search = '?project=p&tab=settings&section=danger';
    await applyRoute(readRoute());
    assert.equal(routeUrl(), '/?project=p&tab=settings&section=danger');
    html = el.detailContent.innerHTML;
    assert.ok(html.includes('<span>危险操作</span></a>') && html.includes('class="button button-danger" type="button" data-delete-project'));
    assert.ok(html.includes('data-transfer-project') || html.includes('正在加载…') || html.includes('href="/settings/teams"'));
    state._settingsSection = 'members';
    assert.equal(projectSettingsSection(), 'general');
    state._settingsSection = 'nonsense';
    assert.equal(projectSettingsSection(), 'general');
    state._settingsSection = '';
    state._teams = null;

    // Local hubs get neither visibility nor transfer.
    state.config = {authRequired: false, authMode: 'none', apiBaseUrl: ''};
    renderView();
    assert.ok(!el.detailContent.innerHTML.includes('data-change-visibility'));
    state._settingsSection = 'danger';
    renderView();
    assert.ok(!el.detailContent.innerHTML.includes('transfer-control') && el.detailContent.innerHTML.includes('data-delete-project'));
    state._settingsSection = '';
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: 'https://inthub.tenon.asia'};
    window.location.search = '';

    routes.length = 0;
    calls.length = 0;
    reply = (url, options) => ({project: {id: 'p', name: JSON.parse(options.body).name, full_name: JSON.parse(options.body).name, created_at: iso(0), visibility: 'private'}});
    await renameProject('p', 'checkout v2');
    assert.deepEqual(calls.at(-1), {url: '/api/v1/projects/p/rename', method: 'POST', body: {name: 'checkout v2'}});
    assert.equal(state.projects[0].name, 'checkout v2');
    assert.equal(state.overview.project.name, 'checkout v2');
    assert.equal(el.projectPickerLabel.textContent, 'checkout v2');
    assert.equal(document.title, 'checkout v2 · IntHub');
    assert.equal(routes.join(), '', 'the URL carries the ID and stays');
    assert.equal(renameErrorMessage(new ApiRequestError('x', 409, 'NAME_TAKEN'), 'docs'), '已有名为 docs 的项目。');
    assert.equal(renameErrorMessage(new ApiRequestError('x', 400, 'INVALID_INPUT', 'Project name must be 1–120 characters.'), 'a'), 'Project name must be 1–120 characters.');

    // Going public needs the typed name and says what it exposes; going private is a plain confirm.
    const typeName = (value) => { el.confirmInput.value = value; for (const listener of el.confirmInput.events.get('input') || []) listener(); };
    calls.length = 0;
    confirmVisibility('public');
    assert.equal(el.confirmTitle.textContent, '将 checkout v2 设为公开？');
    assert.ok(el.confirmBody.textContent.includes('互联网上的任何人') && el.confirmBody.textContent.includes('作者邮箱不会向访客显示') && el.confirmBody.textContent.includes('可能会保留'));
    assert.equal(el.confirmField.hidden, false);
    assert.equal(el.confirmOk.disabled, true);
    assert.equal(el.confirmOk.classList.contains('button-danger'), true);
    typeName('checkout v2');
    reply = () => ({project: {id: 'p', visibility: 'public'}});
    state.activeTab = 'settings';
    await runConfirm();
    assert.deepEqual(calls.at(-1), {url: '/api/v1/projects/p/visibility', method: 'POST', body: {visibility: 'public', confirm: 'checkout v2'}});
    assert.equal(state.overview.project.visibility, 'public');
    assert.equal(state.projects[0].visibility, 'public');
    assert.ok(el.detailContent.innerHTML.includes('data-change-visibility="private"'));
    assert.equal(el.statusLine.textContent, '这个项目现已公开。');
    confirmVisibility('private');
    assert.equal(el.confirmField.hidden, true, 'no typing to make it private');
    assert.equal(el.confirmOk.disabled, false);
    assert.equal(el.confirmOk.classList.contains('button-danger'), false);
    assert.equal(el.confirmOk.classList.contains('button-primary'), true);
    await runConfirm();
    assert.deepEqual(calls.at(-1).body, {visibility: 'private', confirm: ''});
    assert.equal(state.overview.project.visibility, 'private');

    // Transfer lists the teams I administer, and My account once it is a team's project.
    let loaded = null;
    loadProject = async (id, options) => { loaded = {id, options}; };
    state._teams = [{id: 't1', name: 'Acme', role: 'admin'}, {id: 't2', name: 'Guests', role: 'member'}];
    assert.deepEqual(transferTargets().map((target) => target.label), ['Acme']);
    state.overview.project.owner = {type: 'team', id: 't1', slug: 'acme', name: 'Acme'};
    state.overview.project.full_name = 'acme/checkout v2';
    assert.deepEqual(transferTargets().map((target) => target.label), ['我的账号']);
    state._teams = [...state._teams, {id: 't3', name: 'Beta', role: 'admin'}];
    assert.deepEqual(transferTargets().map((target) => target.value), ['t3', 'account']);
    assert.equal(projectSettingsSection(), 'general');
    state._settingsSection = 'members';
    assert.equal(projectSettingsSection(), 'members');
    reply = (url) => url === '/api/v1/teams/t1' ? {team: {id: 't1'}, members: [{id: 'a', name: 'Ana', joined_at: iso(0), role: 'admin', email: 'ana@example.com'}]} : {};
    renderProjectSettings();
    await flush();
    html = el.detailContent.innerHTML;
    assert.ok(html.includes('Ana') && html.includes('管理员') && html.includes('href="/teams/acme" data-route') && !html.includes('data-member-role') && !html.includes('data-remove-member'), 'read-only');
    state._settingsSection = 'danger';
    state._projectTeam = null;
    calls.length = 0;
    const transferSelect = document.getElementById('transfer-target');
    transferSelect.value = 'account';
    const detailQuery = el.detailContent.querySelector;
    el.detailContent.querySelector = (selector) => selector === '.transfer-select input' ? transferSelect : null;
    confirmTransfer();
    assert.equal(el.confirmTitle.textContent, '将 checkout v2 转移到 我的账号？');
    assert.equal(el.confirmOk.disabled, true);
    typeName('checkout v2');
    reply = (url) => url === '/api/v1/projects' ? {projects: state.projects} : {};
    await runConfirm();
    assert.deepEqual(calls.find((call) => call.url.endsWith('/transfer')), {url: '/api/v1/projects/p/transfer', method: 'POST', body: {team_id: null, confirm: 'checkout v2'}});
    assert.deepEqual(loaded, {id: 'p', options: {history: 'replace'}});
    assert.equal(transferErrorMessage(new ApiRequestError('x', 409, 'NAME_TAKEN')), '那里已有同名项目。');
    assert.equal(transferErrorMessage(new ApiRequestError('x', 404, 'TEAM_NOT_FOUND')), '请选择你管理的团队。');
    el.detailContent.querySelector = detailQuery;
    state._settingsSection = '';
    state.overview.project.owner = {type: 'account', name: 'Dozy'};

    let downloaded = null;
    downloadFile = (name, text, type) => { downloaded = {name, text, type}; };
    reply = () => ({format: 'inthub-export', format_version: 1, project: {id: 'p', name: 'checkout v2'}, revisions: []});
    await exportCurrentProject(document.getElementById('export-button'));
    assert.equal(calls.at(-1).url, '/api/v1/projects/p/export');
    assert.equal(downloaded.name, 'checkout v2.inthub-export.json');
    assert.equal(downloaded.type, 'application/json');
    assert.ok(downloaded.text.startsWith('{\\n  "format": "inthub-export"') && downloaded.text.endsWith('}\\n'));
    assert.equal(exportFileName('team/app: v2?'), 'team-app- v2-.inthub-export.json');
    assert.equal(exportFileName('移动端结算'), '移动端结算.inthub-export.json');
    assert.equal(exportFileName('..'), 'project.inthub-export.json');

    // Deleting waits for the exact name, then opens the remaining project, or the empty state after the last one.
    loaded = null;
    calls.length = 0;
    confirmDeleteProject();
    assert.equal(el.confirmField.hidden, false);
    assert.equal(el.confirmOk.disabled, true);
    assert.equal(document.activeElement, el.confirmInput);
    assert.equal(el.confirmTitle.textContent, '删除 checkout v2？');
    assert.ok(el.confirmLabel.innerHTML.includes('<strong class="confirm-name">checkout v2</strong>'));
    typeName('checkout');
    assert.equal(el.confirmOk.disabled, true);
    await runConfirm();
    assert.equal(calls.length, 0, 'nothing is sent before the exact name');
    typeName('checkout v2');
    assert.equal(el.confirmOk.disabled, false);
    fetchJson = async () => { throw new ApiRequestError('mismatch', 400, 'CONFIRMATION_MISMATCH'); };
    await runConfirm();
    assert.equal(el.confirmDialog.open, true);
    assert.equal(el.confirmError.textContent, '请按显示的名称准确输入。');
    fetchJson = track;
    reply = () => ({deleted: true, id: 'p'});
    await runConfirm();
    assert.deepEqual(calls.at(-1), {url: '/api/v1/projects/p/delete', method: 'POST', body: {confirm: 'checkout v2'}});
    assert.equal(el.confirmDialog.open, false);
    assert.deepEqual(state.projects.map((project) => project.id), ['q']);
    assert.deepEqual(loaded, {id: 'q', options: {history: 'replace'}});
    assert.equal(state.activeTab, 'overview');
    assert.equal(el.statusLine.textContent, '已删除 checkout v2。');
    state.currentProjectId = 'q';
    reply = () => ({deleted: true, id: 'q'});
    await deleteProject('q', 'docs');
    assert.equal(state.currentProjectId, null);
    assert.equal(el.projectPickerLabel.textContent, '暂无项目');
    assert.equal(document.title, 'IntHub');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));

    assert.equal(tHtml('Type {name} to confirm.', {name: '<b>x</b>'}), '输入 <b>x</b> 以确认。');
    fetchJson = saved.fetchJson;
    loadProject = saved.loadProject;
    downloadFile = saved.downloadFile;
    state.page = 'project';
    state.account = null;
    state.overview = null;
    state._teams = null;
    state.activeTab = 'overview';
  })()`, context);
  console.log('Account panes and tokens, project settings sections, visibility, transfer, rename/export/delete with confirmation and token dialog focus tests passed.');
}

async function teamCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    window.IntHubI18n.setLanguage('zh-CN');
    const saved = {fetchJson};
    const calls = [];
    let reply = () => ({});
    fetchJson = async (url, options = {}) => {
      calls.push({url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null});
      const answer = reply(url, options);
      if (answer instanceof Error) throw answer;
      return answer;
    };
    const iso = new Date().toISOString();
    window.location.origin = 'https://inthub.example';
    window.location.pathname = '/';
    window.location.search = '';
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: ''};
    state.account = {id: 'me', display_name: 'Ana', email: 'ana@example.com'};
    state.projects = [];
    state.currentProjectId = null;
    state.page = 'project';

    // A form with the fields and the error line these handlers read.
    let formCount = 0;
    const fakeForm = (fields) => {
      const button = document.getElementById('team-submit-' + ++formCount);
      const error = document.getElementById('team-error-' + formCount);
      button.disabled = false;
      error.hidden = true;
      return {button, error, elements: Object.fromEntries(Object.entries(fields).map(([name, value]) => [name, {value, invalid: false, setAttribute() { this.invalid = true; }}])),
        querySelector: (selector) => selector === '.field-error' ? error : selector === '[type=submit]' ? button : null};
    };

    // The URL is derived from a Latin name and left to the person otherwise; typing it stops the derivation.
    assert.equal(slugFromName('Acme Robotics'), 'acme-robotics');
    assert.equal(slugFromName('Café Zürich'), 'cafe-zurich');
    assert.equal(slugFromName('  --Spaced   out--  '), 'spaced-out');
    assert.equal(slugFromName('贝塔实验室'), '');
    assert.equal(slugFromName('Acme 实验室'), '');
    assert.equal(slugFromName('x'.repeat(50)).length, 39);
    assert.equal(teamSlugProblem(''), '请输入团队 URL。');
    assert.ok(teamSlugProblem('Acme').includes('小写字母'));
    assert.ok(teamSlugProblem('-acme').includes('小写字母'));
    assert.equal(teamSlugProblem('a'), '');
    assert.equal(teamSlugProblem('a'.repeat(39)), '');
    assert.ok(teamSlugProblem('a'.repeat(40)).includes('39'));
    assert.equal(teamNameProblem(''), '请输入团队名称。');
    state._teamDraft = {name: '', slug: '', edited: false};
    const slugField = {value: ''};
    const draftForm = {elements: {'team-slug': slugField}, querySelector: () => null};
    updateTeamDraft({name: 'team-name', value: 'Acme Robotics', form: draftForm});
    assert.equal(slugField.value, 'acme-robotics');
    slugField.value = 'acme';
    updateTeamDraft({name: 'team-slug', value: 'acme', form: draftForm});
    updateTeamDraft({name: 'team-name', value: 'Acme Robotics Inc', form: draftForm});
    assert.equal(slugField.value, 'acme', 'a typed URL stays');
    updateTeamDraft({name: 'team-slug', value: '', form: draftForm});
    updateTeamDraft({name: 'team-name', value: 'Back', form: draftForm});
    assert.equal(slugField.value, 'back', 'clearing it starts deriving again');

    // My teams, in the Settings dialog.
    reply = () => ({teams: [
      {id: 't1', slug: 'acme', name: 'Acme <Inc>', created_at: iso, role: 'admin', members: 3, projects: 1},
      {id: 't2', slug: 'beta', name: '贝塔', created_at: iso, role: 'viewer', members: 1, projects: 2},
    ]});
    openSettingsDialog('settings', 'teams');
    await flush();
    let page = el.settingsDialogBody.innerHTML;
    assert.ok(page.includes('href="/teams/acme" data-route') && page.includes('Acme &lt;Inc&gt;') && !page.includes('Acme <Inc>'));
    assert.ok(page.includes('管理员') && page.includes('只读成员') && page.includes('3 位成员') && page.includes('2 个项目'));
    assert.ok(page.includes('data-team-form') && page.includes('id="new-team-slug"'));

    // Creating a team goes to its page; a taken URL or a bad one stays in the form.
    calls.length = 0;
    let form = fakeForm({'team-name': ' ', 'team-slug': ''});
    await createTeam(form);
    assert.equal(calls.length, 0);
    assert.equal(form.error.textContent, '请输入团队名称。');
    assert.equal(form.elements['team-name'].invalid, true);
    form = fakeForm({'team-name': 'New', 'team-slug': 'Bad'});
    await createTeam(form);
    assert.equal(form.elements['team-slug'].invalid, true, 'the field at fault is the one marked');
    assert.equal(form.elements['team-name'].invalid, false);
    form = fakeForm({'team-name': 'New', 'team-slug': 'taken'});
    reply = () => new ApiRequestError('x', 409, 'NAME_TAKEN', 'The team URL taken is taken.');
    await createTeam(form);
    assert.equal(form.error.textContent, '团队 URL taken 已被占用。');
    assert.equal(form.elements['team-slug'].invalid, true);
    assert.equal(state._dialog, 'settings');
    form = fakeForm({'team-name': 'Many', 'team-slug': 'many'});
    reply = () => new ApiRequestError('x', 409, 'TEAM_LIMIT', 'An account can create up to 50 teams.');
    await createTeam(form);
    assert.equal(form.error.textContent, '你创建的团队数量已达上限。');

    const members = () => [
      {id: 'me', name: 'Ana', role: 'admin', joined_at: iso, you: true, email: 'ana@example.com'},
      {id: 'ben', name: 'Ben <Wu>', role: 'member', joined_at: iso, you: false, email: 'ben@example.com'},
    ];
    const detail = (role = 'admin', extra = {}) => ({
      team: {id: 't1', slug: 'acme', name: 'Acme', created_at: iso}, role, members: members(),
      invites: role === 'admin' ? [{id: 'inv1', role: 'viewer', created_at: iso, expires_at: iso, invited_by: 'Ana'}] : [],
      projects: [{id: 'p1', name: 'app', full_name: 'acme/app', visibility: 'public', last_synced_at: iso}],
      ...extra,
    });
    form = fakeForm({'team-name': 'Acme', 'team-slug': 'acme'});
    calls.length = 0;
    routes.length = 0;
    reply = (url, options) => options.method === 'POST' ? {team: {id: 't1', slug: 'acme', name: 'Acme'}, role: 'admin'} : detail();
    await createTeam(form);
    await flush();
    assert.deepEqual(calls[0], {url: '/api/v1/teams', method: 'POST', body: {name: 'Acme', slug: 'acme'}});
    assert.equal(state.page, 'team');
    assert.equal(routes.join(), 'push');
    assert.equal(routeUrl(), '/teams/acme');
    assert.equal(document.title, 'Acme · IntHub');

    // Members: admins manage; everyone can leave.
    page = el.siteContent.innerHTML;
    assert.ok(page.includes('class="page-title settings-title">Acme</h1>') && !page.includes('eyebrow'));
    assert.ok(page.includes('href="/teams/acme" data-route aria-current="page"><svg') && page.includes('<span>成员</span></a>') && page.includes('href="/teams/acme/projects" data-route><svg') && page.includes('<span>项目列表</span></a>') && page.includes('href="/teams/acme/settings" data-route><svg'));
    assert.ok(page.includes('ana@example.com') && page.includes('class="chip">你</span>') && page.includes('Ben &lt;Wu&gt;'));
    assert.ok(page.includes('data-member-role="ben"') && page.includes('data-remove-member="ben"') && page.includes('data-invite-form') && page.includes('data-revoke-invite="inv1"') && page.includes('data-leave-team'));
    assert.ok(page.includes('data-value="viewer" aria-selected="false"') && page.includes('<span>只读成员</span>') && page.includes('class="select role-select"'));

    // A role change is one request; a refusal puts the select back and shows the server's reason.
    calls.length = 0;
    reply = () => ({role: 'viewer'});
    const fakeSelect = (memberRole, value) => {
      const shown = {textContent: ''};
      const options = ['admin', 'member', 'viewer'].map((role) => ({dataset: {value: role}, textContent: role, setAttribute(key, selected) {this[key] = selected;}}));
      const trigger = {disabled: false, querySelector: () => shown};
      const input = {dataset: {memberRole}, value, shown, trigger, closest: () => root};
      const root = {querySelector: (selector) => selector === 'input' ? input : selector === '.select-trigger' ? trigger : {querySelectorAll: () => options}};
      return input;
    };
    await changeMemberRole(fakeSelect('ben', 'viewer'));
    assert.deepEqual(calls.at(-1), {url: '/api/v1/teams/t1/members/ben/role', method: 'POST', body: {role: 'viewer'}});
    assert.equal(el.statusLine.textContent, 'Ben <Wu> 现在是只读成员。');
    const own = fakeSelect('me', 'member');
    reply = () => new ApiRequestError('x', 409, 'LAST_ADMIN', 'Make another member an admin first.');
    await changeMemberRole(own);
    assert.equal(own.value, 'admin');
    assert.equal(own.shown.textContent, 'admin', 'the field shows the role that stayed');
    assert.equal(own.trigger.disabled, false);
    assert.equal(el.statusLine.textContent, '请先把另一位成员设为管理员。');

    // An invite link is built from the page's own origin and shown once, like a new token.
    form = fakeForm({'invite-role': 'viewer'});
    calls.length = 0;
    reply = () => ({invite: {id: 'inv2', role: 'viewer', created_at: iso, expires_at: iso}, path: '/invite?token=ith_inv_SECRET'});
    await createInvite(form);
    assert.deepEqual(calls.at(-1), {url: '/api/v1/teams/t1/invites', method: 'POST', body: {role: 'viewer'}});
    page = el.siteContent.innerHTML;
    assert.ok(page.includes('https://inthub.example/invite?token=ith_inv_SECRET') && page.includes('data-copy-invite') && page.includes('class="secret-box"'));
    assert.ok(page.includes('data-revoke-invite="inv2"'));
    assert.equal(state._newInvite.url, 'https://inthub.example/invite?token=ith_inv_SECRET');
    showTeam('acme', 'projects');
    assert.equal(state._newInvite, null, 'moving to another pane drops it');
    page = el.siteContent.innerHTML;
    assert.ok(!page.includes('ith_inv_SECRET'));
    assert.ok(page.includes('app') && page.includes('href="/?project=p1" data-route') && page.includes('公开'));
    assert.equal(routeUrl(), '/teams/acme/projects');
    showTeam('acme', 'members');
    assert.ok(!el.siteContent.innerHTML.includes('ith_inv_SECRET'));

    const button = document.getElementById('revoke-invite-button');
    button.disabled = false;
    calls.length = 0;
    reply = () => ({revoked: true, id: 'inv1'});
    await revokeInvite('inv1', button);
    assert.deepEqual(calls.at(-1), {url: '/api/v1/teams/t1/invites/inv1/revoke', method: 'POST', body: {}});
    assert.ok(!el.siteContent.innerHTML.includes('data-revoke-invite="inv1"'));

    // Removing asks first and reloads; removing yourself is leaving.
    reply = () => detail();
    confirmRemoveMember('ben');
    assert.equal(el.confirmTitle.textContent, '移除 Ben <Wu>？');
    calls.length = 0;
    await runConfirm();
    assert.equal(calls[0].url, '/api/v1/teams/t1/members/ben/remove');
    assert.equal(el.confirmDialog.open, false);
    confirmRemoveMember('me');
    assert.equal(el.confirmTitle.textContent, '退出 Acme？');

    // Leaving: the last admin gets the server's reason in the dialog, and stays.
    calls.length = 0;
    reply = () => new ApiRequestError('x', 409, 'LAST_ADMIN', 'Make another member an admin first.');
    await runConfirm();
    assert.equal(el.confirmDialog.open, true);
    assert.equal(el.confirmError.textContent, '请先把另一位成员设为管理员。');
    assert.equal(state.page, 'team');
    routes.length = 0;
    reply = (url) => url === '/api/v1/projects' ? {projects: []} : url === '/api/v1/teams' ? {teams: []} : {};
    await runConfirm();
    assert.equal(el.confirmDialog.open, false);
    assert.equal(state.page, 'project', 'the team page is gone: the default view takes over');
    assert.equal(routes[0], 'replace');
    assert.equal(el.statusLine.textContent, '你已退出 Acme。');

    // A member sees the same pages without the controls, and Settings sends them back to Members.
    reply = () => detail('viewer', {members: members().map(({email, ...member}) => ({...member, role: member.id === 'me' ? 'viewer' : member.role}))});
    routes.length = 0;
    await showTeam('acme', 'settings');
    await flush();
    assert.equal(state._team.pane, 'members');
    assert.equal(routes.join(), 'replace');
    page = el.siteContent.innerHTML;
    assert.ok(!page.includes('/teams/acme/settings') && !page.includes('data-member-role') && !page.includes('data-remove-member') && !page.includes('data-invite-form') && !page.includes('ana@example.com'));
    assert.ok(page.includes('data-leave-team') && page.includes('只读成员'));

    // Settings: edit, and delete with the typed URL and the project count.
    state.page = 'project';
    state._team = null;
    reply = () => detail();
    await showTeam('acme', 'settings');
    await flush();
    page = el.siteContent.innerHTML;
    assert.ok(page.includes('data-team-settings-form') && page.includes('value="acme"') && page.includes('删除团队及其 1 个项目。') && page.includes('data-delete-team'));
    form = fakeForm({'team-name': 'Acme 2', 'team-slug': 'acme-2'});
    calls.length = 0;
    routes.length = 0;
    reply = (url, options) => options.method === 'POST' ? {team: {id: 't1', slug: 'acme-2', name: 'Acme 2', created_at: iso}} : {projects: []};
    await saveTeam(form);
    assert.deepEqual(calls[0], {url: '/api/v1/teams/t1', method: 'POST', body: {name: 'Acme 2', slug: 'acme-2'}});
    assert.equal(routeUrl(), '/teams/acme-2/settings');
    assert.equal(routes.join(), 'replace');
    assert.equal(document.title, 'Acme 2 · IntHub');
    assert.ok(el.siteContent.innerHTML.includes('class="page-title settings-title">Acme 2</h1>'));
    confirmDeleteTeam();
    assert.equal(el.confirmTitle.textContent, '删除 Acme 2？');
    assert.ok(el.confirmBody.textContent.includes('1 个项目'));
    assert.ok(el.confirmLabel.innerHTML.includes('acme-2'));
    assert.equal(el.confirmOk.disabled, true);
    el.confirmInput.value = 'acme-2';
    for (const listener of el.confirmInput.events.get('input') || []) listener();
    calls.length = 0;
    reply = (url) => url === '/api/v1/projects' ? {projects: []} : url === '/api/v1/teams' ? {teams: []} : {};
    await runConfirm();
    assert.deepEqual(calls[0], {url: '/api/v1/teams/t1/delete', method: 'POST', body: {confirm: 'acme-2'}});
    assert.equal(state.page, 'project');

    // Teams change on these pages: leaving them drops the lists the project's Settings tab keeps.
    setPage('home');
    state._teams = [{id: 't1', role: 'admin'}];
    state._projectTeam = {id: 't1', data: {members: []}};
    leaveSitePage();
    assert.equal(state._teams, null);
    assert.equal(state._projectTeam, null);

    // A team I am not in answers 404: no team page, but no crash either.
    state.page = 'project';
    state._team = null;
    reply = () => new ApiRequestError('x', 404, 'TEAM_NOT_FOUND');
    await showTeam('other');
    assert.ok(el.siteContent.innerHTML.includes('这个团队不存在，或者你不在其中。'));

    fetchJson = saved.fetchJson;
    setPage('project');
    state.account = null;
    state.projects = [];
  })()`, context);
  console.log('Team list, slug derivation, members, invites, leaving, last-admin refusal and team settings tests passed.');
}

async function homeAndVisitorCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    window.IntHubI18n.setLanguage('zh-CN');
    const saved = {fetchJson, loadProject};
    const calls = [];
    let reply = () => ({});
    fetchJson = async (url, options = {}) => {
      calls.push({url, gate: options.gate});
      const answer = reply(url, options);
      if (answer instanceof Error) throw answer;
      return answer;
    };
    const iso = new Date().toISOString();
    const row = (id, extra = {}) => ({id, name: id, full_name: id, created_at: iso, revision: null, last_synced_at: iso, visibility: 'private', permission: 'admin', team: null, ...extra});
    const overviewOf = (id, permission, extra = {}) => ({
      project: {id, name: id, full_name: 'acme/' + id, created_at: iso, repository_url: null, visibility: 'public', permission, owner: {type: 'team', id: 't1', slug: 'acme', name: 'Acme'}, ...extra},
      history: {project_id: id, revision: 'a'.repeat(64), last_synced_at: iso},
      active_intents: [], other_intents: [], active_decisions: [], deprecated_decisions: [], recent_snaps: [],
    });
    const reset = () => {
      Object.assign(state, {projects: [], currentProjectId: null, _loadedProjectId: null, overview: null, handoff: null, page: 'project', visitor: false, account: null, activeTab: 'overview', _home: null, _homeError: ''});
      el.shell.classList.remove('is-site');
      el.detailContent.innerHTML = '';
      el.siteContent.innerHTML = '';
      el.authGate.classList.add('is-hidden');
      el.shell.inert = false;
      window.location.pathname = '/';
      window.location.search = '';
      calls.length = 0;
      routes.length = 0;
    };
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: '', defaultProjectId: null};
    state.account = {id: 'me', display_name: 'Ana'};
    const settingsTab = document.getElementById('settings-tab');
    const tabQuery = el.tabBar.querySelector;
    el.tabBar.querySelector = (selector) => selector.includes('settings') ? settingsTab : null;

    // / with 2 or more projects: the home page, one list in the server's order, no project opened.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    const homeRows = [
      row('acme-app', {full_name: 'acme/app', active_intents: 2, blocked_intents: 1, visibility: 'public'}),
      row('notes', {active_intents: 0, blocked_intents: 0, last_synced_at: null}),
    ];
    let opened = [];
    loadProject = async (id, options) => { opened.push(id); state.currentProjectId = id; };
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, []);
    assert.equal(state.page, 'home');
    assert.equal(el.shell.classList.contains('is-site'), true);
    assert.equal(document.title, '项目列表 · IntHub');
    assert.equal(routeUrl(), '/');
    let page = el.siteContent.innerHTML;
    assert.ok(page.indexOf('acme/app') < page.indexOf('notes'));
    assert.ok(page.includes('href="/?project=acme-app" data-route') && page.includes('class="page-title">项目列表</h1>'));
    assert.ok(page.includes('2 个进行中') && page.includes('status-dot') && page.includes('1 个被阻塞') && page.includes('公开') && page.includes('私有') && page.includes('刚刚同步') && page.includes('未同步'));
    assert.equal((page.match(/个被阻塞/g) || []).length, 1, 'no zero-blocked pill');

    // The picker: All projects first, then the full names.
    assert.equal(el.projectPickerLabel.textContent, '全部项目');
    let picker = el.projectPickerDropdown.innerHTML;
    assert.ok(picker.indexOf('href="/" data-route') < picker.indexOf('acme/app'));
    assert.ok(picker.includes('aria-selected="true"') && picker.includes('全部项目'));
    assert.equal((picker.match(/role="option"/g) || []).length, 3);
    assert.equal(el.projectPickerTrigger.disabled, false);

    // A default project, one project, none: / opens the project, or the setup guide.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    state.config.defaultProjectId = 'notes';
    opened = [];
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['notes']);
    assert.equal(state.page, 'project');
    assert.ok(!el.projectPickerDropdown.innerHTML.includes('data-route'), 'with a default project there is no home page to link to');
    state.config.defaultProjectId = null;
    reset();
    opened = [];
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows.slice(0, 1)} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['acme-app']);
    assert.equal(state.page, 'project');
    reset();
    reply = () => ({projects: []});
    await loadProjects(readRoute());
    assert.equal(state.page, 'project');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));

    // /account/tokens shipped for a day: it is just / now, and the address follows.
    reset();
    window.location.pathname = '/account/tokens';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.equal(state.page, 'home');
    assert.equal(routes.join(), 'replace');
    assert.equal(routeUrl(), '/');

    // A hidden project is treated as not found, without the gate: / takes over.
    reset();
    window.location.search = '?project=hidden';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : new ApiRequestError('gone', 404, 'PROJECT_NOT_FOUND');
    await loadProjects(readRoute());
    assert.equal(state.page, 'home');
    assert.equal(calls.find((call) => call.url.endsWith('/hidden/overview')).gate, false);
    assert.equal(el.statusLine.textContent, '这个项目不存在，或者你无权查看。');

    // A signed-in non-member keeps the public project open, as a passing entry, with no Settings tab.
    reset();
    loadProject = saved.loadProject;
    state.account = {id: 'me', display_name: 'Ana'};
    window.location.search = '?project=pub';
    const publicOverview = overviewOf('pub', 'public');
    const handoff = {intents: []};
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url.endsWith('/overview') ? publicOverview : url.endsWith('/handoff') ? handoff : {};
    state.activeTab = 'settings';
    await loadProjects(readRoute());
    assert.equal(state.currentProjectId, 'pub');
    assert.equal(state.page, 'project');
    assert.equal(state.activeTab, 'overview', 'Settings is not reachable by URL either');
    assert.deepEqual(state.projects.map((project) => [project.id, Boolean(project.transient)].join()), ['acme-app,false', 'notes,false', 'pub,true']);
    assert.equal(el.projectPickerLabel.textContent, 'acme/pub');
    assert.equal(canManageProject(), false);
    assert.equal(settingsTab.classList.contains('is-hidden'), true);
    assert.equal(hasHomePage(), true, 'a passing entry does not count as one of my projects');
    assert.ok(el.detailContent.innerHTML.includes('Acme') && !el.detailContent.innerHTML.includes('href="/teams/acme"'), 'a non-member gets no link to the team');
    assert.ok(el.detailContent.innerHTML.includes('visibility-pill'));
    // Moving on drops it.
    reply = (url) => url.endsWith('/overview') ? overviewOf('acme-app', 'admin', {visibility: 'private'}) : url.endsWith('/handoff') ? handoff : {};
    await loadProject('acme-app');
    assert.deepEqual(state.projects.map((project) => project.id), ['acme-app', 'notes']);
    assert.equal(canManageProject(), true);
    assert.equal(settingsTab.classList.contains('is-hidden'), false);
    assert.ok(el.detailContent.innerHTML.includes('href="/teams/acme" data-route'), 'a member can follow the owner to the team');

    // A visitor: /api/v1/auth/me says 401 quietly, and the overview answers. No project list, no tokens, no gate.
    reset();
    loadProject = saved.loadProject;
    window.location.search = '?project=pub';
    window.history.replaceState = window.history.replaceState;
    globalThis.fetch = async () => ({ok: true, json: async () => ({...state.config})});
    const authRequired = new ApiRequestError('Sign in', 401, 'AUTH_REQUIRED');
    reply = (url) => url === '/api/v1/auth/me' ? authRequired : url.endsWith('/overview') ? publicOverview : url.endsWith('/handoff') ? handoff : new Error('unexpected ' + url);
    await init(false);
    assert.equal(state.visitor, true);
    assert.equal(el.authGate.classList.contains('is-hidden'), true);
    assert.deepEqual(calls.map((call) => call.url), ['/api/v1/auth/me', '/api/v1/projects/pub/overview', '/api/v1/projects/pub/overview', '/api/v1/projects/pub/handoff']);
    assert.equal(calls[0].gate, false);
    assert.equal(calls[1].gate, false);
    assert.equal(el.accountControl.classList.contains('is-hidden'), true);
    assert.equal(el.signInButton.classList.contains('is-hidden'), false);
    assert.equal(el.projectPickerTrigger.disabled, true);
    assert.equal(el.projectPicker.classList.contains('is-static'), true);
    assert.equal(el.projectPickerLabel.textContent, 'acme/pub');
    assert.equal(canManageProject(), false);
    assert.equal(hasHomePage(), false);
    assert.equal(settingsTab.classList.contains('is-hidden'), true);

    // Sign in opens the gate over the project, keeping it; Back returns to it.
    el.signInButton.events.get('click')[0]();
    assert.equal(el.authGate.classList.contains('is-hidden'), false);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), false);
    assert.equal(state.visitor, true);
    assert.notEqual(el.detailContent.innerHTML, '');
    assert.equal(el.shell.inert, true);
    el.authDismiss.events.get('click')[0]();
    assert.equal(el.authGate.classList.contains('is-hidden'), true);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), true);
    assert.equal(el.shell.inert, false);
    assert.equal(document.activeElement, el.signInButton);

    // Refresh reloads the project and leaves the project list alone.
    calls.length = 0;
    await el.refreshBtn.events.get('click')[0]();
    assert.ok(!calls.some((call) => call.url === '/api/v1/projects'));
    assert.ok(calls.some((call) => call.url === '/api/v1/projects/pub/overview'));

    // An empty public project says so; nobody is told to run the CLI.
    const emptyOverview = {...publicOverview, history: {project_id: 'pub', revision: null}};
    reply = (url) => url.endsWith('/overview') ? emptyOverview : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('这个项目还没有发布任何内容。'));
    assert.ok(!el.detailContent.innerHTML.includes('setup-guide') && !el.detailContent.innerHTML.includes('itt push'));
    assert.equal(el.shell.classList.contains('is-empty'), true);

    // Whoever manages an empty project still reaches its Settings: the guide links there, and the way back works.
    reset();
    state.currentProjectId = 'pub';
    state.projects = [row('pub'), row('other')];
    const managedEmpty = {...overviewOf('pub', 'admin'), history: {project_id: 'pub', revision: null}};
    reply = (url) => url.endsWith('/overview') ? managedEmpty : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));
    assert.ok(el.detailContent.innerHTML.includes('href="/?project=pub&amp;tab=settings" data-route'));
    switchTab('settings');
    assert.equal(el.shell.classList.contains('is-empty'), false);
    assert.ok(el.detailContent.innerHTML.includes('settings-layout') && el.detailContent.innerHTML.includes('data-rename-form'));
    switchTab('overview');
    assert.equal(el.shell.classList.contains('is-empty'), true);
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));
    state.activeTab = 'settings';
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('settings-layout'), 'the URL can name it too');
    state.activeTab = 'overview';
    reply = (url) => url.endsWith('/overview') ? {...managedEmpty, project: {...managedEmpty.project, permission: 'write'}} : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide') && !el.detailContent.innerHTML.includes('tab=settings'), 'a member pushes; only an admin manages');

    // Without a public project the gate takes over, as it did.
    reset();
    window.location.search = '?project=secret';
    reply = (url) => authRequired;
    await init(false);
    assert.equal(state.visitor, false);
    assert.equal(el.authGate.classList.contains('is-hidden'), false);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), true);
    const loginLink = document.getElementById('login-link');
    loginLink.dataset.loginMethod = 'github';
    loginLink.querySelector = () => document.getElementById('login-link-part');
    el.tenonLogin.querySelectorAll = () => [loginLink];
    for (const [pathname, search, returnTo] of [['/settings', '', '%2Fsettings'], ['/invite', '?token=abc', '%2Finvite%3Ftoken%3Dabc']]) {
      reset();
      window.location.pathname = pathname;
      window.location.search = search;
      reply = (url) => authRequired;
      await init(false);
      assert.equal(el.authGate.classList.contains('is-hidden'), false);
      assert.deepEqual(calls.map((call) => call.url), ['/api/v1/auth/me']);
      assert.equal(loginLink.href, '/auth/redirect?method=github&return_to=' + returnTo);
    }
    el.tenonLogin.querySelectorAll = () => [];

    // Site pages on a Tenon hub load the list but no project; on a local hub those paths are project routes.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    opened = [];
    loadProject = async (id) => { opened.push(id); };
    window.location.pathname = '/account';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, []);
    assert.equal(state.currentProjectId, null);
    assert.equal(el.projectPickerLabel.textContent, '全部项目');
    state.config = {authRequired: false, authMode: 'none', apiBaseUrl: '', defaultProjectId: null};
    reset();
    window.location.pathname = '/account';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows.slice(0, 1)} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['acme-app']);
    assert.equal(state.page, 'project');

    // Back and forward reach the same pages.
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: '', defaultProjectId: null};
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    state.projects = homeRows;
    reply = (url) => url === '/api/v1/home' ? {projects: homeRows} : url === '/api/v1/teams/acme' ? {team: {id: 't1', slug: 'acme', name: 'Acme'}, role: 'member', members: [], invites: [], projects: []} : {tokens: [], teams: []};
    window.location.pathname = '/settings/teams';
    await applyRoute(readRoute());
    assert.equal(state._dialog, 'settings');
    assert.equal(state._pane, 'teams');
    window.location.pathname = '/teams/acme';
    await applyRoute(readRoute());
    assert.equal(state._dialog, null, 'leaving for a page closes the dialog');
    assert.equal(el.settingsDialog.open, false);
    assert.equal(state.page, 'team');
    window.location.pathname = '/';
    await applyRoute(readRoute());
    assert.equal(state.page, 'home');
    opened = [];
    window.location.search = '?project=notes';
    await applyRoute(readRoute());
    assert.equal(state.page, 'project');
    assert.deepEqual(opened, ['notes']);

    fetchJson = saved.fetchJson;
    loadProject = saved.loadProject;
    el.tabBar.querySelector = tabQuery;
    delete globalThis.fetch;
    reset();
    state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};
  })()`, context);
  console.log('Home page, picker, passing public projects, visitor mode, gate fallbacks and route dispatch tests passed.');
}

async function inviteCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    window.IntHubI18n.setLanguage('zh-CN');
    const saved = {fetchJson};
    const calls = [];
    let reply = () => ({});
    fetchJson = async (url, options = {}) => {
      calls.push({url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null});
      const answer = reply(url, options);
      if (answer instanceof Error) throw answer;
      return answer;
    };
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: '', defaultProjectId: null};
    state.account = {id: 'me', display_name: 'Ana'};
    state.projects = [];
    state.page = 'project';
    window.location.pathname = '/invite';
    window.location.search = '?token=ith_inv_abc';
    const team = {id: 't1', slug: 'acme', name: 'Acme <Inc>'};

    reply = () => ({team, role: 'viewer', invited_by: 'Ben', expires_at: '2026-11-06T00:00:00Z', already_member: false});
    await applyRoute(readRoute());
    assert.equal(calls[0].url, '/api/v1/invites/preview?token=ith_inv_abc');
    assert.equal(document.title, '团队邀请 · IntHub');
    assert.equal(el.shell.classList.contains('is-site'), true);
    let page = el.siteContent.innerHTML;
    assert.ok(page.includes('Ben 邀请你以只读成员身份加入 Acme &lt;Inc&gt;。') && !page.includes('Acme <Inc>'));
    assert.ok(page.includes('data-accept-invite') && page.includes('暂不加入') && page.includes('href="/" data-route'));

    // Accept goes to the team and leaves no token behind, in the address or in the history.
    const button = document.getElementById('accept-invite-button');
    button.disabled = false;
    routes.length = 0;
    calls.length = 0;
    reply = (url, options) => url === '/api/v1/invites/accept' ? {team, role: 'viewer', joined: true}
      : url === '/api/v1/projects' ? {projects: []} : {team, role: 'viewer', members: [], invites: [], projects: []};
    await acceptInvite(button);
    await flush();
    assert.deepEqual(calls[0], {url: '/api/v1/invites/accept', method: 'POST', body: {token: 'ith_inv_abc'}});
    assert.equal(routes[0], 'replace');
    assert.ok(!routes.includes('push'));
    assert.equal(state.page, 'team');
    assert.equal(routeUrl(), '/teams/acme');
    assert.equal(el.statusLine.textContent, '你已加入 Acme <Inc>。');

    // Already a member: no Accept, a link to the team instead.
    state.page = 'project';
    reply = () => ({team, role: 'viewer', invited_by: 'Ben', expires_at: '2026-11-06T00:00:00Z', already_member: true});
    await showInvite('ith_inv_abc');
    page = el.siteContent.innerHTML;
    assert.ok(page.includes('你已经在这个团队中。') && page.includes('href="/teams/acme" data-route') && !page.includes('data-accept-invite'));

    // Expired, revoked, used or missing: one message and a way on.
    reply = () => new ApiRequestError('x', 410, 'INVITE_INVALID', 'This invite link is no longer valid.');
    await showInvite('ith_inv_old');
    page = el.siteContent.innerHTML;
    assert.ok(page.includes('这个邀请链接已失效。') && !page.includes('data-accept-invite') && page.includes('前往 IntHub'));
    calls.length = 0;
    await showInvite('');
    assert.equal(calls.length, 0, 'no token, nothing to ask');
    assert.ok(el.siteContent.innerHTML.includes('这个邀请链接已失效。'));

    // The link can die between the preview and the click.
    reply = () => ({team, role: 'member', invited_by: null, expires_at: '2026-11-06T00:00:00Z', already_member: false});
    await showInvite('ith_inv_abc');
    assert.ok(el.siteContent.innerHTML.includes('你受邀以成员身份加入 Acme &lt;Inc&gt;。'));
    button.disabled = false;
    reply = () => new ApiRequestError('x', 410, 'INVITE_INVALID', 'This invite link is no longer valid.');
    await acceptInvite(button);
    assert.ok(el.siteContent.innerHTML.includes('这个邀请链接已失效。'));

    fetchJson = saved.fetchJson;
    setPage('project');
    state.account = null;
    window.location.pathname = '/';
    window.location.search = '';
  })()`, context);
  console.log('Invite page preview, accept, already-member and invalid-link tests passed.');
}

async function historyCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    const saved = {fetchJson};
    const calls = [];
    let reply = () => ({});
    fetchJson = async (url, options = {}) => { calls.push(url); return reply(url, options); };
    window.location.pathname = '/';
    window.location.search = '';
    state.page = 'project';
    state.config = {authRequired: false, authMode: 'none', apiBaseUrl: ''};
    state.projects = [{id: 'p', name: 'checkout', full_name: 'checkout'}];
    state.currentProjectId = 'p';
    state._loadedProjectId = 'p';
    const hash = (mark) => mark.repeat(64);

    // One sentence per revision, in both languages, with the counts the server keeps exact.
    window.IntHubI18n.setLanguage('en');
    assert.equal(revisionSummary({intents_added: 2, snaps_added: 5, decisions_changed: 1}), 'Added 2 Intents and 5 Snaps; changed 1 Decision');
    assert.equal(revisionSummary({intents_added: 1, snaps_added: 1, decisions_added: 2}), 'Added 1 Intent, 1 Snap and 2 Decisions');
    assert.equal(revisionSummary({intents_changed: 2, snaps_changed: 0}), 'Changed 2 Intents');
    assert.equal(revisionSummary({intents_added: 0, intents_changed: 0, snaps_added: 0, snaps_changed: 0, decisions_added: 0, decisions_changed: 0}), 'No semantic changes');
    window.IntHubI18n.setLanguage('zh-CN');
    assert.equal(revisionSummary({intents_added: 2, snaps_added: 5, decisions_changed: 1}), '新增 2 个意图、5 个 Snap，变更 1 个决策');
    assert.equal(revisionSummary({}), '没有语义变化');

    // Who pushed: the account first, then what the CLI declared; nobody means no name at all.
    const account = {login: 'ana', name: 'Ana Lee'};
    const declared = {name: 'Ana', email: 'ana@example.com'};
    assert.equal(pushedBy({pushed_by: account, pusher: declared}), 'Ana Lee');
    assert.equal(pushedBy({pushed_by: {login: 'ana', name: null}, pusher: declared}), 'ana');
    assert.equal(pushedBy({pushed_by: null, pusher: declared}), 'Ana');
    assert.equal(pushedBy({pushed_by: null, pusher: {email: 'ana@example.com'}}), 'ana@example.com');
    assert.equal(pushedBy({pushed_by: null, pusher: null}), '');

    // The list: grouped by day, First push on the first revision, paged with Load more.
    state.overview = {history: {project_id: 'p', revision: hash('a'), last_synced_at: '2026-10-20T10:00:00Z'}, project: {id: 'p', name: 'checkout'}, authors: [], active_intents: [], other_intents: []};
    state.activeTab = 'history';
    state._history = null;
    const revision = (mark, day, parent, summary, extra = {}) => ({revision: hash(mark), parent, created_at: '2026-10-' + day + 'T10:00:00Z', pushed_by: null, pusher: {name: 'Bo Chen'}, summary, ...extra});
    reply = (url) => url.includes('offset=0')
      ? {revisions: [revision('c', '20', hash('b'), {snaps_added: 1}), revision('b', '20', hash('a'), {}, {pusher: null})], total: 3, has_more: true}
      : {revisions: [revision('a', '18', null, {intents_added: 1}, {pushed_by: account})], total: 3, has_more: false};
    calls.length = 0;
    renderView();
    assert.ok(el.detailContent.innerHTML.includes('view-loading'));
    await flush();
    assert.equal(calls[0], '/api/v1/projects/p/revisions?offset=0&limit=30');
    let page = el.detailContent.innerHTML;
    assert.equal(page.split('class="history-group"').length - 1, 1);
    assert.ok(page.includes('新增 1 个 Snap') && page.includes('没有语义变化') && page.includes('Bo Chen'));
    assert.ok(page.includes('data-detail-type="revision" data-remote-id="p__' + hash('c') + '"'));
    assert.ok(page.includes('<span class="row-id">' + hash('c').slice(0, 8) + '</span>'));
    assert.ok(page.includes('id="load-more-history"') && page.includes('加载更多（1）'));
    assert.ok(!page.includes('首次推送'));
    await loadHistoryPage();
    page = el.detailContent.innerHTML;
    assert.equal(calls.at(-1), '/api/v1/projects/p/revisions?offset=2&limit=30');
    assert.equal(page.split('class="history-group"').length - 1, 2);
    assert.ok(page.includes('首次推送') && page.includes('Ana Lee') && page.includes('3 次推送'));
    assert.ok(!page.includes('load-more-history'));

    // Nothing pushed: the empty state says how; a failed page offers a retry.
    reply = () => ({revisions: [], total: 0, has_more: false});
    state._history = null;
    renderView();
    await flush();
    assert.ok(el.detailContent.innerHTML.includes('还没有推送。') && el.detailContent.innerHTML.includes('<pre class="command-snippet">itt push</pre>'));
    reply = () => { throw new ApiRequestError('无法加载', 500, 'BROKEN'); };
    state._history = null;
    renderView();
    await flush();
    assert.ok(el.detailContent.innerHTML.includes('无法加载') && el.detailContent.innerHTML.includes('data-retry-history'));

    // A revision opens in the sheet, deep-linkable, with its objects and changes.
    const ana = {name: 'Ana Lee', email: 'ana@example.com'};
    const detail = {
      project_id: 'p', revision: hash('c'), parent: hash('b'), created_at: '2026-10-20T10:00:00Z', pushed_by: null, pusher: {name: 'Bo Chen'},
      summary: {intents_added: 1, snaps_added: 203, decisions_added: 0, intents_changed: 2, snaps_changed: 0, decisions_changed: 1},
      changes: {
        intents: {added: [{id: 'intent-007', what: 'New <goal>', status: 'active', author: ana, origin: 'claude-code'}], changed: [
          {object: {id: 'intent-005', what: 'Old goal', status: 'cancelled'}, changes: [{field: 'status', from: 'active', to: 'cancelled', reason: 'Provider changed'}]},
          {object: {id: 'intent-006', what: 'Rollout', status: 'active'}, changes: [{field: 'relation', action: 'removed', type: 'depends_on', intent: 'intent-004'}, {field: 'relation', action: 'added', type: 'part_of', intent: 'intent-001'}]},
        ], truncated: false},
        snaps: {added: Array.from({length: 200}, (_, index) => ({id: 'snap-' + index, what: 'Step ' + index, intent_id: 'intent-001'})), changed: [], truncated: true},
        decisions: {added: [], changed: [{object: {id: 'decision-003', what: 'Rule', status: 'deprecated'}, changes: [{field: 'status', from: 'active', to: 'deprecated'}]}], truncated: false},
      },
    };
    reply = () => detail;
    calls.length = 0;
    state._detailCache = new Map();
    await openDetail('revision', 'p__' + hash('c'));
    assert.equal(calls[0], '/api/v1/projects/p/revisions/' + hash('c'));
    assert.ok(el.drawerTitle.innerHTML.includes('修订') && el.drawerTitle.innerHTML.includes(hash('c').slice(0, 8)) && !el.drawerTitle.innerHTML.includes(hash('c')));
    assert.ok(routeUrl().includes('detail=p__' + hash('c')) && routeUrl().includes('detailType=revision'));
    let sheet = el.drawerContent.innerHTML;
    assert.ok(sheet.includes('由 Bo Chen 推送'));
    assert.ok(sheet.includes('新增 1 个意图、203 个 Snap，变更 2 个意图、1 个决策'));
    assert.ok(sheet.indexOf('新增的意图') < sheet.indexOf('新增的 Snap') && sheet.indexOf('新增的 Snap') < sheet.indexOf('>变更<'));
    assert.ok(!sheet.includes('新增的决策'), 'a list with nothing in it has no section');
    assert.ok(sheet.includes('New &lt;goal&gt;') && !sheet.includes('New <goal>'));
    assert.ok(sheet.includes('data-detail-type="intent" data-remote-id="p__intent-007"') && sheet.includes('Ana Lee · Claude Code'));
    assert.ok(sheet.includes('进行中 → 已取消') && sheet.includes('Provider changed'));
    assert.ok(sheet.includes('有效 → 已废弃'), 'Decisions use their own status words');
    assert.ok(sheet.includes('移除关系：依赖 ') && sheet.includes('新增关系：属于 '));
    assert.ok(sheet.includes('data-detail-type="intent" data-remote-id="p__intent-004"'));
    assert.ok(sheet.includes('另有 3 个未显示'), 'the summary stays exact when a list is cut');
    closeDrawer({history: 'none'});
    assert.ok(buildRevisionDetailHtml({...detail, parent: null}).includes('首次推送'));
    const empty = buildRevisionDetailHtml({...detail, summary: {}, changes: {}});
    assert.ok(empty.includes('这次推送没有新增或变更任何内容。') && empty.includes('没有语义变化'));

    // Authors and agents: the name, then the email; no author keeps the agent alone.
    assert.equal(byline({author: ana, origin: 'claude-code'}), 'Ana Lee · Claude Code');
    assert.equal(byline({author: {email: 'bo@example.com'}, origin: 'codex'}), 'bo@example.com · Codex');
    assert.equal(byline({origin: 'claude-code'}), 'Claude Code');
    assert.equal(byline({origin: 'some-tool'}), 'some-tool');
    assert.equal(byline({}), '');
    assert.equal(rowByline({}), '');
    assert.ok(rowByline({author: ana, origin: 'codex', verified: true}).includes('Ana Lee · Codex') && rowByline({author: ana, verified: true}).includes('status-verified'));
    assert.ok(!rowByline({author: ana}).includes('status-verified'), 'unverified objects get no label');
    assert.ok(verifiedBadge({verified: true}).includes('已验证') && verifiedBadge({verified: true}).includes('由拥有此邮箱的账号推送。'));
    const meta = identityMeta({author: ana, origin: 'claude-code', verified: true});
    assert.ok(meta.includes('ana@example.com') && meta.includes('data-help="verified"'));
    assert.ok(!identityMeta({author: {email: 'bo@example.com'}}).includes('detail-email'), 'an email already standing in for the name is not repeated');
    const snap = {id: 'snap-001', what: 'Done', created_at: '2026-10-20T10:00:00Z', intent_id: 'intent-001', author: ana, origin: 'codex', verified: true, remote_id: 'p__snap-001'};
    assert.ok(snapTimelineEntry(snap).includes('Ana Lee · Codex') && snapTimelineEntry(snap).includes('status-verified'));
    assert.ok(intentEntry({id: 'intent-001', remote_id: 'p__intent-001', status: 'active', what: 'Goal', author: ana, origin: 'codex', snap_ids: [], decision_ids: []}).includes('Ana Lee · Codex'));
    assert.ok(decisionConstraint({id: 'decision-001', remote_id: 'p__decision-001', status: 'active', what: 'Rule', author: ana, origin: 'codex', intent_ids: []}, 0).includes('Ana Lee · Codex'));
    assert.ok(continuationCard({id: 'intent-001', remote_id: 'p__intent-001', project_id: 'p', status: 'active', what: 'Goal', latest_snap: snap}).includes('Ana Lee · Codex'));

    // The commit a Snap was recorded on.
    const sha = '1a2b3c4'.padEnd(40, '0');
    assert.equal(commitUrl('https://github.com/acme/app', sha), 'https://github.com/acme/app/commit/' + sha);
    assert.equal(commitUrl('https://gitee.com/acme/app', sha), 'https://gitee.com/acme/app/commit/' + sha);
    assert.equal(commitUrl('https://gitlab.com/acme/tools/app', sha), 'https://gitlab.com/acme/tools/app/-/commit/' + sha);
    for (const unsafe of ['http://github.com/acme/app', 'javascript:alert(1)', 'https://evil.example/acme/app', '', null]) assert.equal(commitUrl(unsafe, sha), '');
    assert.equal(commitUrl('https://github.com/acme/app', 'not-a-sha'), '');
    state.overview.project.repository_url = 'https://github.com/acme/app';
    const linked = commitLine({git: {commit: sha, dirty: true}});
    assert.ok(linked.includes('href="https://github.com/acme/app/commit/' + sha + '"') && linked.includes('target="_blank"') && linked.includes('rel="noopener noreferrer"'));
    assert.ok(linked.includes('提交 <span class="mono">1a2b3c4</span>') && linked.includes('含未提交的修改'));
    state.overview.project.repository_url = null;
    const plainCommit = commitLine({git: {commit: sha}});
    assert.ok(plainCommit.includes('提交 <span class="mono">1a2b3c4</span>') && !plainCommit.includes('<a ') && !plainCommit.includes('含未提交的修改'));
    assert.equal(commitLine({}), '');

    // The author filter: only with two authors, alongside the Intent filter, and in the URL.
    const intents = [{id: 'intent-001', project_id: 'p', what: 'Goal', status: 'active', snap_ids: ['snap-001'], decision_ids: []}];
    state.overview = {...state.overview, active_intents: intents, other_intents: [], total_snaps: 3, recent_snaps: [],
      authors: [{key: 'ana@example.com', name: 'Ana Lee', snaps: 2}]};
    state.activeTab = 'snaps';
    reply = () => ({snaps: [], total: 0, has_more: false});
    resetTimeline('', 'ana@example.com');
    routes.length = 0;
    renderView();
    await flush();
    assert.equal(state._timeline.author, '', 'a filter nothing can clear is dropped');
    assert.ok(!el.detailContent.innerHTML.includes('author-filter'));
    state.overview.authors = [{key: 'ana@example.com', name: 'Ana Lee', snaps: 2}, {key: 'bo@example.com', name: 'Bo Chen', snaps: 1}];
    resetTimeline('intent-001', '');
    renderView();
    await flush();
    let timeline = el.detailContent.innerHTML;
    assert.ok(timeline.includes('author-filter') && timeline.includes('全部作者') && timeline.includes('data-timeline-author="bo@example.com"'));
    assert.ok(timeline.indexOf('data-timeline-intent') < timeline.indexOf('author-filter'), 'beside the Intent filter, after it');
    assert.ok(timeline.includes('没有符合筛选条件的检查点。'));
    calls.length = 0;
    routes.length = 0;
    setTimelineFilter({author: 'bo@example.com'}, '.author-filter .timeline-filter-trigger');
    await flush();
    assert.equal(calls[0], '/api/v1/projects/p/snaps?offset=0&limit=50&intent_id=intent-001&author=bo%40example.com');
    assert.equal(routes.join(), 'push');
    assert.equal(routeUrl(), '/?project=p&tab=snaps&intent=intent-001&author=bo%40example.com');
    window.location.search = '?project=p&tab=snaps&intent=intent-001';
    assert.deepEqual([readRoute().intent, readRoute().author], ['intent-001', '']);
    await applyRoute(readRoute());
    await flush();
    assert.equal(state._timeline.author, '', 'back restores the filters');
    assert.equal(state._timeline.intentId, 'intent-001');
    window.location.search = '?project=p&tab=snaps&author=bo%40example.com';
    assert.deepEqual({...routedTimelineFilters('p')}, {intentId: '', author: 'bo@example.com'});
    assert.deepEqual({...routedTimelineFilters('q')}, {intentId: '', author: ''}, 'a link only filters its own project');
    window.location.search = '';

    // The profile says which email links Snaps to the account.
    const linkedAccount = profileIdentityHtml({email: 'ana@example.com'});
    assert.ok(linkedAccount.includes('ana@example.com') && linkedAccount.includes('data-copy="git config --global user.email ana@example.com"'));
    assert.ok(profileIdentityHtml({email: "o'brien x@example.com"}).includes('data-copy="git config --global user.email &#39;o&#39;\\\\&#39;&#39;brien x@example.com&#39;"'));
    const unlinked = profileIdentityHtml({email: null});
    assert.ok(unlinked.includes('请重新登录，把 Snap 关联到此账号。') && !unlinked.includes('git config'));

    fetchJson = saved.fetchJson;
    state.activeTab = 'overview';
    state._history = null;
  })()`, context);
  console.log('History list and revision sheet, authors and verified marks, commit links, author filter and profile identity tests passed.');
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
  await flowAndPagingCases();
  await settingsCases();
  await teamCases();
  await homeAndVisitorCases();
  await inviteCases();
  await historyCases();
  await redirectCase('https://account.tenon.asia/api/auth/oauth2/authorize?state=fresh');
  await redirectCase('https://evil.example/authorize');
  await redirectCase('', true);
  console.log('Fixed transition destination, timeout, retry and safe return tests passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
