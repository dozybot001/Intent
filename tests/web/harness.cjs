// Pure copy/render/controller tests. No browser, screenshot or visual validation.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const root = path.join(__dirname, '../../apps/inthub_web/static');
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
const appFiles = fs.readFileSync(path.join(root, 'js/order.txt'), 'utf8').split('\n').filter(Boolean).map((name) => `js/${name}`);
const app = appFiles.map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
vm.runInContext(app.replace(/init\(\);\s*$/, ''), context);
const zh = context.window.IntHubI18n.zh;
for (const file of [...appFiles, 'help.js']) {
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

module.exports = {assert, context, fs, path, root, vm};
