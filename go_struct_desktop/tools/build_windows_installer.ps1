[CmdletBinding()]
param(
    [string]$Version = "0.1.0",
    [string]$ReleaseLabel = "Beta 0.1",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$buildStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$payload = Join-Path $projectRoot "release\payload\$Version-$buildStamp"
$workPath = Join-Path $projectRoot "release\build\$Version-$buildStamp"
$installerScript = Join-Path $projectRoot "installer\GO-Struct-Desktop.iss"
$frameIcon = Join-Path $projectRoot "src\go_struct_desktop\assets\icons\frame.ico"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing virtual environment: $python"
}
if (-not (Test-Path -LiteralPath $iscc)) {
    throw "Inno Setup 6 was not found at: $iscc"
}
if (-not (Test-Path -LiteralPath $frameIcon)) {
    throw "Frame icon was not found at: $frameIcon"
}

Push-Location $projectRoot
try {
    & $python -m pip install "PyInstaller>=6.10,<7"
    if ($LASTEXITCODE -ne 0) { throw "Unable to install PyInstaller." }

    if (-not $SkipTests) {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed; installer was not created." }
    }

    & $python -m PyInstaller `
        --noconfirm --clean --windowed `
        --name "GO-Struct-Desktop" `
        --icon $frameIcon `
        --paths "src" `
        --collect-data "go_struct_desktop" `
        --hidden-import "go_struct_desktop.app" `
        --hidden-import "go_struct_desktop.beam_workspace" `
        --hidden-import "go_struct_desktop.truss_workspace" `
        --hidden-import "PySide6.QtSvg" `
        --exclude-module "openseespy" `
        --exclude-module "pymoo" `
        --exclude-module "scipy" `
        --exclude-module "matplotlib" `
        --exclude-module "pytest" `
        --distpath $payload `
        --workpath $workPath `
        --specpath $workPath `
        "src\go_struct_desktop\launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller did not complete successfully." }

    & $iscc "/DSourceRoot=$projectRoot" "/DPayloadRoot=$payload" "/DAppVersion=$Version" "/DReleaseLabel=$ReleaseLabel" $installerScript
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup did not complete successfully." }

    $setup = Join-Path $projectRoot "release\installer\GO-Struct-Desktop-Beta-0.1-Setup.exe"
    if (-not (Test-Path -LiteralPath $setup)) { throw "Installer output was not found: $setup" }
    Write-Host "Installer created: $setup"
}
finally {
    Pop-Location
}
