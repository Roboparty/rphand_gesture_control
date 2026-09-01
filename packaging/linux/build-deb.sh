#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /path/to/RP_Hand_SDK-API-Linux.tar.gz [artifact-directory]" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "${script_dir}/../.." && pwd)"
sdk_archive="$(realpath "$1")"
artifact_dir="${2:-${project_root}/artifacts/linux}"
staged_sdk="${script_dir}/vendor-sdk.tar.gz"
docker_network="${RP_HAND_DOCKER_NETWORK:-host}"

if [[ ! -f "${sdk_archive}" ]]; then
  echo "Vendor SDK archive not found: ${sdk_archive}" >&2
  exit 1
fi

required_entries=(
  "./x86_64/lib/libLHandProLib.so"
  "./x86_64/share/LHandProLib/examples/CANFD_python/lib/libcanbus(ubuntu22).tar"
)
archive_entries="$(tar -tzf "${sdk_archive}")"
for entry in "${required_entries[@]}"; do
  if ! grep -Fqx -- "${entry}" <<<"${archive_entries}"; then
    echo "Vendor SDK is missing required entry: ${entry}" >&2
    exit 1
  fi
done

cleanup() {
  rm -f -- "${staged_sdk}"
}
trap cleanup EXIT

cp -- "${sdk_archive}" "${staged_sdk}"
mkdir -p -- "${artifact_dir}"

docker buildx build \
  --platform linux/amd64 \
  --network "${docker_network}" \
  --progress plain \
  --file "${script_dir}/Dockerfile" \
  --output "type=local,dest=${artifact_dir}" \
  "${project_root}"

echo "Linux package exported to: ${artifact_dir}"
