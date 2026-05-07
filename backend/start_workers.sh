#!/bin/sh

python temporal_worker.py &
opa run --server /policies

wait