#!/usr/bin/env bash
set -e

mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH6QvEv9HNZM2mPGJ3YMkrikjVkPUcv0N4wYJdPtzFNM codex-autodl
EOF
chmod 600 ~/.ssh/authorized_keys
