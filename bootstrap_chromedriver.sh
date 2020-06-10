#!/usr/bin/env bash

# This is meant as a developer tool so that developers can easily install chromedriver to their system for
# testing locally. This can also be used inside automation scripts to install the chromedriver in a production
# environment.

# You can set CHROMEDRIVER_DIR in order to customize
# the output location of the installed binary, and CHROMEDRIVER_DIST to customize the appropriate
# driver distribution; distributions should be provided in the format "linux64", "mac64", "win32," etc.
# By default CHROMEDRIVER_DIR is assumed to be the virtualenv bin directory, and the distribution is assumed to be
# linux64.
#
# To install in your virtualenv on a mac (a developer use case):
# CHROMEDRIVER_DIST=mac64 ./bootstrap_chromedriver.sh
#
# To install in /usr/local/bin on linux (a VM/container use case):
# CHROMEDRIVER_DIR=/usr/local/bin CHROMEDRIVER_DIST=linux64 sudo ./bootstrap_chromedriver.sh

set -e
CHROMEDRIVER_DIR=${CHROMEDRIVER_DIR:-env/bin}
CHROMEDRIVER_DIST=${CHROMEDRIVER_DIST:-linux64}
export CHROMEDRIVER_BIN="${CHROMEDRIVER_DIR}/chromedriver"
export CHROMEDRIVER_VERSION=$(curl https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
CHROMEDRIVER_URL="https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_${CHROMEDRIVER_DIST}.zip"

# Create the destination dir if it does not already exist, and remove any existing chromedriver binaries
test -d "${CHROMEDRIVER_DIR}" || mkdir -p "${CHROMEDRIVER_DIR}"
test -f "${CHROMEDRIVER_BIN}" && rm "${CHROMEDRIVER_BIN}"

echo "Installing chromedriver ${CHROMEDRIVER_VERSION} for ${CHROMEDRIVER_DIST} to ${CHROMEDRIVER_DIR}"
curl "${CHROMEDRIVER_URL}" > /tmp/chromedriver.zip
unzip /tmp/chromedriver.zip -d "${CHROMEDRIVER_DIR}"
chmod 755 "${CHROMEDRIVER_DIR}/chromedriver"
export PATH="${PATH}:${CHROMEDRIVER_DIR}"
