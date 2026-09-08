#!/usr/bin/env bash
# Set up (or update) the local dev/test environment for the custom_components
# integration under custom_components/edenic_bluelab.
#
# Usage: ./scripts/setup_dev_env.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip -q
pip install -q \
    pytest-homeassistant-custom-component \
    requests \
    ruff

echo "Dev environment ready. Activate it with:"
echo "  source .venv/bin/activate"
