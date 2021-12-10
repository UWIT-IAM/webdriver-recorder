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

function print_help {
   cat <<EOF
   Use: bootstrap_chromedriver.sh [OPTIONS]

   Installs the latest chromedriver instance from Google. If no options are provided,
   it will be installed to your poetry environment ( if it is set up).
   You can specify the destination with '-d', if that doesn't suit your needs.

   Options:
   --dest / -d     The location to store the chromedriver binary.
                   If not provided, will be installed to the poetry
                   environment if exists. Otherwise, an error will be raised.
   --dist          mac64 / linux64 -- If not provided, will be derived from your
                   environment
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}


# Initialize some globals
dest=
dist=
DEBUG=
CHROMEDRIVER_VERSION=

function parse_args {
  while (( $# ))
  do
    case $1 in
      --dest|-d)
        shift
        dest="$1"
        ;;
      --dist)
        shift
        dist="$1"
        ;;
      --help|-h)
        print_help
        exit 0
        ;;
      --debug|-g)
        DEBUG=1
        ;;
      *)
        echo "Invalid Option: $1"
        print_help
        exit 1
        ;;
    esac
    shift
  done
}
function configure_dest {
  if [[ -z "${dest}" ]]
  then
    echo "No destination provided. Checking poetry status."
    if ! type poetry > /dev/null
    then
      echo "No --dest provided, and no poetry installation detected."
      return 1
    fi
    path=$(poetry env list --full-path | tail -n 1 | cut -f1 -d' ')
    if [[ "$?" != "0" ]] || [[ -z "${path}" ]]
    then
      echo "No --dest provided, and no poetry environment exists."
      return 1
    fi
    echo "Installing to poetry environment."
    dest="${path}/bin"
  fi
  if ! [[ -d "${dest}" ]]
  then
    echo "Creating destination: ${dest}"
    mkdir -p ${dest}
  fi
}

function configure_dist {
  if [[ -z "${dist}" ]]
  then
    if [[ "$(uname)" == "Darwin" ]]
    then
      dist=mac64
    else
      dist=linux64
    fi
  fi
}

function chromedriver_version {
  if [[ -z "${CHROMEDRIVER_VERSION}" ]]
  then
    export CHROMEDRIVER_VERSION=$(curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
  fi
  echo "${CHROMEDRIVER_VERSION}"
}

function chromedriver_url {
  local version="$(chromedriver_version)"
  local filename="chromedriver_${dist}.zip"
  echo "https://chromedriver.storage.googleapis.com/${version}/${filename}"
}


function install_chromedriver {
  local dest_filename="${dest}/chromedriver"
  local tmp_filename="/tmp/chromedriver.zip"

  echo "Installing chromedriver $(chromedriver_version) for ${dist} to ${dest}"
  curl -s "$(chromedriver_url)" > "${tmp_filename}"
  if rm "${dest_filename}" > /dev/null
  then
    echo "Removed previous installation of chromedriver from destination"
  fi
  unzip "${tmp_filename}" -d "${dest}" > /dev/null
  chmod 755 "${dest_filename}"
  rm "${tmp_filename}"
}


set -e
parse_args $@
configure_dest
configure_dist
install_chromedriver
