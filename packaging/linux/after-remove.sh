#!/bin/sh
set -e

launcher_path="/usr/bin/rp-hand-gesture"

case "${1:-remove}" in
  remove|purge|0)
    rm -f "${launcher_path}"
    rm -f /etc/udev/rules.d/70-rp-hand-canfd.rules
    if command -v udevadm >/dev/null 2>&1; then
      udevadm control --reload-rules || true
    fi
    ;;
esac

exit 0
