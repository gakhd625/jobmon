#!/usr/bin/env bash
# deploy/setup_ec2.sh
# ──────────────────────────────────────────────────────────────────
# One-shot setup script for a fresh Ubuntu 22.04 EC2 instance.
# Run once after cloning the repo:
#
#   git clone https://github.com/YOUR_USER/jobmon.git
#   cd jobmon
#   chmod +x deploy/setup_ec2.sh
#   ./deploy/setup_ec2.sh
#
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "==> Repo directory: $REPO_DIR"

# ── 1. System packages ───────────────────────────────────────────
echo "==> Installing system dependencies …"
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git curl

# ── 2. Python virtual environment ───────────────────────────────
echo "==> Creating Python venv …"
python3 -m venv "$REPO_DIR/venv"
source "$REPO_DIR/venv/bin/activate"

echo "==> Installing Python packages …"
pip install --upgrade pip -q
pip install -r "$REPO_DIR/requirements.txt" -q

# ── 3. Playwright browser binaries ──────────────────────────────
echo "==> Installing Playwright Chromium …"
playwright install chromium
playwright install-deps chromium

# ── 4. Create .env if it doesn't exist ──────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "==> Copying .env.example -> .env (fill in your secrets!)"
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    echo ""
    echo "  *** IMPORTANT: Edit $REPO_DIR/.env with your real credentials ***"
    echo ""
fi

# ── 5. Create data and logs directories ─────────────────────────
mkdir -p "$REPO_DIR/data" "$REPO_DIR/logs"

# ── 6. Install systemd service + timer ──────────────────────────
echo "==> Installing systemd service and timer …"

# Patch the WorkingDirectory and ExecStart to match current deploy path
sed "s|/home/ubuntu/jobmon|$REPO_DIR|g" \
    "$REPO_DIR/deploy/jobmon.service" \
    | sudo tee /etc/systemd/system/jobmon.service > /dev/null

sed "s|/home/ubuntu/jobmon|$REPO_DIR|g" \
    "$REPO_DIR/deploy/jobmon.timer" \
    | sudo tee /etc/systemd/system/jobmon.timer > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable jobmon.timer
sudo systemctl start  jobmon.timer

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit $REPO_DIR/.env with your OnlineJobsPH, Telegram and OpenAI credentials."
echo "  2. Run a test:  $REPO_DIR/venv/bin/python $REPO_DIR/monitor.py"
echo "  3. Check timer: systemctl list-timers --all | grep jobmon"
echo "  4. Watch logs:  journalctl -u jobmon -f"
