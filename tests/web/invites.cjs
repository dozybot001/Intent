const {assert, context, fs, path, root, vm} = require('./harness.cjs');

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

module.exports = inviteCases;
