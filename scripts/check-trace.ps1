# Fails (exit 1) if any acceptance criterion is unmapped, maps to a missing backlog task,
# a required §13 plan document is missing, or an architecture decision (AD-n) has no ADR.
# How to run and change the plan: docs/SOP.md. Decision records: docs/adr/ (index in docs/SOP.md).
$ErrorActionPreference = 'Stop'
$docs = Join-Path $PSScriptRoot '..\docs'
$errors = @()

$required = '01-product-decision.md', '02-mvp-spec.md', '03-technical-design.md',
            '04-validation-plan.md', '05-backlog.md', '06-decision-log.md', 'traceability.md'
foreach ($f in $required) {
    if (-not (Test-Path (Join-Path $docs $f))) { $errors += "Missing plan document: $f" }
}
if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }

$spec    = Get-Content (Join-Path $docs '02-mvp-spec.md') -Raw
$backlog = Get-Content (Join-Path $docs '05-backlog.md') -Raw
$trace   = Get-Content (Join-Path $docs 'traceability.md')

$acs   = [regex]::Matches($spec, '(?m)^\| (AC-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
$tasks = [regex]::Matches($backlog, '(?m)^\| ([DI]-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
if (-not $acs) { $errors += 'No acceptance criteria found in 02-mvp-spec.md' }

foreach ($ac in $acs) {
    $row = $trace | Where-Object { $_ -match "^\| $ac \|" }
    if (-not $row) { $errors += "$ac not mapped in traceability.md"; continue }
    $cols = ($row -split '\|') | ForEach-Object { $_.Trim() }
    # cols: '', AC, design, tasks, eval, ''
    if (-not $cols[2]) { $errors += "$ac has no design section" }
    $refs = [regex]::Matches($cols[3], '[DI]-\d+') | ForEach-Object { $_.Value }
    if (-not $refs) { $errors += "$ac has no backlog task" }
    foreach ($t in $refs) { if ($tasks -notcontains $t) { $errors += "$ac references unknown task $t" } }
}

$design = Get-Content (Join-Path $docs '03-technical-design.md') -Raw
$adrDir = Join-Path $docs 'adr'
$adrText = if (Test-Path $adrDir) { (Get-ChildItem $adrDir -Filter '*.md' | Get-Content -Raw) -join "`n" } else { '' }
$decisions = [regex]::Matches($design, '(?m)^\| (AD-\d+) \|') | ForEach-Object { $_.Groups[1].Value }
foreach ($ad in $decisions) {
    if ($adrText -notmatch "\($ad\)") { $errors += "$ad has no ADR in docs/adr" }
}

if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
Write-Host "PASS $($acs.Count) acceptance criteria mapped to $($tasks.Count) backlog tasks; $($decisions.Count) architecture decisions have ADRs"
