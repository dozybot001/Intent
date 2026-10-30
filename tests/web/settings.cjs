const {assert, context, fs, path, root, vm} = require('./harness.cjs');

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
    assert.ok(page.includes('id="token-lifetime" type="button" role="combobox" aria-haspopup="listbox" aria-expanded="false" aria-controls="token-lifetime-options"'));
    assert.ok(page.includes('for="token-lifetime"'));
    assert.ok(page.includes('<span class="select-value">90 天</span>') && page.includes('id="token-lifetime-options" role="listbox" popover="manual"'));
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

module.exports = settingsCases;
