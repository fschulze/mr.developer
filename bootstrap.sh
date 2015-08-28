#!/bin/bash
if [[ $PYTHON == "" ]]; then
    export PYTHON=python
fi
$PYTHON bootstrap.py
./bin/buildout
