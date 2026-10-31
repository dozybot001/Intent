const {assert, context, fs, path, root, vm} = require('./harness.cjs');

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

    // The list: grouped by day, First revision on the first one, paged with Load more.
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
    assert.ok(!page.includes('首条修订'));
    await loadHistoryPage();
    page = el.detailContent.innerHTML;
    assert.equal(calls.at(-1), '/api/v1/projects/p/revisions?offset=2&limit=30');
    assert.equal(page.split('class="history-group"').length - 1, 2);
    assert.ok(page.includes('首条修订') && page.includes('Ana Lee') && page.includes('3 条修订'));
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
    assert.ok(sheet.includes('来自 Bo Chen'));
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
    assert.ok(buildRevisionDetailHtml({...detail, parent: null}).includes('首条修订'));
    const merged = buildRevisionDetailHtml({...detail, merge: true, title: 'Merged origin/main into main'});
    assert.ok(merged.includes('Merged origin/main into main') && merged.includes('合并'));
    const empty = buildRevisionDetailHtml({...detail, summary: {}, changes: {}});
    assert.ok(empty.includes('这条修订没有新增或变更任何内容。') && empty.includes('没有语义变化'));

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

module.exports = historyCases;
