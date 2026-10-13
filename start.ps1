# Main entry point for Windows (PowerShell 5.1+).
# Bootstraps the project-local .venv with uv (from uv.lock) and forwards all arguments to
# the Python CLI. Usage:  .\start.ps1 --help
# If scripts are blocked:  powershell -ExecutionPolicy Bypass -File .\start.ps1 --help
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    foreach ($c in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
        if (Test-Path $c) { $uv = $c }
    }
}
if (-not $uv) {
    Write-Host "ERROR: 'uv' is not installed. It is needed once to manage Python 3.12 and the .venv." -ForegroundColor Red
    Write-Host "Install it (one time) following the official instructions:"
    Write-Host "  https://docs.astral.sh/uv/getting-started/installation/"
    Write-Host "  Windows with winget:  winget install --id=astral-sh.uv -e"
    Write-Host "Then open a new terminal and re-run this command. See README.md -> Getting started."
    exit 127
}

$syncFlags = @('--locked', '--quiet')
if ($args -contains '--setup') { $syncFlags = @('--locked') }

# Creates .venv on first use; a fast no-op when it already matches uv.lock.
& $uv sync @syncFlags
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: environment sync failed. If you edited dependencies, run 'uv lock' and commit uv.lock." -ForegroundColor Red
    exit 1
}

# Make src/ importable even if the editable-install .pth file is skipped.
$env:PYTHONPATH = "$Root\src" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })

& $uv run --locked --no-sync python -m bess_catalonia @args
exit $LASTEXITCODE
