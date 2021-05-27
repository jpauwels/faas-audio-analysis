#!/bin/bash


cat | ${BASH_SOURCE%/*}/run-essentia.sh "${Http_Path:1}"
