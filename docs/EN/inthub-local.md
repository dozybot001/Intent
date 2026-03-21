# IntHub Local

[中文](../CN/inthub-local.md) | English

## What it is

IntHub Local is the first distributable IntHub form.

It runs a local IntHub instance on your machine, serves both the API and the Web UI, and lets you inspect the semantic history from your own repositories in a browser.

It is distributed through GitHub Release assets, not PyPI.

## Requirements

- Python 3.9+
- a local repository that already uses Intent
- a GitHub `origin` remote in that repository for IntHub V1 linking

## Download

Open the latest project release on GitHub and download the `IntHub Local` asset bundle.

The bundle contains:

- `inthub-local.pyz`
- `inthub-local`
- `inthub-local.cmd`
- `README.txt`

## Start IntHub Local

On macOS or Linux:

```bash
./inthub-local
```

On Windows:

```bat
inthub-local.cmd
```

Or, on any platform with Python:

```bash
python3 inthub-local.pyz
```

By default, IntHub Local:

- binds to `http://127.0.0.1:7210`
- stores its database at `~/.inthub/inthub.db`
- opens your browser automatically

## Connect your repo

Inside your own project repository:

```bash
itt hub link --api-base-url http://127.0.0.1:7210
itt hub sync
```

Then open `http://127.0.0.1:7210` in your browser.

If you record more Intent data later, run `itt hub sync` again to refresh the local IntHub view.

## Useful options

```bash
./inthub-local --no-open
./inthub-local --port 7211
./inthub-local --db-path /path/to/inthub.db
```

If you change the port, use the same URL in `itt hub link --api-base-url ...`.
