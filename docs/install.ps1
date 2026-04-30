# NEXUS Agent Quick Installer
# Usage: irm https://werizu.github.io/nexus/install.ps1 | iex

$ErrorActionPreference = "Stop"

$BrainIP = if ($env:NEXUS_BRAIN) { $env:NEXUS_BRAIN } else { "100.122.236.58" }
$InstallDir = "$env:ProgramFiles\NEXUS Agent"

Write-Host ""
Write-Host "  NEXUS Agent Installer" -ForegroundColor Cyan
Write-Host "  Brain: $BrainIP" -ForegroundColor Gray
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  [!] Bitte als Administrator ausfuehren!" -ForegroundColor Red
    Write-Host "  Rechtsklick auf PowerShell -> Als Administrator ausfuehren" -ForegroundColor Yellow
    exit 1
}

# Check Python
Write-Host "  [1/5] Python pruefen..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  [!] Python nicht gefunden. Bitte installieren: https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $(python --version 2>&1)" -ForegroundColor Green

# Create directory with full permissions
Write-Host "  [2/5] Verzeichnis erstellen..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
icacls $InstallDir /grant "Benutzer:F" /T /Q 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    icacls $InstallDir /grant "Users:F" /T /Q 2>&1 | Out-Null
}
Write-Host "  OK: $InstallDir" -ForegroundColor Green

# Download files
Write-Host "  [3/5] Dateien herunterladen..." -ForegroundColor Yellow
$base = "https://raw.githubusercontent.com/Werizu/nexus/main/agent"
@("nexus_agent.py", "nexus_service.py", "requirements.txt") | ForEach-Object {
    Invoke-WebRequest -Uri "$base/$_" -OutFile "$InstallDir\$_" -UseBasicParsing
    Write-Host "  OK: $_" -ForegroundColor Green
}

# Write config
@"
mqtt:
  broker: "$BrainIP"
  port: 1883
  client_id: "nexus-agent-pc"
agent:
  device_id: "main_pc"
  name: "$env:COMPUTERNAME"
  report_interval: 10
alerts:
  cpu: 90
  ram: 90
  disk: 90
  gpu_temp: 85
  gpu_load: 95
  cooldown: 300
"@ | Out-File "$InstallDir\config.yaml" -Encoding UTF8

# Install dependencies (pywin32 first, then the rest)
Write-Host "  [4/5] Dependencies installieren..." -ForegroundColor Yellow
python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
python -m pip install --quiet pywin32 2>&1 | Out-Null
python -m pip install --quiet -r "$InstallDir\requirements.txt" 2>&1 | Out-Null
Write-Host "  OK: Alle Dependencies installiert" -ForegroundColor Green

# Install and start service
Write-Host "  [5/5] Windows-Dienst einrichten..." -ForegroundColor Yellow
$svc = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($svc) {
    Stop-Service NexusAgent -Force -ErrorAction SilentlyContinue
    python "$InstallDir\nexus_service.py" remove 2>&1 | Out-Null
    Start-Sleep 2
}
python "$InstallDir\nexus_service.py" install 2>&1 | Out-Null
Set-Service -Name "NexusAgent" -StartupType Automatic
python "$InstallDir\nexus_service.py" start 2>&1 | Out-Null

# Verify
Start-Sleep 2
$svc = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    Write-Host "  OK: Dienst laeuft!" -ForegroundColor Green
} else {
    Write-Host "  [!] Dienst konnte nicht gestartet werden" -ForegroundColor Yellow
    Write-Host "  Versuche: python `"$InstallDir\nexus_agent.py`"" -ForegroundColor Gray
}

Write-Host ""
Write-Host "  NEXUS Agent installiert!" -ForegroundColor Green
Write-Host ""
Write-Host "  Status:       Get-Service NexusAgent" -ForegroundColor Gray
Write-Host "  Logs:         Get-Content `"$InstallDir\nexus-agent.log`" -Tail 20" -ForegroundColor Gray
Write-Host "  Deinstall.:   python `"$InstallDir\nexus_service.py`" remove" -ForegroundColor Gray
Write-Host ""
