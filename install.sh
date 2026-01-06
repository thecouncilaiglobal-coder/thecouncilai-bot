#!/bin/bash

# TheCouncilAI Bot - Installation Script for Linux/Mac
# This script installs the TheCouncilAI trading bot with one command

set -e

echo "========================================"
echo "  TheCouncilAI Bot - Installation"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo ""
    echo "Please install Docker first:"
    echo "  - Linux: https://docs.docker.com/engine/install/"
    echo "  - Mac: https://docs.docker.com/desktop/install/mac-install/"
    echo ""
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed!"
    echo ""
    echo "Please install Docker Compose:"
    echo "  https://docs.docker.com/compose/install/"
    echo ""
    exit 1
fi

echo "✅ Docker is installed"
echo ""

# Determine installation directory
INSTALL_DIR="${INSTALL_DIR:-$HOME/thecouncilai-bot}"

echo "📁 Installation directory: $INSTALL_DIR"
echo ""

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "📂 Directory exists. Updating repository..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📥 Cloning repository..."
    git clone https://github.com/thecouncilaiglobal-coder/thecouncilai-bot.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""
echo "✅ Repository downloaded"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env configuration file..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env file and configure your settings:"
    echo "   - Backend service URLs (if using remote services)"
    echo "   - Broker credentials (configured via setup command)"
    echo ""
    echo "Run the following command to edit:"
    echo "   nano $INSTALL_DIR/.env"
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Run setup to configure bot credentials
echo "🔧 Bot setup is required before first run"
echo ""
echo "After editing .env, run the setup command:"
echo "   cd $INSTALL_DIR"
echo "   docker-compose run --rm bot python -m bot.main setup"
echo ""
echo "This will:"
echo "  1. Ask for your email and password (PocketBase account)"
echo "  2. Configure your broker (Alpaca or IBKR)"
echo "  3. Generate a QR code for app pairing (E2EE)"
echo ""

# Pull the latest Docker image
echo "🐳 Pulling latest Docker image..."
docker-compose pull

echo ""
echo "========================================"
echo "  ✅ Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit configuration (if needed):"
echo "   cd $INSTALL_DIR"
echo "   nano .env"
echo ""
echo "2. Run bot setup:"
echo "   docker-compose run --rm bot python -m bot.main setup"
echo ""
echo "3. Start the bot:"
echo "   docker-compose up -d"
echo ""
echo "4. View logs:"
echo "   docker-compose logs -f bot"
echo ""
echo "5. Stop the bot:"
echo "   docker-compose down"
echo ""
echo "📖 For more information, visit:"
echo "   https://github.com/thecouncilaiglobal-coder/thecouncilai-bot"
echo ""
