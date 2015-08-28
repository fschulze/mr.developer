#!/bin/bash
$PYTHON bootstrap.py
./bin/buildout buildout:parts=test
