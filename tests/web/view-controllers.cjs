const {assert, context, fs, path, root, vm} = require('./harness.cjs');

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

module.exports = viewControllerCases;
