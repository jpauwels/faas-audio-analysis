#!/bin/sh
ssh johan@frank -L 172.17.0.1:9000:127.0.0.1:9000 -N
