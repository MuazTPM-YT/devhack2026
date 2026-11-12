#!/usr/bin/env bash
# build payment:v2-bad and load it into the k3d cluster (plan §3.4)
set -euo pipefail

cd "$(dirname "$0")/.."

docker build -t payment:v2-bad chaos/payment-bad
k3d image import payment:v2-bad -c oncall
echo "payment:v2-bad imported into oncall"
