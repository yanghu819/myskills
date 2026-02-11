#!/usr/bin/env bash
set -e

KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH6QvEv9HNZM2mPGJ3YMkrikjVkPUcv0N4wYJdPtzFNM codex-autodl'

mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
grep -qxF "$KEY" ~/.ssh/authorized_keys || echo "$KEY" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

echo "authorized_keys updated"
