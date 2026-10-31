# IntHub collaboration guide

[中文](../CN/inthub-collaboration.md) | English

IntHub is the optional service for browsing and sharing Intent history. This guide covers the hosted service at [inthub.tenon.asia](https://inthub.tenon.asia). The model follows GitHub's: each project has an owner and is private or public, and a team gives its members roles.

Two rules hold throughout:

- **The browser manages, the CLI writes history.** Renames, visibility, teams and deletion happen in the browser. History changes only through `itt push` with an access token. A browser session cannot write history, and a token cannot manage anything.
- **Private by default.** Every new project starts private. Going public takes an explicit confirmation, and a push never changes visibility.

A local hub (`itt hub start`) runs on your own machine and has no accounts, teams, visibility or quotas. You can still rename, export and delete projects there.

| Where | What is there |
|---|---|
| **Settings** (gear icon) | Access tokens, Teams, Usage |
| **Account** (avatar) | Profile, Danger zone |
| Team page, `/teams/TEAM` | Members, Projects, Settings (admins only) |
| A project's **Settings** tab (admins only) | General, Members (team projects), Danger zone |

## Accounts and sign-in

An IntHub account is a Tenon account. In the browser, sign in with GitHub, Apple or email. IntHub requests no access to your repositories, and a browser session lasts up to 30 days. Your name and email come from Tenon. **Account** shows them and links to Tenon to change them.

To sign in from the terminal, run `itt auth login`:

1. The terminal shows an 8-letter code, and opens the `/device` page if the machine has a browser.
2. In any browser, sign in, type the code, check the device name and click **Authorize**.
3. The CLI receives a 90-day access token named "itt on MACHINE".

The code expires after 10 minutes. You always type it by hand, so nobody can send you a link to approve. Step 2 can happen on another device, so this also works over SSH and in containers. `itt auth status` shows whether you are signed in.

Each Intent, Snap and Decision records its author, read from your Git config or from `ITT_AUTHOR_NAME` and `ITT_AUTHOR_EMAIL`. When your account pushes an object whose author email is your Tenon email, IntHub marks it **Verified**. **Account** shows the command that sets Git to that address.

## Projects and visibility

A project's owner is your account or a team. Names are unique per owner. A personal project is `NAME`. A team project is `TEAM/NAME`, where `TEAM` is the team's URL. The home page lists your projects and your teams' projects, most recently synced first.

You create projects from the CLI:

```bash
itt push    # a personal project, named after this directory

itt remote add origin https://inthub.tenon.asia --project acme/checkout    # a team project
itt push
```

A project is private or public, and there is no third setting. A team's private project is the middle layer: the whole team can read it, and nobody else can.

| Project | Read in the browser | `itt pull` | `itt push` | Manage |
|---|---|---|---|---|
| Personal, private | You | You | You | You |
| Personal, public | Everyone | You | You | You |
| Team, private | All team members | All team members | Admins and members | Admins |
| Team, public | Everyone | All team members | Admins and members | Admins |

Manage means rename, change visibility, transfer, export from settings and delete.

To go public, open the project's **Settings** tab, choose **Make public** and type the project name. IntHub first checks the current history for likely credentials: private keys, API keys, access tokens and passwords in URLs. If it finds any, it lists the objects. Check them, then confirm again if you still want to publish. **Make private** takes effect at once, but people who already read the project may have kept a copy.

A project's link is `/?project=ID`, which keeps working after a rename or transfer. IntHub has no public directory, so visitors reach a public project through its link.

Admins rename a project in its **Settings** tab, and transfer it under **Danger zone** to a team they administer or back to their own account. A transfer needs the project name typed. The new owner needs a free project slot and no project with that name. Who can read, push and manage then follows the new owner.

Clones follow a rename, a transfer or a new team URL on their next push or pull, because they find the project by ID. A very old `itt` reports `REMOTE_CHANGED` until you upgrade it. Do not use `itt remote add` to follow a rename: it clears the sync baseline, so unpushed local work reads as diverged.

## Teams and roles

A team is a flat group of accounts that own projects together. Create one under **Settings → Teams** with a name and a URL. The URL uses lowercase letters, digits and hyphens, up to 39 characters, with no hyphen at either end. You become its admin. An account can create up to 10 teams.

| Role | Read and pull | Push and create projects | Manage members, the team and its projects |
|---|---|---|---|
| Admin | Yes | Yes | Yes |
| Member | Yes | Yes | No |
| Viewer | Yes | No | No |

- Only members can open a team page. Everyone in the team sees the member list, and only admins see email addresses.
- Admins change roles, remove members, rename the team and change its URL.
- Anyone can leave a team. A team always keeps at least one admin, so the last admin has to make someone else an admin first.
- Team changes are browser actions. An access token uses a membership but cannot change it.

## Invites

Admins add people with invite links on the team page:

- Choose a role and create a link. It is shown once, and IntHub keeps only its hash.
- A link works once and expires after 7 days.
- Pending invites are listed and can be revoked. A team can hold up to 50.
- Anyone who opens the link and signs in can join with that role, because a link is not tied to an email address. Send it only to the person you mean.
- Accepting happens in the browser, so an access token cannot join a team.

## What visitors can see

A visitor is anyone reading a public project without belonging to it: signed out, or signed in with an account that is not a member.

Visitors can read the Overview, Intents, Flow, Timeline, History and Decisions tabs, and search the project. They see the names of authors and pushers.

Visitors cannot:

- See author or pusher emails. Emails come from Git config and can be private.
- See the Settings tab or the member list.
- Run `itt pull` or export. Both carry the complete snapshot with author emails, and removing them would change the revision checksum.
- Push.

To anyone outside it, a private project looks the same as one that does not exist.

Public projects show **Report this project** to everyone who cannot manage them. A project that IntHub takes down becomes private and cannot go public again without contacting support.

## Push and pull rights

The table above shows who can do what. Pulling takes membership, even on a public project. Pushing takes the admin or member role, or owning the personal project. Both use an access token.

Each project has one shared history, and pushes only fast-forward:

- If someone pushed before you, run `itt pull`, then `itt push`.
- If you both recorded work, `itt status` reports `diverged`. Run `itt pull` to merge the remote, settle any conflict, then `itt push`.

Merging parallel work is planned for Intent 8. See [Semantic Git](semantic-git.md).

## Access tokens

The CLI reads and pushes with an access token. A token belongs to your account and carries all of its rights, so it cannot be limited to one project.

- `itt auth login` creates a token and stores it for you.
- Under **Settings → Access tokens** you can generate one by hand, with a name and a lifetime of 30, 90 or 365 days. It is shown once, in the list. Generate one for each machine or agent.
- The list shows active tokens with their creation date, last use and expiry. **Revoke** stops a token at once.
- On unattended machines, set `INTHUB_TOKEN` or pass `--token`.
- `itt auth logout` removes the token from this machine only. It stays valid until it expires or you revoke it.
- Tokens cannot manage projects, teams, other tokens or your account. Those need a browser session.

## Quotas

Each owner, an account or a team, can keep 100 projects and 1 GB of history on the hosted service. **Settings → Usage** shows your personal allowance and each team's.

Each push stores a whole snapshot, so storage grows with every push. At a limit, creating a project or pushing fails with `QUOTA_EXCEEDED`. Deleting a project frees its storage.

## Export and deletion

**Export a project.** In the project's **Settings** tab, **Download export** saves a JSON file with the current snapshot and the revision list. It holds everything `itt pull` can restore.

**Delete a project.** Under **Danger zone** in the project's **Settings** tab, type the project name. This removes the project and its history from IntHub and cannot be undone. Your local `.intent/` is not touched. To publish it again, run `itt hub link`, then `itt push`.

**Delete a team.** On the team's **Settings** page, type the team URL. This removes the team and all of its projects from IntHub and cannot be undone. Local `.intent/` directories are not touched.

**Delete your account.** Under **Account → Danger zone**, start the deletion and confirm it in Tenon's account center. This removes your account, personal projects and access tokens from IntHub. A team where you are the only admin passes to its longest-standing member, or to its longest-standing viewer if it has no members. A team with nobody else in it is deleted with its projects. Your local `.intent/` is not touched.
