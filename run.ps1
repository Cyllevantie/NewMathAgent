param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PythonArgs)
$ErrorActionPreference = 'Stop'
# Missing config must fail with the *useful* message, not Get-Content's "Cannot find path":
# on a fresh machine the file is absent, and this script's own hint below is written for
# exactly that case -- but before the guard it was unreachable. Template ships next to it.
# ASCII only: Windows PowerShell 5.1 reads .ps1 as ANSI/GBK, non-ASCII breaks parsing.
$configPath = Join-Path $PSScriptRoot 'config/runtime.local.json'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw ('Missing config/runtime.local.json. Copy config/runtime.local.json.example to ' +
           'config/runtime.local.json and fill in "python" + "tool_directories" ' +
           '(see docs/ENVIRONMENT.md).')
}
$runtimeConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$projectPython = $runtimeConfig.python
if (-not (Test-Path -LiteralPath $projectPython -PathType Leaf)) {
    throw 'Project Python not found. See docs/ENVIRONMENT.md and config/runtime.local.json.'
}
if (-not $PythonArgs) { $PythonArgs = @('runtime/doctor.py') }
$previousPath = $env:PATH
$previousVenv = $env:VIRTUAL_ENV
$env:VIRTUAL_ENV = Split-Path (Split-Path $projectPython -Parent) -Parent
$toolDirectories = @($runtimeConfig.tool_directories | Where-Object { Test-Path -LiteralPath $_ -PathType Container })
$env:PATH = (@((Split-Path $projectPython -Parent)) + $toolDirectories + @($env:PATH)) -join [IO.Path]::PathSeparator
Push-Location $PSScriptRoot
try {
    & $projectPython @PythonArgs
    $resultCode = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PATH = $previousPath
    $env:VIRTUAL_ENV = $previousVenv
}
exit $resultCode
