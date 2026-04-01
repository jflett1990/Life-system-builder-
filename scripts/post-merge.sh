#!/bin/bash
set -e
# Update lockfile and install all workspace dependencies.
# Using --no-frozen-lockfile because task agents may add packages
# that update package.json files without regenerating the lockfile.
pnpm install --no-frozen-lockfile
