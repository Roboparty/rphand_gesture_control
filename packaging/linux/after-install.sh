#!/bin/sh
set -e

sandbox_path="/opt/RP-Hand-Gesture/chrome-sandbox"
app_path="/opt/RP-Hand-Gesture/rp-hand-gesture"
launcher_path="/usr/bin/rp-hand-gesture"
rule_path="/etc/udev/rules.d/70-rp-hand-canfd.rules"

if [ -f "${sandbox_path}" ]; then
  # Chromium refuses to start when its packaged SUID sandbox loses these modes.
  chown root:root "${sandbox_path}"
  chmod 4755 "${sandbox_path}"
fi

# The custom package hook replaces electron-builder's default launcher setup.
# Keep a package-owned command in PATH so the GUI can start from any shell.
if [ -x "${app_path}" ]; then
  ln -sfn "${app_path}" "${launcher_path}"
fi

cat > "${rule_path}" <<'EOF'
# RP-Hand USB-CANFD adapter: grant the active desktop user device access.
SUBSYSTEMS=="usb", ATTRS{idVendor}=="a8fa", ATTRS{idProduct}=="8598", GROUP="plugdev", MODE="0660", TAG+="uaccess"
EOF

if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
  udevadm trigger --subsystem-match=usb || true
fi

exit 0
