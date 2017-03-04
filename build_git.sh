#!/bin/sh
set -e

pwd
BASE_DIR=$(pwd)

if [ "$USE_GIT_VERSION" = "" ]; then
    echo "Not building git"
    exit 0
fi

if [ -e "git/prefix-${USE_GIT_VERSION}/bin/git" ]; then
    echo "Using existing git build"
    exit 0
fi

mkdir -p downloads
mkdir -p git
cd ${BASE_DIR}/downloads
pwd
wget -c https://github.com/git/git/archive/v${USE_GIT_VERSION}.tar.gz
cd ${BASE_DIR}/git
pwd
tar xzf ../downloads/v${USE_GIT_VERSION}.tar.gz
cd ${BASE_DIR}/git/git-${USE_GIT_VERSION}
pwd
NO_GETTEXT=1 make prefix=${BASE_DIR}/git/prefix-${USE_GIT_VERSION} install
cd $BASE_DIR
