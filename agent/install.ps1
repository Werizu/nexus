# NEXUS Agent Installer for Windows
# Run as Administrator: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [string]$InstallDir = "$env:ProgramFiles\NEXUS Agent"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  NEXUS Agent Installer" -ForegroundColor Cyan
Write-Host "  =====================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] Bitte als Administrator ausfuehren!" -ForegroundColor Red
    Write-Host "  Rechtsklick auf PowerShell -> Als Administrator ausfuehren" -ForegroundColor Yellow
    exit 1
}

# ── Credentials ────────────────────────────────────────
Write-Host "  Dein NEXUS Admin muss dir einen Account angelegt haben." -ForegroundColor White
Write-Host ""
$BrainIP = Read-Host "  Brain IP (Tailscale IP des Brain Pi)"
$NexusUser = Read-Host "  NEXUS Username"
$NexusPass = Read-Host "  NEXUS Passwort" -AsSecureString
$NexusPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($NexusPass))

if (-not $BrainIP -or -not $NexusUser -or -not $NexusPassPlain) {
    Write-Host "[!] Alle Felder sind erforderlich." -ForegroundColor Red
    exit 1
}

# ── Verify connection ──────────────────────────────────
Write-Host ""
Write-Host "[1/5] Verbindung zum Brain pruefen..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "http://${BrainIP}:8000/api/v1/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "  Brain erreichbar" -ForegroundColor Green
} catch {
    Write-Host "  [!] Brain nicht erreichbar unter http://${BrainIP}:8000" -ForegroundColor Red
    Write-Host "  Pruefe: Ist Tailscale aktiv? Ist der Brain Pi eingeschaltet?" -ForegroundColor Yellow
    exit 1
}

# ── Check Python ───────────────────────────────────────
Write-Host "[2/5] Python pruefen..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[!] Python nicht gefunden. Installieren: https://python.org" -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  $pyVersion" -ForegroundColor Green

# ── Download agent files ───────────────────────────────
Write-Host "[3/5] Agent herunterladen..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$repoBase = "https://raw.githubusercontent.com/Werizu/nexus/main/agent"
$files = @("nexus_agent.py", "nexus_service.py", "requirements.txt")

foreach ($file in $files) {
    $url = "$repoBase/$file"
    $dest = Join-Path $InstallDir $file
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        Write-Host "  $file" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Download fehlgeschlagen: $file" -ForegroundColor Red
        exit 1
    }
}

# ── Write config with credentials ──────────────────────
Write-Host "[4/5] Konfiguration schreiben..." -ForegroundColor Yellow
$configContent = @"
mqtt:
  broker: "$BrainIP"
  port: 1883
auth:
  username: "$NexusUser"
  password: "$NexusPassPlain"
agent:
  report_interval: 10
alerts:
  cpu: 90
  ram: 90
  disk: 90
  gpu_temp: 85
  gpu_load: 95
  cooldown: 300
"@
$configContent | Out-File -FilePath (Join-Path $InstallDir "config.yaml") -Encoding UTF8
Write-Host "  Config geschrieben" -ForegroundColor Green

# ── Install dependencies ──────────────────────────────
Write-Host "[5/5] Dependencies installieren..." -ForegroundColor Yellow
$reqFile = Join-Path $InstallDir "requirements.txt"
python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
python -m pip install --quiet -r $reqFile 2>&1
Write-Host "  Dependencies installiert" -ForegroundColor Green

# ── Install and start Windows service ──────────────────
Write-Host ""
Write-Host "  Service installieren..." -ForegroundColor Yellow
$servicePath = Join-Path $InstallDir "nexus_service.py"

$existingService = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($existingService) {
    Stop-Service -Name "NexusAgent" -Force -ErrorAction SilentlyContinue
    python $servicePath remove 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

python $servicePath install 2>&1
python $servicePath start 2>&1

$service = Get-Service -Name "NexusAgent" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "  Service laeuft!" -ForegroundColor Green
} else {
    Write-Host "  [!] Service installiert aber laeuft evtl. nicht." -ForegroundColor Yellow
    Write-Host "  Alternativ: python `"$(Join-Path $InstallDir 'nexus_agent.py')`"" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  NEXUS Agent installiert!" -ForegroundColor Green
Write-Host "  ════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Der Agent registriert sich automatisch beim Brain." -ForegroundColor White
Write-Host "  Dein Geraet erscheint in wenigen Sekunden im Dashboard." -ForegroundColor White
Write-Host ""
Write-Host "  Status:   Get-Service NexusAgent" -ForegroundColor Gray
Write-Host "  Logs:     Get-Content `"$(Join-Path $InstallDir 'nexus-agent.log')`" -Tail 20" -ForegroundColor Gray
Write-Host "  Stoppen:  Stop-Service NexusAgent" -ForegroundColor Gray
Write-Host "  Entfernen: python `"$servicePath`" remove" -ForegroundColor Gray
Write-Host ""
