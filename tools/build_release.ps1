$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$releaseRoot = Join-Path $projectRoot 'output\release'
$web = Join-Path $projectRoot 'app\web'
$assets = Join-Path $projectRoot 'app\assets'
$skills = Join-Path $projectRoot 'skills'
$webData = @()
Get-ChildItem -LiteralPath $web -Force | Where-Object Name -ne 'node_modules' | ForEach-Object {
    $webData += '--add-data'
    $destination = if ($_.PSIsContainer) { "app/web/$($_.Name)" } else { 'app/web' }
    $webData += "$($_.FullName);$destination"
}

if (-not (Test-Path -LiteralPath $python)) {
    throw '先在 .venv 中安装 requirements.txt 和 requirements-build.txt。'
}

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Push-Location $projectRoot
try {
    & $python -m PyInstaller `
        --noconfirm --clean --onefile --windowed --log-level WARN `
        --name LearningDex `
        --icon (Join-Path $assets 'learndex.ico') `
        $webData `
        --add-data "${assets};app/assets" `
        --add-data "${skills};skills" `
        --collect-all webview `
        --collect-all yt_dlp `
        --collect-all imageio_ffmpeg `
        --collect-all ctranslate2 `
        --collect-all faster_whisper `
        --collect-all litellm `
        --collect-submodules tiktoken_ext `
        --exclude-module personal `
        --exclude-module tests `
        --distpath (Join-Path $releaseRoot 'dist') `
        --workpath (Join-Path $releaseRoot 'build') `
        --specpath (Join-Path $releaseRoot 'spec') `
        (Join-Path $projectRoot 'run_learndex.py')
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败：$LASTEXITCODE" }
    & $python (Join-Path $PSScriptRoot 'verify_release.py') (Join-Path $releaseRoot 'dist\LearningDex.exe')
    if ($LASTEXITCODE -ne 0) { throw 'EXE 资源和隐私校验失败。' }
}
finally {
    Pop-Location
}
