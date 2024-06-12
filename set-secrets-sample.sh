#!/bin/bash
export OPENFAAS_URL=$(perl -ne 'print "$1\n" if /gateway: (.*)$/' stack.yml)
faas secret create database-connection --from-literal="mongodb://admin:test@mongo.storage.svc.cluster.local:27017/?directConnection=true&authSource=admin"
faas secret create freesound-api-key --from-literal=secret-string
faas secret create europeana-api-key --from-literal=another-secret-string
faas secret create object-store-access-key --from-literal=access-key
faas secret create object-store-secret-key --from-literal=secret-key
