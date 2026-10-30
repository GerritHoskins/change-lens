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

# Evaluation generator tests (docs/07-eval-dataset.md, D-6); standard library only
$env:PYTHONDONTWRITEBYTECODE = '1'
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $errors += 'TEST eval: python not found' }
else {
    $ErrorActionPreference = 'Continue'   # unittest reports on stderr; PowerShell 5.1 would treat that as an error
    $global:LASTEXITCODE = -1             # so a failed launch can never reuse the previous script's 0
    $out = & python -m unittest discover -s (Join-Path $PSScriptRoot 'eval') 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Write-Host "eval unittest: $(($out | Select-String '^Ran ') -join '') $(($out | Select-Object -Last 1))"
    if ($code -ne 0) { $out | Write-Host; $errors += "TEST eval unittest exit $code" }
    elseif (-not ($out -match '^Ran [1-9]')) { $errors += 'TEST eval: no tests ran' }
}

if ($errors) {
    $errors | Where-Object { $_ -like 'TEST*' } | ForEach-Object { Write-Host "FAIL $_" }
    Write-Host "CI FAIL ($($errors.Count) problems)"; exit 1
}
Write-Host 'CI PASS'
