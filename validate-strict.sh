#!/usr/bin/env bash

# When validating strictly, we don't want to
# amend the code provided, so instead of running "black"
# we want to run "black --check" which validates formatting
# without changing it.
# This command cuts and re-splices the default tox
# env to replace the "black" env with the "black_check" env.
tox_envs=$(poetry run tox -l | sed '/^\\$/d' | sed 's|black|black_check|g' | paste -sd "," -)
set -ex
poetry run tox -e ${tox_envs}
