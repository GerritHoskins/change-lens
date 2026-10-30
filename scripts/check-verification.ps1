# Fails (exit 1) until every acceptance criterion has an independent verification record and
# every review finding is resolved or explicitly accepted. Mission criteria; see docs/SOP.md.
$ErrorActionPreference = 'Stop'
$docs = Join-Path $PSScriptRoot '..\docs'
$errors = @()
$authors = 'author', 'planner', 'claude-main', 'self'

$spec = Get-Content (Join-Path $docs '02-mvp-spec.md') -Raw
$acs  = [regex]::Matches($spec, '(?m)^\| (AC-\d+) \|') | ForEach-Object { $_.Groups[1].Value }

# 1. Independent verification: | AC | Verifier | Method | Result | Evidence |
$vfile = Join-Path $docs 'verification.md'
if (-not (Test-Path $vfile)) { $errors += 'Missing docs/verification.md' } else {
    $vrows = Get-Content $vfile
    foreach ($ac in $acs) {
        $row = $vrows | Where-Object { $_ -match "^\| $ac \|" }
        if (-not $row) { $errors += "$ac has no independent verification record"; continue }
        $c = ($row -split '\|') | ForEach-Object { $_.Trim() }
        if (-not $c[2] -or $authors -contains $c[2].ToLower()) { $errors += "$ac verifier is missing or is the author" }
        if ($c[4] -notin 'pass', 'fail', 'accepted-gap') { $errors += "$ac result must be pass, fail or accepted-gap" }
        if ($c[4] -eq 'fail') { $errors += "$ac failed independent verification" }
        if (-not $c[5]) { $errors += "$ac has no verification evidence" }
    }
}

# 2. Review ledger: | ID | Source | Finding | Severity | Status | Resolution |
$lfile = Join-Path $docs 'review-ledger.md'
if (-not (Test-Path $lfile)) { $errors += 'Missing docs/review-ledger.md' } else {
    $lrows = Get-Content $lfile | Where-Object { $_ -cmatch '^\| [A-Z]+-\d+ \|' }
    if (-not $lrows) { $errors += 'No review findings recorded in docs/review-ledger.md' }
    foreach ($r in $lrows) {
        $c = ($r -split '\|') | ForEach-Object { $_.Trim() }
        if ($c[5] -notin 'resolved', 'accepted') { $errors += "$($c[1]) status is '$($c[5])', not resolved or accepted" }
        if (-not $c[6]) { $errors += "$($c[1]) has no resolution reference or acceptance reason" }
    }
}

if ($errors) { $errors | ForEach-Object { Write-Host "FAIL $_" }; exit 1 }
Write-Host "PASS $($acs.Count) acceptance criteria independently verified; $($lrows.Count) review findings closed"
