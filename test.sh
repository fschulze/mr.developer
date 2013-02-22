#!/bin/bash
if [[ $PYTHON == "" ]]; then
    export PYTHON=python
fi
if $($PYTHON --version >/dev/null 2>&1); then
    export PYTHON_VERSION=$($PYTHON --version 2>&1)
else
    export PYTHON_VERSION="Python 2.4.x"
fi
if echo $PYTHON_VERSION | grep -q " 2."; then
    ./bin/py.test
else
    ./bin/py.test build/lib/
fi
