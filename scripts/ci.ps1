# CI entry point, run locally and by .github/workflows/plan-checks.yml. The plan has no code to
# compile, so the "build" stage checks the documents themselves; the test stage runs the suite.
# Exits 1 if any stage fails. See docs/SOP.md.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$errors = @()
$files = git ls-files -- docs scripts '*.md' | Sort-Object -Unique
$strict = New-Object System.Text.UTF8Encoding($false, $true)

# Build 1: size limit (project rule: files under 500 lines)
foreach ($f in $files) {
    $n = (Get-Content $f | Measure-Object -Line).Lines
    if ($n -gt 500) { $errors += "BUILD $f has $n lines (limit 500)" }
}

# Build 2: encoding (strict UTF-8, no mojibake from a PowerShell 5.1 ANSI round trip)
foreach ($f in $files) {
    try { $text = $strict.GetString([IO.File]::ReadAllBytes((Join-Path $root $f))) }
    catch { $errors += "BUILD $f is not valid UTF-8"; continue }
    if ($text -match ([char]0x00E2 + [char]0x20AC) -or $text -match ([char]0x00C3 + '[' + [char]0x0080 + '-' + [char]0x00BF + ']')) {
        $errors += "BUILD $f contains mojibake (UTF-8 read as ANSI)"
    }
}

# Build 3: relative Markdown links resolve
foreach ($f in ($files | Where-Object { $_ -like '*.md' })) {
    $dir = Split-Path (Join-Path $root $f) -Parent
    foreach ($m in [regex]::Matches((Get-Content $f -Raw -Encoding UTF8), '\]\(([^)\s#]+)(#[^)]*)?\)')) {
        $target = $m.Groups[1].Value
        if ($target -match '^(https?|mailto):') { continue }
        if (-not (Test-Path (Join-Path $dir $target))) { $errors += "BUILD $f links to missing $target" }
    }
}

# Build 4: no secrets or env files committed (03 §6 Secrets and supply chain)
$leakPattern = 'AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|(api[_-]?key|secret|password)\s*[:=]\s*[''"][^''"]{8,}'
foreach ($f in (git ls-files)) {
    if ($f -match '(^|/)\.env(\.|$)') { $errors += "BUILD env file committed: $f" }
    elseif ((Get-Content $f -Raw -Encoding UTF8) -match $leakPattern) { $errors += "BUILD possible secret in $f" }
}
if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" } }
else { Write-Host "PASS build: $($files.Count) files within size, UTF-8, link and secret checks" }

# Test suite
foreach ($s in 'check-trace', 'check-verification', 'cost-model') {
    & powershell -NoProfile -File (Join-Path $PSScriptRoot "$s.ps1") | Select-Object -Last 1 | Write-Host
    if ($LASTEXITCODE -ne 0) { $errors += "TEST $s exit $LASTEXITCODE" }
}

# Evaluation tests run in a project venv; never install into the global Python.
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $errors += 'TEST eval: python not found' }
    else {
        & python -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { $errors += 'TEST eval: venv creation failed' }
    }
}
if (-not (Test-Path $python)) { $errors += 'TEST eval: project venv missing' }
else {
    $ErrorActionPreference = 'Continue'
    # pip skips hash checks for packages already installed, so reinstall every pinned wheel each run.
    $global:LASTEXITCODE = -1
    $install = & $python -m pip install --disable-pip-version-check --force-reinstall --no-deps --require-hashes -r (Join-Path $PSScriptRoot 'eval/requirements-render.txt') 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { $install | Write-Host; $errors += 'TEST render: dependency installation failed' }
    else { Write-Host 'PASS render dependency install: every pinned wheel reinstalled with --require-hashes' }
    $global:LASTEXITCODE = -1
    $deps = & $python -c "import reportlab, pypdfium2, PIL" 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { $deps | Write-Host; $errors += 'TEST render: required dependencies not importable' }
    foreach ($suite in 'generate', 'render', 'render_hidden', 'label_kit', 'label_rounds') {
        $global:LASTEXITCODE = -1
        $out = & $python -m unittest discover -s (Join-Path $PSScriptRoot 'eval') -p "test_$suite.py" 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
        Write-Host "eval $suite unittest: $(($out | Select-String '^Ran ') -join '') $(($out | Select-Object -Last 1))"
        if ($code -ne 0) { $out | Write-Host; $errors += "TEST eval $suite unittest exit $code" }
        elseif (-not ($out -match '^Ran [1-9]')) { $errors += "TEST eval $suite`: no tests ran" }
    }
    $ErrorActionPreference = 'Stop'
}

if ($errors) {
    $errors | Where-Object { $_ -like 'TEST*' } | ForEach-Object { Write-Host "FAIL $_" }
    Write-Host "CI FAIL ($($errors.Count) problems)"; exit 1
}
Write-Host 'CI PASS'
