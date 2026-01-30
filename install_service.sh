#!/bin/bash
set -e

SERVICE_FILE="gemma-bridge.service"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "[*] Creating systemd user directory..."
mkdir -p "$USER_SYSTEMD_DIR"

echo "[*] Copying service file..."
cp "$SERVICE_FILE" "$USER_SYSTEMD_DIR/"

echo "[*] Initializing global configuration directory..."
GLOBAL_CONFIG_DIR="$HOME/.config/gemma-bridge"
mkdir -p "$GLOBAL_CONFIG_DIR"

if [ ! -f "$GLOBAL_CONFIG_DIR/antigravity_config.json" ]; then
    echo "[*] Initializing default config..."
    cp antigravity_config.json "$GLOBAL_CONFIG_DIR/"
fi

echo "[*] Reloading systemd manager..."
systemctl --user daemon-reload

echo "[*] Enabling and starting service..."
systemctl --user enable --now gemma-bridge.service

echo "[*] Checking status..."
systemctl --user status gemma-bridge.service --no-pager
