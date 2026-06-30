#!/usr/bin/env bash
# One-shot setup for a Raspberry Pi (Debian/Raspberry Pi OS). Idempotent-ish.
# Installs PortAudio, creates a venv with the live extra, and installs the systemd unit.
set -euo pipefail

PREFIX="${PREFIX:-/opt/olive}"
DATA_DIR="${DATA_DIR:-/var/lib/olive}"
CONF_DIR="${CONF_DIR:-/etc/olive}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing system audio libraries (PortAudio)"
sudo apt-get update
sudo apt-get install -y python3-venv libportaudio2

echo "==> Creating ${PREFIX} and ${DATA_DIR}"
sudo mkdir -p "$PREFIX" "$DATA_DIR" "$CONF_DIR"
sudo python3 -m venv "$PREFIX/.venv"
sudo "$PREFIX/.venv/bin/pip" install --upgrade pip
sudo "$PREFIX/.venv/bin/pip" install "$REPO_DIR[live]"

echo "==> Installing default config (edit ${CONF_DIR}/config.json for your placement/tz)"
if [ ! -f "$CONF_DIR/config.json" ]; then
  sudo cp "$REPO_DIR/config.sample.json" "$CONF_DIR/config.json"
  sudo sed -i 's#"db_path": "olive.db"#"db_path": "/var/lib/olive/olive.db"#' "$CONF_DIR/config.json"
  sudo sed -i 's#"health_path": "olive-health.json"#"health_path": "/var/lib/olive/olive-health.json"#' "$CONF_DIR/config.json"
fi

echo "==> Installing systemd unit"
sudo cp "$REPO_DIR/deploy/olive-monitor.service" /etc/systemd/system/
sudo systemctl daemon-reload

cat <<'EOF'

Done. Next steps:
  1. Edit /etc/olive/config.json  (set tz, placement_note, threshold).
  2. Create the service user:      sudo useradd -r -g audio olive && sudo chown -R olive /var/lib/olive
  3. Start it:                     sudo systemctl enable --now olive-monitor
  4. Watch logs:                   journalctl -u olive-monitor -f
  5. Generate a report:            /opt/olive/.venv/bin/olive-report --config /etc/olive/config.json --out report.html
EOF
