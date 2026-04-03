#!/usr/bin/env bash
# =============================================================================
# install.sh  –  Deploy payu_frappe to Frappe Bench (Developer Mode)
# Run this from the frappe-bench root directory:
#   bash /path/to/install.sh
# =============================================================================

set -e

BENCH_DIR="$(pwd)"
APP_SRC="/path/to/payu_frappe"   # <-- Change this to where you copied the app
SITE="mysite.local"               # <-- Change to your site name

echo ""
echo "============================================"
echo "  payu_frappe – Frappe App Installer"
echo "============================================"
echo ""

# 1. Copy the app into the bench apps directory (skip if already there)
if [ ! -d "${BENCH_DIR}/apps/payu_frappe" ]; then
    echo "[1/6] Copying app source into bench/apps/ ..."
    cp -r "${APP_SRC}" "${BENCH_DIR}/apps/payu_frappe"
else
    echo "[1/6] App source already in apps/  – updating files ..."
    rsync -a --delete "${APP_SRC}/" "${BENCH_DIR}/apps/payu_frappe/"
fi

# 2. Install the Python package in editable mode
echo "[2/6] Installing Python package (pip install -e) ..."
env/bin/pip install -e apps/payu_frappe --quiet

# 3. Install the app into the site
echo "[3/6] Installing payu_frappe into site: ${SITE} ..."
bench --site "${SITE}" install-app payu_frappe

# 4. Run database migrations (creates DocType tables)
echo "[4/6] Running migrate (creates DocType tables) ..."
bench --site "${SITE}" migrate

# 5. Build assets (JS/CSS) — developer mode still needs this for first run
echo "[5/6] Building assets ..."
bench build --app payu_frappe

# 6. Restart to pick up hooks and new routes
echo "[6/6] Restarting bench ..."
bench restart

echo ""
echo "✅  Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Open Frappe desk → PayU Settings → enter Merchant Key & Salt"
echo "  2. Tick 'Use Sandbox' for testing, untick for production"
echo "  3. Submit an ITR form from your website"
echo "  4. Open the ITR Filing Submission in Frappe desk"
echo "  5. Set Service Amount → click 'Generate & Send Payment Link'"
echo ""
echo "API endpoint (React website):"
echo "  POST /api/method/payu_frappe.api.submit_itr_details"
echo ""
