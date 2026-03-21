$Repo = "https://github.com/dozybot001/Intent.git"

function Info($msg)  { Write-Host "[intent] $msg" -ForegroundColor Cyan }
function Err($msg)   { Write-Host "[intent] $msg" -ForegroundColor Red; exit 1 }

# --- Python ---
$py = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $null = & $cmd --version 2>$null
        if ($LASTEXITCODE -eq 0) { $py = $cmd; break }
    } catch {}
}
if (-not $py) { Err "Python not found. Install Python 3.9+ first." }

$ver = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$major, $minor = $ver -split '\.'
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 9)) {
    Err "Python $ver found, but 3.9+ is required."
}
Info "Python $ver"

# --- pipx ---
$hasPipx = $false
try { $null = & pipx --version 2>$null; if ($LASTEXITCODE -eq 0) { $hasPipx = $true } } catch {}

if (-not $hasPipx) {
    Info "Installing pipx..."
    & $py -m pip install --user pipx 2>$null
    if ($LASTEXITCODE -ne 0) { & $py -m pip install pipx }
    & $py -m pipx ensurepath 2>$null
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
}
Info "pipx $(& pipx --version)"

# --- intent-cli ---
Info "Installing intent-cli..."
& pipx install "intent-cli @ git+$Repo" --force

Info "Done! Run 'itt version' to verify."
Info "To add the agent skill: npx skills add dozybot001/Intent -g --all"
