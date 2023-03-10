#!/bin/bash
export OPENFAAS_URL=$(perl -ne 'print "$1\n" if /gateway: (.*)$/' stack.yml)
faas secret create database-connection --from-literal=mongodb://localhost:27017/test
faas secret create freesound-api-key --from-literal=secret-string
faas secret create europeana-api-key --from-literal=another-secret-string
faas secret create object-store-readwrite-access --from-literal=access-key
faas secret create object-store-readwrite-secret --from-literal=secret-key
faas secret create object-store-readonly-access --from-literal=access-key
faas secret create object-store-readonly-secret --from-literal=secret-key
