# NEXUS Agent Quick Installer
# Usage: irm https://werizu.github.io/nexus/install.ps1 | iex

$ErrorActionPreference = "Stop"

$BrainIP = if ($env:NEXUS_BRAIN) { $env:NEXUS_BRAIN } else { "192.168.178.202" }
$InstallDir = "$env:ProgramFiles\NEXUS Agent"

Write-Host ""
Write-Host "  NEXUS Agent Installer" -ForegroundColor Cyan
Write-Host "  Brain: $BrainIP" -ForegroundColor Gray
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  [!] Bitte als Administrator ausfuehren!" -ForegroundColor Red
    exit 1
}

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  [!] Python nicht gefunden. Bitte installieren: https://python.org" -ForegroundColor Red
    exit 1
}

# Create directory
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# Download files
$base = "https://raw.githubusercontent.com/Werizu/nexus/main/agent"
@("nexus_agent.py", "nexus_service.py", "requirements.txt") | ForEach-Object {
    Invoke-WebRequest -Uri "$base/$_" -OutFile "$InstallDir\$_" -UseBasicParsing
    Write-Host "  Downloaded $_" -ForegroundColor Green
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
"@ | Out-File "$InstallDir\config.yaml" -Encoding UTF8

# Install deps
python -m pip install --quiet -r "$InstallDir\requirements.txt" 2>&1 | Out-Null

# Install service
$svc = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($svc) {
    Stop-Service NexusAgent -Force -ErrorAction SilentlyContinue
    python "$InstallDir\nexus_service.py" remove 2>&1 | Out-Null
    Start-Sleep 2
}
python "$InstallDir\nexus_service.py" install 2>&1
python "$InstallDir\nexus_service.py" start 2>&1

Write-Host ""
Write-Host "  NEXUS Agent installiert!" -ForegroundColor Green
Write-Host "  Status: Get-Service NexusAgent" -ForegroundColor Gray
Write-Host ""
