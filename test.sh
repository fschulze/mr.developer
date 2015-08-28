#!/bin/bash
if [[ $PYTHON == "" ]]; then
    export PYTHON=python
fi
export PYTHON_VERSION=$($PYTHON --version 2>&1)
./bin/py.test --cov src/mr/developer $*
