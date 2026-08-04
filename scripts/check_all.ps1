# Runs each independent project's own checks in turn. There is no shared
# venv anymore, so there is no single `uv run` that covers all of them.
#
#   .\scripts\check_all.ps1

$root = Split-Path -Parent $PSScriptRoot
$projects = @("jwies-server", "jwies-qt-client", "jwies-web-client", "tests")

foreach ($project in $projects) {
    $path = Join-Path $root $project
    Write-Host ""
    Write-Host "=== $project ===" -ForegroundColor Cyan
    Push-Location $path
    try {
        Write-Host "-- uv sync"
        uv sync
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "-- ruff check"
        uv run ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "-- pytest"
        uv run pytest -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "-- mypy (jwies-server only)" -ForegroundColor Cyan
Push-Location (Join-Path $root "jwies-server")
try {
    uv run mypy jwies_server jwies_core
} finally {
    Pop-Location
}
