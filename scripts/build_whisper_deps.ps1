# Build the optional whisper dependency bundle.
#
# The full desktop exe ships Vosk only. faster-whisper's inference stack is
# downloaded on demand as this zip and extracted into the vidnote cache dir.
#
# Usage:
#   powershell -File scripts/build_whisper_deps.ps1
#
# Output:
#   build\release\vidnote-whisper-deps-<version>.zip

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = ".\.venv\Scripts\python.exe"
$target = "build\whisper-deps"
$release = "build\release"

$pyproject = Get-Content pyproject.toml -Raw
$version = [regex]::Match($pyproject, 'version = "([^"]+)"').Groups[1].Value
if (-not $version) { throw "Cannot read version from pyproject.toml" }

Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $target, $release | Out-Null

Write-Host "==> Installing whisper dependencies (vidnote $version)"
$packages = @(
    "faster-whisper==1.2.1",
    "ctranslate2==4.8.5",
    "onnxruntime==1.31.1",
    "tokenizers==0.23.3",
    "huggingface-hub==2.4.0",
    "hf-xet==1.8.0",
    "numpy==2.5.4",
    "tqdm==4.70.1",
    "httpx2==2.16.0",
    "httpcore2==2.16.0"
)
& $python -m pip install --target $target --upgrade --only-binary=:all: @packages
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# av + FFmpeg are already packaged in the desktop exe; keep the download slim.
Remove-Item (Join-Path $target "av") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $target "av.libs") -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $target -Filter "av-*.dist-info" -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $target "bin") -Recurse -Force -ErrorAction SilentlyContinue

$zip = Join-Path $release "vidnote-whisper-deps-$version.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Write-Host "==> Compressing $zip"
Compress-Archive -Path "$target\*" -DestinationPath $zip -Force

$total = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Done: $zip ($total MB)"
