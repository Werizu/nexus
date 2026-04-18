#!/bin/bash
# NEXUS — Einmalige Pi-Installation
set -e

echo "=== NEXUS Installation ==="

# System update
sudo apt-get update && sudo apt-get upgrade -y

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Docker Compose
sudo apt-get install -y docker-compose-plugin

# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
echo "Run: sudo tailscale up"

# Clone and start
echo ""
echo "=== Installation complete ==="
echo "Next steps:"
echo "  1. sudo tailscale up"
echo "  2. cd nexus && docker compose up -d"
echo "  3. Open http://$(hostname -I | awk '{print $1}'):8000/api/v1/health"
