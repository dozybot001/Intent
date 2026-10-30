const { t } = window.IntHubI18n;
window.IntHubI18n.bindStatic(document.body);

/* ---- State ---- */

const TABS = ["overview", "intents", "flow", "snaps", "history", "decisions", "settings"];
const DETAIL_PATHS = { intent: "intents", decision: "decisions", snap: "snaps", revision: "revisions" };
const PAGE_SIZE = 30;
// One timeline page from /projects/{id}/snaps; the overview only carries the newest Snaps.
const SNAP_PAGE_SIZE = 50;
const REVISION_PAGE_SIZE = 30;
// Agents by name; any other label stays as the CLI recorded it.
const ORIGIN_NAMES = {
  "claude-code": "Claude Code", codex: "Codex", cursor: "Cursor", vscode: "VS Code",
  codespaces: "Codespaces", "github-actions": "GitHub Actions", gitpod: "Gitpod",
};
const INSTALL_COMMAND = "curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash";
// Two agents by default: --all would create dozens of agent folders in the home directory.
const SKILL_COMMAND = "npx skills add dozybot001/Intent -g -a claude-code -a codex -y";
// The CLI's default endpoint: there `itt auth login` needs no URL and a push names the project after its directory.
const HOSTED_INTHUB = "https://inthub.tenon.asia";
// Account and Settings open in a dialog over the current page, and team pages have paths of their own;
// project views stay on / with query parameters.
const ACCOUNT_PATHS = { profile: "/account", danger: "/account/danger" };
const SETTINGS_PATHS = { tokens: "/settings", teams: "/settings/teams", usage: "/settings/usage" };
const DIALOG_PATHS = { account: ACCOUNT_PATHS, settings: SETTINGS_PATHS };
const TENON_ACCOUNT_URL = "https://account.tenon.asia/account/";
const SUPPORT_EMAIL = "support@tenonai.cn";
// Lifetimes the token form offers, in days.
const TOKEN_LIFETIMES = [30, 90, 365];
const DEFAULT_TOKEN_DAYS = 90;
// The hub's rule for project names (intent_cli.hub.versions.validate_project_name), checked while typing.
const PROJECT_NAME_MAX = 120;
const JSON_HEADERS = { "Content-Type": "application/json" };
// The hub's rule for team URLs (intent_cli.hub.versions.TEAM_SLUG), checked while typing.
const TEAM_SLUG = /^[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?$/;
const TEAM_ROLES = ["admin", "member", "viewer"];

const state = {
  config: null,
  projects: [],
  currentProjectId: null,
  activeTab: "overview",
  selectedDetail: null,
  searchQuery: "",
  overview: null,
  handoff: null,
  authenticated: false,
  account: null,
  // "project" shows the tabs; "home", "team", "invite" and "device" render beside the untouched project view.
  page: "project",
  // A visitor reads one public project on a hosted hub, without an account.
  visitor: false,
};

const el = {
  shell: document.getElementById("shell"),
  projectPicker: document.getElementById("project-picker"),
  projectPickerTrigger: document.getElementById("project-picker-trigger"),
  projectPickerLabel: document.getElementById("project-picker-label"),
  projectPickerEyebrow: document.getElementById("project-picker-eyebrow"),
  projectPickerDropdown: document.getElementById("project-picker-dropdown"),
  refreshBtn: document.getElementById("refresh-btn"),
  searchTrigger: document.getElementById("search-trigger"),
  searchDialog: document.getElementById("search-dialog"),
  searchForm: document.getElementById("search-form"),
  searchInput: document.getElementById("search-input"),
  searchResults: document.getElementById("search-results"),
  searchStatus: document.getElementById("search-status"),
  syncChip: document.getElementById("sync-chip"),
  syncIndicator: document.getElementById("sync-indicator"),
  tabBar: document.getElementById("tab-bar"),
  detailPane: document.getElementById("detail-pane"),
  detailContent: document.getElementById("detail-content"),
  siteContent: document.getElementById("site-content"),
  skipLink: document.querySelector(".skip-link"),
  statusLine: document.getElementById("status-line"),
  siteFooter: document.getElementById("site-footer"),
  reportLink: document.getElementById("report-link"),
  authPitch: document.getElementById("auth-pitch"),
  authStart: document.getElementById("auth-start"),
  settingsDialog: document.getElementById("settings-dialog"),
  settingsDialogTitle: document.getElementById("settings-dialog-title"),
  settingsDialogBody: document.getElementById("settings-dialog-body"),
  settingsDialogClose: document.getElementById("settings-dialog-close"),
  intentCount: document.getElementById("intent-count"),
  decisionCount: document.getElementById("decision-count"),
  snapCount: document.getElementById("snap-count"),
  drawer: document.getElementById("drawer"),
  drawerOverlay: document.getElementById("drawer-overlay"),
  drawerClose: document.getElementById("drawer-close"),
  drawerBack: document.getElementById("drawer-back"),
  drawerTitle: document.getElementById("drawer-title"),
  drawerContent: document.getElementById("drawer-content"),
  logoutBtn: document.getElementById("logout-btn"),
  signInButton: document.getElementById("sign-in-button"),
  accountControl: document.getElementById("account-control"),
  accountLabel: document.getElementById("account-label"),
  accountMode: document.getElementById("account-mode"),
  accountMenuTrigger: document.getElementById("account-menu-trigger"),
  accountActions: document.getElementById("account-actions"),
  settingsLink: document.getElementById("settings-link"),
  authGate: document.getElementById("auth-gate"),
  authError: document.getElementById("auth-error"),
  authDismiss: document.getElementById("auth-dismiss"),
  tenonLogin: document.getElementById("tenon-login"),
  aboutDialog: document.getElementById("about-dialog"),
  aboutClose: document.getElementById("about-close"),
  aboutVersion: document.getElementById("about-version"),
  confirmDialog: document.getElementById("confirm-dialog"),
  confirmForm: document.getElementById("confirm-form"),
  confirmTitle: document.getElementById("confirm-title"),
  confirmBody: document.getElementById("confirm-body"),
  confirmField: document.getElementById("confirm-field"),
  confirmLabel: document.getElementById("confirm-label"),
  confirmInput: document.getElementById("confirm-input"),
  confirmError: document.getElementById("confirm-error"),
  confirmCancel: document.getElementById("confirm-cancel"),
  confirmOk: document.getElementById("confirm-ok"),
};
