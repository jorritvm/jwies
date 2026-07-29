# Start een server en vier clients voor een testpotje op deze computer.
#
#   .\scripts\run_dev.ps1              -> server + 4 PyQt-clients
#   .\scripts\run_dev.ps1 -Clients 2   -> server + 2 PyQt-clients (de rest via de browser)
#   .\scripts\run_dev.ps1 -ServerOnly  -> enkel de server
#
# Druk op een toets in dit venster om alles weer af te sluiten.

param(
    [int]$Clients = 4,
    [switch]$ServerOnly,
    [int]$Port = 8000,
    [int]$WebPort = 8080
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$configPath = Join-Path $root "config\server.yaml"
if (-not (Test-Path $configPath)) {
    Write-Host "Geen config\server.yaml gevonden; ik gebruik templates\server.yaml."
    $configPath = Join-Path $root "templates\server.yaml"
}

# Twee aparte processen: de spelserver en de webserver die de browserclient
# uitdeelt. Zo blijft de pagina laden wanneer je de spelserver herstart.
Write-Host "Spelserver starten op poort $Port..."
$server = Start-Process -PassThru -FilePath "uv" -ArgumentList @(
    "run", "--package", "jwies-server", "jwies-server",
    "--config", $configPath, "--port", $Port
)

Write-Host "Webclient starten op poort $WebPort..."
$web = Start-Process -PassThru -FilePath "uv" -ArgumentList @(
    "run", "--package", "jwies-web-client", "jwies-web",
    "--port", $WebPort,
    "--game-server", "ws://127.0.0.1:$Port/ws"
)

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Browserclient: http://localhost:$WebPort"
Write-Host "Spelserver:    ws://localhost:$Port/ws"

$processes = @($server, $web)
if (-not $ServerOnly) {
    $names = @("Jan", "Piet", "Joris", "Korneel")
    for ($i = 0; $i -lt $Clients; $i++) {
        $processes += Start-Process -PassThru -FilePath "uv" -ArgumentList @(
            "run", "--package", "jwies-qt-client", "jwies",
            "--username", $names[$i],
            "--server", "ws://127.0.0.1:$Port/ws"
        )
        Start-Sleep -Milliseconds 400
    }
}

Write-Host ""
Write-Host "Druk op een toets om alles af te sluiten..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

foreach ($process in $processes) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "Alles afgesloten."
