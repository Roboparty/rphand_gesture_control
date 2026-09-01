# syntax=docker/dockerfile:1.7
FROM ubuntu:22.04 AS build

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_VERSION=22.18.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        dpkg \
        fakeroot \
        file \
        git \
        libatspi2.0-0 \
        libglib2.0-0 \
        libgtk-3-0 \
        libsecret-1-0 \
        libusb-1.0-0 \
        libx11-xcb1 \
        libxss1 \
        patchelf \
        python3 \
        python3-dev \
        python3-venv \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# OpenCV imports libGL even when tests run without a display. Keep this layer
# separate so changes to GUI runtime libraries do not invalidate the toolchain.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && tar -xJf "node-v${NODE_VERSION}-linux-x64.tar.xz" -C /usr/local --strip-components=1 \
    && rm "node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && node --version \
    && npm --version

WORKDIR /workspace
COPY . .

# The SDK archive is an ignored local build input. Only the two x86_64 runtime
# libraries needed by RP-Hand are copied into the frozen Python application.
RUN mkdir -p /tmp/rp-hand-sdk /tmp/libcanbus vendor/lib/linux/x86_64 \
    && tar -xzf packaging/linux/vendor-sdk.tar.gz -C /tmp/rp-hand-sdk \
        ./x86_64/lib/libLHandProLib.so \
        './x86_64/share/LHandProLib/examples/CANFD_python/lib/libcanbus(ubuntu22).tar' \
    && cp /tmp/rp-hand-sdk/x86_64/lib/libLHandProLib.so \
        vendor/lib/linux/x86_64/libLHandProLib.so \
    && tar -xf '/tmp/rp-hand-sdk/x86_64/share/LHandProLib/examples/CANFD_python/lib/libcanbus(ubuntu22).tar' \
        -C /tmp/libcanbus \
    && cp /tmp/libcanbus/libcanbus.so vendor/lib/linux/x86_64/libcanbus.so \
    && file vendor/lib/linux/x86_64/libLHandProLib.so vendor/lib/linux/x86_64/libcanbus.so \
    && ldd vendor/lib/linux/x86_64/libLHandProLib.so \
    && ldd vendor/lib/linux/x86_64/libcanbus.so

RUN python3 -m venv .venv \
    && .venv/bin/python -m pip install --no-cache-dir --upgrade pip \
    && .venv/bin/python -m pip install --no-cache-dir \
        -r requirements.txt -r requirements-dev.txt

ENV PATH="/workspace/.venv/bin:${PATH}"
RUN npm ci --prefix electron
RUN python -m pytest -q

# electron-builder can use a system FPM installation. Keep it after the test
# layers so package-tool changes do not invalidate the Python and Node setup.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ruby-dev ruby-rubygems \
    && gem install --no-document fpm -v 1.17.0 \
    && rm -rf /var/lib/apt/lists/* \
    && fpm --version

RUN --mount=type=cache,target=/root/.cache/electron \
    --mount=type=cache,target=/root/.cache/electron-builder \
    chmod +x packaging/linux/*.sh \
    && cd electron \
    && USE_SYSTEM_FPM=true npm run dist:linux

FROM scratch AS artifact
COPY --from=build /workspace/electron/dist/*.deb /
