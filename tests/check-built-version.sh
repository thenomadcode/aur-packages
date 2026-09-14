#!/usr/bin/env bash
# Run inside Arch, in the source package directory, after a successful build.
set -euo pipefail
version="$(makepkg --printsrcinfo | awk -F ' = ' '/^[[:space:]]*pkgver = / {print $2; exit}')"
[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.r[0-9]+\.g[0-9a-f]+$ ]]
for previous in mobile.android.v0.0.44.r10870.gfe4237cd41 1.1.30.r0.g0000000; do
  if [[ "$(vercmp "${version}" "${previous}")" -le 0 ]]; then
    echo "ERROR: built version ${version} does not upgrade ${previous}." >&2
    exit 1
  fi
done
echo "Verified desktop package version and upgrade ordering: ${version}"
