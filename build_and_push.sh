#!/bin/bash
set -e

IMAGE="gamorosino/app-optic-radiation-track"
TAG="${1:-latest}"

echo "==> Building ${IMAGE}:${TAG}"
docker build -t "${IMAGE}:${TAG}" .

echo "==> Pushing ${IMAGE}:${TAG}"
docker push "${IMAGE}:${TAG}"

echo "==> Done: ${IMAGE}:${TAG}"
