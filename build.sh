#!/bin/sh

./bin/buildout -c stage1.cfg $*
./bin/buildout -c stage2.cfg $*
