#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker &> /dev/null; then
  echo "Docker is required. Install Docker Desktop: https://www.docker.com/products/docker-desktop" >&2
  exit 1
fi

docker compose up --build -d

echo
echo "PulseDesk is running at http://localhost:8000"
echo "Logs:  docker compose logs -f"
echo "Stop:  ./stop.sh"
