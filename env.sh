# Sensible defaults for environment variables

# Docker image name: default to current directory
export DOCKER_IMAGE=${DOCKER_IMAGE:-$(basename "$PWD")}
