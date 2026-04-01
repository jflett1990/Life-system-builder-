#!/bin/bash
set -e
# Update lockfile and install all workspace dependencies.
# Using --no-frozen-lockfile because task agents may add packages
# that update package.json files without regenerating the lockfile.
pnpm install --no-frozen-lockfile

# Install Python dependencies for the API server.
# Using --quiet to suppress the large download progress output.
pip install -q -r artifacts/api-server/requirements.txt
