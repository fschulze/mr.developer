#!/bin/bash
if [[ $PYTHON == "" ]]; then
    export PYTHON=python
fi
if $($PYTHON --version >/dev/null 2>&1); then
    export PYTHON_VERSION=$($PYTHON --version 2>&1)
else
    export PYTHON_VERSION="Python 2.4.x"
fi
if echo $PYTHON_VERSION | grep -q " 2.4"; then
    echo $PYTHON $PYTHON_VERSION 2.4
    $PYTHON bootstrap.py -d
    ./bin/buildout buildout:parts=test versions:zc.buildout=1.7.1
elif echo $PYTHON_VERSION | grep -q " 2.5"; then
    echo $PYTHON $PYTHON_VERSION 2.5
    $PYTHON bootstrap.py -d
    ./bin/buildout buildout:parts=test versions:zc.buildout=1.7.1
elif echo $PYTHON_VERSION | grep -q " 2."; then
    echo $PYTHON $PYTHON_VERSION 2.x
    $PYTHON bootstrap.py -d
    ./bin/buildout buildout:parts=test
else
    echo $PYTHON $PYTHON_VERSION 3.x
    $PYTHON bootstrap2.py
    ./bin/buildout buildout:parts=test
fi
