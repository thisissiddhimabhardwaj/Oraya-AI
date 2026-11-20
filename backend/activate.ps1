# Dot-source from any directory: . "D:\New folder\backend\activate.ps1"
$orayaRoot = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot\.venv\Scripts\Activate.ps1"
$env:PATH = "$orayaRoot\.tools\bin\ffmpeg;$env:PATH"
Set-Location $PSScriptRoot
