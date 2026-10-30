const {assert, context, fs, path, root, vm} = require('./harness.cjs');

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

module.exports = teamCases;
