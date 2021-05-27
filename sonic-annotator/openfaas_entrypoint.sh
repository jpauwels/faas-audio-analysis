#!/bin/bash


# Construct Sonic Annotator arguments from query string
arguments=""
urldecode() { : "${*//+/ }"; echo -e "${_//%/\\x}"; }
for p in ${Http_Query//&/ }; do
    kvp=( ${p/=/ } )
    arguments+=" $(urldecode ${kvp[0]}) $(urldecode ${kvp[1]})"
done

cat | ${BASH_SOURCE%/*}/run-sonic-annotator.sh "${Http_Path:1}" ${arguments}
