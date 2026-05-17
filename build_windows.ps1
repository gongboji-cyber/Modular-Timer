$ErrorActionPreference = "Stop"

# Build from the project root, no matter where the script is launched from.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "[1/5] Preparing virtual environment..."
if (!(Test-Path ".venv")) {
    python -m venv .venv
}

Write-Host "[2/5] Installing dependencies..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "[3/5] Cleaning previous build..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "ModularTimer.spec") { Remove-Item -Force "ModularTimer.spec" }

Write-Host "[4/5] Building Windows executable..."
.\.venv\Scripts\pyinstaller.exe `
  --noconfirm `
  --clean `
  --windowed `
  --name ModularTimer `
  --paths "$ProjectRoot\src" `
  --collect-submodules modular_timer_desktop `
  --add-data "$ProjectRoot\assets\app.ico;assets" `
  --icon "$ProjectRoot\assets\app.ico" `
  "$ProjectRoot\run.py"

Write-Host "[5/5] Done. Open: $ProjectRoot\dist\ModularTimer\ModularTimer.exe"