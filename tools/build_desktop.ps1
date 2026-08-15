[CmdletBinding()]
param(
    [switch]$Clean
)

$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $ProjectRoot "src\desktop_main.py"
$SourcePath = Join-Path $ProjectRoot "src"
$BuildRoot = Join-Path $ProjectRoot "build\desktop"
$WorkPath = Join-Path $BuildRoot "work"
$SpecPath = Join-Path $BuildRoot "spec"
$DistributionPath = Join-Path $ProjectRoot "dist"
$Executable = Join-Path $DistributionPath "Hypatia\Hypatia.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Hypatia virtual environment was not found at $Python."
}

if (-not (Test-Path -LiteralPath $EntryPoint -PathType Leaf)) {
    throw "Desktop entry point was not found at $EntryPoint."
}

& $Python -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is required. Run '$Python -m pip install -r requirements-desktop-build.txt'."
}

if ($Clean) {
    foreach ($TargetPath in @($BuildRoot, (Join-Path $DistributionPath "Hypatia"))) {
        if (Test-Path -LiteralPath $TargetPath) {
            Remove-Item -LiteralPath $TargetPath -Recurse -Force
        }
    }
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name Hypatia `
    --paths $SourcePath `
    --distpath $DistributionPath `
    --workpath $WorkPath `
    --specpath $SpecPath `
    $EntryPoint

if ($LASTEXITCODE -ne 0) {
    throw "Hypatia desktop package build failed."
}

if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Hypatia desktop package did not produce $Executable."
}

Write-Host "Desktop package created: $Executable"
