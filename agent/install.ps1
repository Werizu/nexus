# NEXUS Agent Installer for Windows
# Run as Administrator: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [string]$BrainIP = "192.168.178.202",
    [int]$MQTTPort = 1883,
    [string]$DeviceID = "main_pc",
    [string]$InstallDir = "$env:ProgramFiles\NEXUS Agent"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║         NEXUS Agent Installer          ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run as Administrator!" -ForegroundColor Red
    Write-Host "  Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
    exit 1
}

# Check Python
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  Found: $pyVersion" -ForegroundColor Green

# Create install directory
Write-Host "[2/6] Creating install directory..." -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    Write-Host "  Directory exists, updating..." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Write-Host "  $InstallDir" -ForegroundColor Green

# Download agent files
Write-Host "[3/6] Downloading agent files..." -ForegroundColor Yellow
$repoBase = "https://raw.githubusercontent.com/Werizu/nexus/main/agent"
$files = @("nexus_agent.py", "nexus_service.py", "requirements.txt")

foreach ($file in $files) {
    $url = "$repoBase/$file"
    $dest = Join-Path $InstallDir $file
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        Write-Host "  Downloaded: $file" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Failed to download $file : $_" -ForegroundColor Red
        exit 1
    }
}

# Create config
Write-Host "[4/6] Creating configuration..." -ForegroundColor Yellow
$configContent = @"
# NEXUS Agent Configuration
mqtt:
  broker: "$BrainIP"
  port: $MQTTPort
  client_id: "nexus-agent-pc"

agent:
  device_id: "$DeviceID"
  name: "$env:COMPUTERNAME"
  report_interval: 10
"@
$configContent | Out-File -FilePath (Join-Path $InstallDir "config.yaml") -Encoding UTF8
Write-Host "  Config: broker=$BrainIP, device=$DeviceID" -ForegroundColor Green

# Install dependencies
Write-Host "[5/6] Installing Python dependencies..." -ForegroundColor Yellow
$reqFile = Join-Path $InstallDir "requirements.txt"
python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
python -m pip install --quiet -r $reqFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] Some dependencies may have failed" -ForegroundColor Yellow
} else {
    Write-Host "  Dependencies installed" -ForegroundColor Green
}

# Install and start Windows service
Write-Host "[6/6] Installing Windows service..." -ForegroundColor Yellow
$servicePath = Join-Path $InstallDir "nexus_service.py"

# Stop existing service if running
$existingService = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "  Stopping existing service..." -ForegroundColor Yellow
    Stop-Service -Name "NexusAgent" -Force -ErrorAction SilentlyContinue
    python $servicePath remove 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

python $servicePath install 2>&1
python $servicePath start 2>&1

$service = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "  Service installed and running!" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Service installed but may not be running." -ForegroundColor Yellow
    Write-Host "  Try: python `"$servicePath`" start" -ForegroundColor Yellow
    Write-Host "  Or run directly: python `"$(Join-Path $InstallDir 'nexus_agent.py')`"" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ✓ NEXUS Agent installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  Install dir:  $InstallDir" -ForegroundColor White
Write-Host "  Brain:        $BrainIP:$MQTTPort" -ForegroundColor White
Write-Host "  Device ID:    $DeviceID" -ForegroundColor White
Write-Host ""
Write-Host "  Commands:" -ForegroundColor White
Write-Host "    Status:   Get-Service NexusAgent" -ForegroundColor Gray
Write-Host "    Stop:     Stop-Service NexusAgent" -ForegroundColor Gray
Write-Host "    Start:    Start-Service NexusAgent" -ForegroundColor Gray
Write-Host "    Remove:   python `"$servicePath`" remove" -ForegroundColor Gray
Write-Host "    Logs:     Get-Content `"$(Join-Path $InstallDir 'nexus-agent.log')`" -Tail 20" -ForegroundColor Gray
Write-Host ""
