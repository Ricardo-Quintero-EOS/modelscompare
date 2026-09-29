$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $projectRoot

try {
    python -m pip install -e ".[build]"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the package build dependencies."
    }

    python -m PyInstaller `
        --clean `
        --noconfirm `
        --onefile `
        --console `
        --name ModelsCompare `
        --paths src `
        --specpath build\pyinstaller `
        --collect-all prompt_toolkit `
        --collect-all rich `
        --collect-all openpyxl `
        --collect-all bs4 `
        --collect-all requests `
        --collect-all certifi `
        src\modelscompare\cli.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller could not build ModelsCompare.exe."
    }

    $releaseDirectory = Join-Path $env:TEMP ("modelscompare-release-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $releaseDirectory | Out-Null
    Copy-Item dist\ModelsCompare.exe $releaseDirectory
    Copy-Item PORTABLE-README.md (Join-Path $releaseDirectory "README.md")
    Compress-Archive `
        -Path (Join-Path $releaseDirectory "*") `
        -DestinationPath dist\modelscompare-windows-x64.zip `
        -Force

    Write-Host "Portable package ready: dist\modelscompare-windows-x64.zip"
}
finally {
    Pop-Location
}
