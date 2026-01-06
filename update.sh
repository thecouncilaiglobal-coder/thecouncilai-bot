#!/bin/bash

# TheCouncilAI Bot - Manual Update Script
# This script manually updates the bot to the latest version

set -e

echo "========================================"
echo "  TheCouncilAI Bot - Manual Update"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "🔄 Pulling latest changes from GitHub..."
git pull

echo ""
echo "🐳 Pulling latest Docker image..."
docker-compose pull

echo ""
echo "♻️  Restarting bot with new version..."
docker-compose up -d

echo ""
echo "========================================"
echo "  ✅ Update Complete!"
echo "========================================"
echo ""
echo "View logs to ensure bot is running:"
echo "   docker-compose logs -f bot"
echo ""
