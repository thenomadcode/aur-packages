# aur-packages

Arch User Repository packages maintained by [thenomadcode](https://aur.archlinux.org/account/thenomadcode).

Each subdirectory is the canonical source for an AUR package; a GitHub Actions workflow keeps it in sync with the upstream project and pushes updates to AUR automatically.

## Packages

| AUR | Source in this repo | Purpose |
| --- | --- | --- |
| [`stably-orca-bin`](https://aur.archlinux.org/packages/stably-orca-bin) | [`stably-orca-bin/`](stably-orca-bin/) | Installs the prebuilt `orca-linux.AppImage` from each upstream release. Fast, stable. |
| [`stably-orca-git`](https://aur.archlinux.org/packages/stably-orca-git) | [`stably-orca-git/`](stably-orca-git/) | Builds Stably Orca from `main`. For testing upstream HEAD. Slow (full Electron build), may break without notice. |

Both packages install to `/opt/stably-orca/` with a wrapper at `/usr/bin/stably-orca` and a desktop entry at `/usr/share/applications/stably-orca.desktop`. They conflict with each other — install only one.

## Install

```sh
# Prebuilt (recommended)
yay -S stably-orca-bin

# Built from main (bleeding edge, slow, may break)
yay -S stably-orca-git
```

Any AUR helper works — `paru`, `yay`, plain `makepkg -si`. No AUR helper is required as a dependency.

## Upstream

[stablyai/orca](https://github.com/stablyai/orca) — Electron-based agentic coding IDE, MIT licensed. All credit to the Stably AI team. This repo only packages their releases for Arch; it does not modify their code.

## Auto-update

`stably-orca-bin` is bumped automatically:

1. A GitHub Actions job runs every 6 hours.
2. [`nvchecker`](https://github.com/lilydjwg/nvchecker) reads the latest `v*` tag from `stablyai/orca` releases.
3. If the upstream version differs from the committed `pkgver`, the workflow bumps `pkgver`/`pkgrel`, regenerates `sha256sums` with `updpkgsums`, and **test-builds the package in an `archlinux:base-devel` container**. If the build fails, a GitHub issue is opened and nothing is pushed to AUR.
4. On a clean build, `.SRCINFO` is regenerated, committed to `main`, and the `stably-orca-bin/` subtree is pushed to the AUR git repo over SSH using [`KSXGitHub/github-actions-deploy-aur`](https://github.com/KSXGitHub/github-actions-deploy-aur).

`stably-orca-git` has its own weekly workflow that re-runs the build against upstream HEAD and opens an issue if it breaks. It does not auto-bump, auto-push, or auto-release — `-git` packages fetch HEAD at install time.

### Required repo configuration

| Name | Type | Value |
| --- | --- | --- |
| `AUR_USERNAME` | Variable | AUR account username (e.g. `thenomadcode`) |
| `AUR_SSH_PRIVATE_KEY` | Secret | Private SSH key registered on the AUR account |

## Maintainer notes

Local commands (run from the package directory):

```sh
# Build + install from source in place
makepkg -si

# Build only, inspect artifact
makepkg -s

# Lint the PKGBUILD
namcap PKGBUILD
namcap ./*.pkg.tar.zst

# Refresh source checksums after bumping pkgver
updpkgsums

# Regenerate .SRCINFO (required before pushing to AUR)
makepkg --printsrcinfo > .SRCINFO

# Clean build tree
git clean -xdf
```

Pushing a manual fix to AUR:

```sh
# AUR repo lives at ssh://aur@aur.archlinux.org/<pkgname>.git
git clone ssh://aur@aur.archlinux.org/stably-orca-bin.git /tmp/aur-stably-orca-bin
rsync -a --delete --exclude=.git stably-orca-bin/ /tmp/aur-stably-orca-bin/
cd /tmp/aur-stably-orca-bin
git add -A
git commit -m "fix: <what>"
git push
```

## License

This packaging repository is MIT licensed (see [`LICENSE`](LICENSE)). Stably Orca itself is MIT licensed by [stablyai](https://github.com/stablyai/orca).
