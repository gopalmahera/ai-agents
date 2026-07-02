#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-414448255958.dkr.ecr.ap-south-1.amazonaws.com/monitoring}"
IMAGE="${IMAGE:-dai-agent}"
AWS_REGION="${AWS_REGION:-ap-south-1}"
PLATFORM="${PLATFORM:-linux/amd64}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  VCS_REF="$(git rev-parse --short HEAD)"
  if git describe --tags --exact-match >/dev/null 2>&1; then
    DEFAULT_TAG="$(git describe --tags --exact-match)"
  else
    DEFAULT_TAG="${VCS_REF}"
  fi
else
  VCS_REF="unknown"
  DEFAULT_TAG="dev"
fi

TAG="${TAG:-$DEFAULT_TAG}"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
IMAGE_URI="${REGISTRY}/${IMAGE}"

echo "Building ${IMAGE_URI}:${TAG} (${PLATFORM})"
echo "  VCS_REF=${VCS_REF}"
echo "  BUILD_DATE=${BUILD_DATE}"

docker build \
  --platform "${PLATFORM}" \
  --pull \
  --build-arg VERSION="${TAG}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  -t "${IMAGE_URI}:${TAG}" \
  -t "${IMAGE_URI}:${VCS_REF}" \
  -f Dockerfile.agent \
  .

if [[ "${PUSH:-true}" == "true" ]]; then
  echo "Logging in to ECR (${AWS_REGION})"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "${REGISTRY%%/*}"

  echo "Pushing ${IMAGE_URI}:${TAG}"
  docker push "${IMAGE_URI}:${TAG}"
  docker push "${IMAGE_URI}:${VCS_REF}"

  if [[ "${TAG_LATEST:-false}" == "true" ]]; then
    docker tag "${IMAGE_URI}:${TAG}" "${IMAGE_URI}:latest"
    docker push "${IMAGE_URI}:latest"
  fi
fi

echo "Done: ${IMAGE_URI}:${TAG}"
echo "Image architecture: $(docker inspect --format '{{.Architecture}}' "${IMAGE_URI}:${TAG}")"
