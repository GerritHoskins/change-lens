# CI entry point, run locally and by .github/workflows/plan-checks.yml. The "build" stage checks the
# tracked documents and files; the test stage runs the plan checks, the evaluation, release and
# playbook tests, and the backend unit tests. The Flutter app (Codemagic) and the backend integration
# tests (backend-integration.yml) are not run here; backend/tests/dataset needs the private dataset.
# Exits 1 if any stage fails. See docs/SOP.md.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$errors = @()
# Binary files (images, PDFs) are tracked too, but the line and UTF-8 checks only apply to text.
$files = git ls-files -- docs scripts '*.md' | Where-Object { $_ -notmatch '\.(png|jpe?g|gif|webp|ico|pdf)$' } | Sort-Object -Unique
$strict = New-Object System.Text.UTF8Encoding($false, $true)

# Build 1: size limit (project rule: files under 500 lines). Hand-written backend and app code counts
# too; the localisation classes Flutter generates from the ARB files are not hand-written.
$codeFiles = git ls-files -- 'backend/*.py' 'app/lib/*.dart' | Where-Object { $_ -notmatch '^app/lib/l10n/app_localizations(_[a-z]+)?\.dart$' }
foreach ($f in @($files) + @($codeFiles)) {
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
else { Write-Host "PASS build: $($files.Count) files within size, UTF-8, link and secret checks; $(@($codeFiles).Count) code files within size" }

# Test suite
foreach ($s in 'check-trace', 'check-verification', 'cost-model') {
    & powershell -NoProfile -File (Join-Path $PSScriptRoot "$s.ps1") | Select-Object -Last 1 | Write-Host
    if ($LASTEXITCODE -ne 0) { $errors += "TEST $s exit $LASTEXITCODE" }
}

# Evaluation tests run in a project venv; never install into the global Python.
$env:PYTHONDONTWRITEBYTECODE = '1'
# The pinned wheels are for one CPython minor version; a venv made by another one cannot install them.
$pinned = '3.14'
function Get-VenvPython($exe) { & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null }
function Get-VenvHint($dir, $exe) { "$dir uses Python $(Get-VenvPython $exe), the pins need $pinned; delete $dir and run: py -$pinned -m venv $dir" }
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $errors += 'TEST eval: python not found' }
    else {
        & python -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { $errors += 'TEST eval: venv creation failed' }
    }
}
if (-not (Test-Path $python)) { $errors += 'TEST eval: project venv missing' }
elseif ((Get-VenvPython $python) -ne $pinned) { $errors += "TEST eval: $(Get-VenvHint '.venv' $python)" }
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
    # Each suite: its label, the folder unittest discovers in, and the file pattern. The release and
    # playbook suites use the standard library only; they run here so no test file is left out of CI.
    $suites = @()
    foreach ($s in 'generate', 'render', 'render_hidden', 'label_kit', 'label_rounds', 'split', 'fresh_cohort') {
        $suites += , @("eval $s", 'scripts/eval', "test_$s.py")
    }
    $suites += , @('release', 'scripts/release', 'test_*.py')
    $suites += , @('playbooks', '.paseo/plugins/playbooks/tests', 'test_*.py')
    foreach ($suite in $suites) {
        $label, $dir, $pattern = $suite
        $global:LASTEXITCODE = -1
        $out = & $python -m unittest discover -s (Join-Path $root $dir) -p $pattern 2>&1 | ForEach-Object { "$_" }
        $exit = $LASTEXITCODE
        Write-Host "$label unittest: $(($out | Select-String '^Ran ') -join '') $(($out | Select-Object -Last 1))"
        if ($exit -ne 0) { $out | Write-Host; $errors += "TEST $label unittest exit $exit" }
        elseif (-not ($out -match '^Ran [1-9]')) { $errors += "TEST $label`: no tests ran" }
    }
    $ErrorActionPreference = 'Stop'
}

# Backend unit tests (I-22) in their own venv; integration tests need Docker and run locally (backend/README.md).
$bpy = Join-Path $root 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path $bpy) -and (Get-Command python -ErrorAction SilentlyContinue)) { & python -m venv (Join-Path $root 'backend/.venv') }
if (-not (Test-Path $bpy)) { $errors += 'TEST backend: venv missing' }
elseif ((Get-VenvPython $bpy) -ne $pinned) { $errors += "TEST backend: $(Get-VenvHint 'backend/.venv' $bpy)" }
else {
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = -1
    $install = & $bpy -m pip install --disable-pip-version-check --force-reinstall --no-deps --require-hashes -r backend/requirements.txt -r backend/requirements-test.txt 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { $install | Write-Host; $errors += 'TEST backend: dependency installation failed' }
    $global:LASTEXITCODE = -1
    $out = & $bpy -m pytest backend/tests/unit -q -c backend/pytest.ini 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    Write-Host "backend unit pytest: $($out | Select-Object -Last 1)"
    if ($code -ne 0) { $out | Write-Host; $errors += "TEST backend unit pytest exit $code" }
    elseif (-not ($out -match '^[1-9][0-9]* passed')) { $errors += 'TEST backend: no tests ran' }
    $ErrorActionPreference = 'Stop'
}

if ($errors) {
    $errors | Where-Object { $_ -like 'TEST*' } | ForEach-Object { Write-Host "FAIL $_" }
    Write-Host "CI FAIL ($($errors.Count) problems)"; exit 1
}
Write-Host 'CI PASS'
