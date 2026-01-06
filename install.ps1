# TheCouncilAI Bot - Installation Script for Windows
# Run in PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TheCouncilAI Bot - Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "✅ Docker is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Docker Desktop for Windows:" -ForegroundColor Yellow
    Write-Host "  https://docs.docker.com/desktop/install/windows-install/" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check if Docker Compose is installed
try {
    docker-compose --version | Out-Null
    Write-Host "✅ Docker Compose is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Docker Compose should come with Docker Desktop." -ForegroundColor Yellow
    Write-Host "Please ensure Docker Desktop is properly installed." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""

# Determine installation directory
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { "$env:USERPROFILE\thecouncilai-bot" }

Write-Host "📁 Installation directory: $InstallDir" -ForegroundColor Cyan
Write-Host ""

# Clone or update repository
if (Test-Path $InstallDir) {
    Write-Host "📂 Directory exists. Updating repository..." -ForegroundColor Yellow
    Set-Location $InstallDir
    git pull
} else {
    Write-Host "📥 Cloning repository..." -ForegroundColor Cyan
    git clone https://github.com/thecouncilaiglobal-coder/thecouncilai-bot.git $InstallDir
    Set-Location $InstallDir
}

Write-Host ""
Write-Host "✅ Repository downloaded" -ForegroundColor Green
Write-Host ""

# Create .env file if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env configuration file..." -ForegroundColor Cyan
    Copy-Item .env.example .env
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Please edit .env file and configure your settings:" -ForegroundColor Yellow
    Write-Host "   - Backend service URLs (if using remote services)" -ForegroundColor Yellow
    Write-Host "   - Broker credentials (configured via setup command)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run the following command to edit:" -ForegroundColor Cyan
    Write-Host "   notepad $InstallDir\.env" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
    Write-Host ""
}

# Run setup to configure bot credentials
Write-Host "🔧 Bot setup is required before first run" -ForegroundColor Cyan
Write-Host ""
Write-Host "After editing .env, run the setup command:" -ForegroundColor Yellow
Write-Host "   cd $InstallDir" -ForegroundColor White
Write-Host "   docker-compose run --rm bot python -m bot.main setup" -ForegroundColor White
Write-Host ""
Write-Host "This will:" -ForegroundColor Cyan
Write-Host "  1. Ask for your email and password (PocketBase account)" -ForegroundColor White
Write-Host "  2. Configure your broker (Alpaca or IBKR)" -ForegroundColor White
Write-Host "  3. Generate a QR code for app pairing (E2EE)" -ForegroundColor White
Write-Host ""

# Pull the latest Docker image
Write-Host "🐳 Pulling latest Docker image..." -ForegroundColor Cyan
docker-compose pull

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Edit configuration (if needed):" -ForegroundColor Yellow
Write-Host "   cd $InstallDir" -ForegroundColor White
Write-Host "   notepad .env" -ForegroundColor White
Write-Host ""
Write-Host "2. Run bot setup:" -ForegroundColor Yellow
Write-Host "   docker-compose run --rm bot python -m bot.main setup" -ForegroundColor White
Write-Host ""
Write-Host "3. Start the bot:" -ForegroundColor Yellow
Write-Host "   docker-compose up -d" -ForegroundColor White
Write-Host ""
Write-Host "4. View logs:" -ForegroundColor Yellow
Write-Host "   docker-compose logs -f bot" -ForegroundColor White
Write-Host ""
Write-Host "5. Stop the bot:" -ForegroundColor Yellow
Write-Host "   docker-compose down" -ForegroundColor White
Write-Host ""
Write-Host "📖 For more information, visit:" -ForegroundColor Cyan
Write-Host "   https://github.com/thecouncilaiglobal-coder/thecouncilai-bot" -ForegroundColor White
Write-Host ""
