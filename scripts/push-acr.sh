#!/usr/bin/env bash
set -euo pipefail

# 閉域の ACR へ、エージェントイメージを上げる。
# 使い方: ACR_LOGIN_SERVER=closedaiacr.azurecr.io ./scripts/push-acr.sh

root="$(cd "$(dirname "$0")/.." && pwd)"
server="${ACR_LOGIN_SERVER:?ACR_LOGIN_SERVER が空}"
tag="${IMAGE_TAG:-latest}"

az acr login --name "${server%%.*}"
docker build -t "${server}/closed-agent:${tag}" "${root}/agent"
docker push "${server}/closed-agent:${tag}"
echo "pushed ${server}/closed-agent:${tag}"
