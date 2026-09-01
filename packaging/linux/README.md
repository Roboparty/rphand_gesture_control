# Ubuntu 22.04 deb build

The Linux package is built inside an Ubuntu 22.04 Docker image. The proprietary
vendor SDK remains outside Git and is supplied to the build script explicitly.

```bash
bash packaging/linux/build-deb.sh \
  /path/to/RP_Hand_SDK-API-Linux-20260727.tar.gz
```

The resulting amd64 package is exported to `artifacts/linux/`.

The build uses the host network by default so Docker can reuse DNS and proxy
settings from the Linux build machine. Set `RP_HAND_DOCKER_NETWORK=default` if
the machine's Docker bridge already has working outbound DNS.

The package bundles `libLHandProLib.so` and the Ubuntu 22 x86_64
`libcanbus.so`. It depends on the distribution `libusb-1.0-0` package and
installs a udev rule granting the active desktop user access to the RP-Hand
USB-CANFD adapter (`a8fa:8598`).

Installing the package also creates `/usr/bin/rp-hand-gesture`, so the desktop
application can be started from any shell with `rp-hand-gesture`.

For a GUI-only smoke test without physical hardware:

```bash
RP_HAND_DRIVER=sim rp-hand-gesture
```

Hardware mode remains the default when `RP_HAND_DRIVER` is not set.
