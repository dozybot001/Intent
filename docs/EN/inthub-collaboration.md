# IntHub Management and Collaboration

Status: settings and management (7.3), identity and history (7.4), and teams and public projects (7.5) are implemented. Device-code sign-in is still a proposal.

IntHub is benchmarked against GitHub. Pushing, browsing and resuming already work; this document covers the three layers around them: management (settings, rename, delete, export), history (what each push changed) and collaboration (teams, visibility, public pages).

## Principles

- **The browser manages projects; the CLI writes history.** Renames, visibility and members happen on the web. Semantic history only accepts CLI pushes with an access token, and a browser session can never rewrite it.
- **Private by default.** New projects are private. Going public takes an explicit confirmation in settings, and a push never publishes anything.
- **Deletable and portable.** You can delete a project or export its data at any time.
- **Follow GitHub's habits.** Names, layers and locations match what developers already know.

## How GitHub splits visibility

GitHub repositories are public or private. A third level, internal, exists only in GitHub Enterprise organizations.

"Visible to the team" is not a visibility level on GitHub. It comes from ownership plus grants: the repository belongs to an organization, stays private, and its members get a base permission. Permissions run Read, Triage, Write, Maintain, Admin.

## The IntHub model

IntHub reduces GitHub's organization to a **team**: a flat group of members.

| | Who can read | Who can push | Who can manage |
|---|---|---|---|
| Personal private project | The owner | The owner | The owner |
| Team private project | Every team member | Admins and members | Admins |
| Public project | Everyone, including signed-out visitors | As above | As above |

- **Visibility has two levels,** as on GitHub. A team's private project is naturally visible to the team, which gives the private, team and public layers with one switch.
- **The owner is a person or a team.** Names are unique per owner. A team project's full name is `team/project`, like GitHub's `owner/repo`. Personal projects have no prefix, because Tenon accounts have no chosen username. A project can move between a person and a team.
- **Three team roles:** admin (members, settings, deletion), member (read and push), viewer (read only). GitHub's five levels are too fine for small teams.
- **Public projects are read-only.** Visitors see the overview, Intents, Flow, Timeline, History, Decisions and search, but no members or settings. Pushing still takes membership.
- **Public projects hide author emails from visitors.** Author emails come from Git config and can be private, so visitors and non-members see names only. `itt pull` and export stay members-only: they carry the complete snapshot, and removing emails would change the revision checksum.
- **Links use the project ID.** A public link is `/?project=ID`, which keeps working after a rename or transfer.

## Settings

The header has two levels:

- **Settings** (gear): appearance, language, refresh, about. It needs no sign-in, so visitors can use it.
- **Account** (avatar): account things only: profile, access tokens, teams, Tenon account center, sign out.

Account, team and project settings share one layout: navigation on the left, one section at a time on the right.

**Account page** (`/account`):

- Profile: the name and sign-in come from Tenon and are shown read-only with a link to edit them; the email that links Snaps to the account; account deletion through Tenon.
- Access tokens: a name and a 30-, 90- or 365-day lifetime; the list shows when each was created, last used and expires; any token can be revoked. A new token is shown once, in the list.
- Teams: the teams you belong to, your role in each, and creating a team.

**Team page** (`/teams/TEAM`):

- Members: roles, removal, invite links and leaving. A team always keeps at least one admin.
- Projects: all of the team's projects.
- Settings (admins): name and URL; deleting the team, which needs its URL typed and removes its projects.

**Project settings** (the Settings tab, shown to admins):

- General: rename; visibility (going public needs the project name typed); a JSON export of the current snapshot and the revision list, which holds everything `itt pull` can restore.
- Members: team projects show the team's members and roles.
- Danger zone: transfer to a team you administer or back to your account; delete, which needs the project name typed.

## How the CLI follows renames and transfers

- Current CLIs send the project ID. IntHub finds the project by ID and returns its current name, and the CLI updates its local configuration and says so. Transfers and team URL changes work the same way.
- CLIs from 7.2.1 and earlier look projects up by name, so a rename gives `REMOTE_CHANGED` rather than a duplicate project. Upgrading fixes it. Do not use `itt remote add` to rename: it clears the sync baseline, so unpushed local work becomes "diverged".
- Old names do not redirect. GitHub redirects old repository URLs, but IntHub project names are only used by the CLI.

## Identity

As in Git, authors declare who they are, and the platform links that to an account and verifies it.

- **Each object records its author.** New Intents, Snaps and Decisions store `author: {name, email}`, read in Git's order: `ITT_AUTHOR_NAME` and `ITT_AUTHOR_EMAIL`, then Git's `user.name` and `user.email`. Most developers have nothing to set up.
- **A missing identity never blocks recording.** `itt init`, `itt status` and `itt doctor` warn instead. Older objects have no author, and the interface shows none.
- **Agents are recorded separately.** The existing `origin` field records which Agent wrote an object, like Git's `Co-authored-by`.
- **Each push records its pusher:** the account behind the token, and the name and email the CLI declares.
- **Changes belong to revisions.** Status and relation changes have no author of their own; they belong to the revision that brought them, as a Git commit does.
- **IntHub links identities.** Sign-in stores the verified Tenon email. An author email that matches a member's shows that member.
- **Verified.** When an object was also pushed by the author's own account, it is marked Verified, like GitHub's badge. The server works this out at push time.
- **No signatures.** Pushes already need an access token, so "the pushing account is the author" is enough.

## History

- **History page:** each push is one revision with its time, pusher and a summary such as "2 Intents and 5 Snaps added, 1 Decision deprecated". The timeline filters by author, like `git log --author`.
- **Semantic diff:** comparing adjacent snapshots lists added objects, status changes and relation changes, like a GitHub commit page.
- **Snaps link to Git:** inside a Git repository a Snap records the current commit, and IntHub links it when the project has a known remote.

## Teams and collaboration

- Create a team, add people by invite link (single use, valid for 7 days, stored as a hash), change roles, remove members. Accepting an invite is a browser action, so an access token cannot join a team.
- From the CLI, a team project is `itt remote add origin URL --project team/project`. Without a prefix it is a personal project, so existing configurations are unaffected. Admins and members can create and push; viewers can pull.
- When an account is deleted, its teams keep an admin: the longest-standing member takes over, preferring members over viewers. A team with nobody left is deleted with its projects.
- **Concurrent pushes still fast-forward.** With several people on a project, the later push has to `itt pull` first. An Agent can do that, but if both sides changed, a person has to resolve it. Real semantic merging belongs to Intent 8 (see [Semantic Git](semantic-git.md)), and teams will be its main users.
- **Home page:** lists your projects and your teams' projects, most recently synced first, with how many active Intents are blocked. With a single project, it opens that project.

## CLI sign-in (proposal)

Today `itt auth login` means creating a token on the web and pasting it into a terminal. The proposal is device-code sign-in like `gh auth login`:

1. The terminal shows a one-time code and opens IntHub's authorization page.
2. You sign in, check the code and click Authorize.
3. The CLI receives a token named "itt · machine", which can be revoked in settings.

The token never appears on screen, and this works over SSH, in containers and for Agents. Pasting a token stays as the fallback.

## Releases

| Version | Content |
|---|---|
| 7.3 | Account settings and token management; project rename, export and delete; CLI follows renames; focus styling |
| 7.4 | Author and pusher identity; history page and semantic diff; Snaps link to Git commits |
| 7.5 | Teams and roles; private and public; public project pages; project transfer; cross-project home |

The database only ever grows:

- 7.3 changes no tables.
- 7.4 adds the pusher and change summary to revisions, and the verified email to accounts.
- 7.5 adds team, member and invite tables, and owner team and visibility columns on projects. After a rollback the previous image ignores them: team projects and public pages become unreachable, and the data stays.

Each release can roll back to the previous image. Older CLIs do not validate unknown fields, so they read and write objects carrying `author` without trouble.
