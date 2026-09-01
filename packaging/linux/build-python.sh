#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "${script_dir}/../.." && pwd)"

if [[ ! -f "${project_root}/main.py" ]]; then
  echo "Python entry point not found: ${project_root}/main.py" >&2
  exit 1
fi

cd "${project_root}"
python3 -m PyInstaller --noconfirm --clean packaging/linux/RP-Hand-linux.spec
