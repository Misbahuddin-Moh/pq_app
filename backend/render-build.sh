#!/usr/bin/env bash
set -euo pipefail

# Render build script to install private GitHub dependencies via SSH deploy key.
# Requires env var: SSH_PRIVATE_KEY_B64 (base64-encoded private key)

if [[ -z "${SSH_PRIVATE_KEY_B64:-}" ]]; then
  echo "ERROR: SSH_PRIVATE_KEY_B64 is not set. Cannot install private git dependencies."
  exit 1
fi

mkdir -p ~/.ssh
chmod 700 ~/.ssh

echo "${SSH_PRIVATE_KEY_B64}" | base64 --decode > ~/.ssh/id_ed25519
chmod 600 ~/.ssh/id_ed25519

# Trust GitHub host key (avoid interactive prompt)
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
chmod 644 ~/.ssh/known_hosts

export GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes"

python -m pip install --upgrade pip
pip install -r requirements.txt
