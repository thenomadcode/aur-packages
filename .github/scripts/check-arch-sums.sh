#!/usr/bin/env bash
# Check that .SRCINFO has a real sha256 for every architecture's AppImage and
# that it matches the digest GitHub reports for the upstream release asset.
#
# Usage: check-arch-sums.sh <path/to/.SRCINFO> <release tag, e.g. v1.4.274>
# Needs `gh` (GH_TOKEN) unless SKIP_DIGEST_LOOKUP=1.
set -euo pipefail

srcinfo="$1"
tag="$2"
repo="${UPSTREAM_REPO:-stablyai/orca}"

declare -A assets=(
  [x86_64]='orca-linux.AppImage'
  [aarch64]='orca-linux-arm64.AppImage'
)

digests=''
if [[ "${SKIP_DIGEST_LOOKUP:-0}" != 1 ]]; then
  digests="$(gh api "repos/${repo}/releases/tags/${tag}" \
    --jq '.assets[] | "\(.name) \(.digest // "")"')"
fi

status=0
for arch in x86_64 aarch64; do
  mapfile -t sums < <(awk -F ' = ' -v key="sha256sums_${arch}" \
    '$1 ~ "^[[:space:]]*" key "$" {print $2}' "${srcinfo}")
  if (( ${#sums[@]} != 1 )) || ! [[ "${sums[0]}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "::error::${srcinfo}: expected one sha256 in sha256sums_${arch}, got: ${sums[*]:-<none>}"
    status=1
    continue
  fi
  echo "${arch}: ${sums[0]}"
  [[ "${SKIP_DIGEST_LOOKUP:-0}" == 1 ]] && continue

  asset="${assets[${arch}]}"
  digest="$(awk -v name="${asset}" '$1 == name {print $2}' <<<"${digests}")"
  if [[ -z "${digest}" ]]; then
    echo "::warning::${tag} has no digest for ${asset}; relying on the downloaded hash."
  elif [[ "${digest}" != "sha256:${sums[0]}" ]]; then
    echo "::error::sha256sums_${arch} does not match ${tag}/${asset} (${digest})"
    status=1
  fi
done
exit "${status}"
