# Install or upgrade the Intent CLI (`itt`) in an isolated environment.
# Uses uv or pipx when available, otherwise a private virtual environment.
# Errors are thrown instead of calling `exit`, so `irm ... | iex` never closes
# the caller's PowerShell window. Set $env:INTENT_VERSION to pin a release.

function Install-IntentCli {
    # Native-command failures are checked through $LASTEXITCODE below; "Stop"
    # would turn harmless stderr output into errors on Windows PowerShell 5.1.
    $ErrorActionPreference = "Continue"
    $Repo = "https://github.com/dozybot001/Intent.git"
    $ReleaseTag = if ($env:INTENT_VERSION) { $env:INTENT_VERSION } else { "v7.5.1" }
    # Releases before 7.1.0 were published under the distribution name intent-cli.
    $Dist = if ($ReleaseTag -match '^v([0-6]\.|7\.0\.)') { "intent-cli" } else { "intent-history" }
    $Spec = "$Dist @ git+$Repo@$ReleaseTag"
    $Home_ = if ($env:INTENT_HOME) { $env:INTENT_HOME } else { Join-Path $env:LOCALAPPDATA "Intent" }
    $VenvDir = Join-Path $Home_ "venv"

    function Info($msg) { Write-Host "[intent] $msg" -ForegroundColor Cyan }
    function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

    if (-not (Test-Command "git")) { throw "Git is required to download Intent $ReleaseTag. Install Git, then retry." }

    $py = $null
    foreach ($cmd in @("python", "python3", "py")) {
        if (Test-Command $cmd) {
            & $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { $py = $cmd; break }
        }
    }
    if (-not $py) { throw "Python 3.9+ not found. Install it from https://www.python.org/downloads/ (enable 'Add to PATH'), then retry." }
    Info "Python $(& $py -c 'import platform; print(platform.python_version())')"

    # Intent 7.0 was installed as intent-cli. Remove that install (only one that
    # provides `itt`) so a stale second `itt` cannot come back on a later upgrade.
    if ($Dist -eq "intent-history") {
        if (Test-Command "uv") {
            $tool = $null; $legacy = $false
            foreach ($line in @(& uv tool list 2>$null)) {
                if ($line -match '^([^-\s]\S*)') { $tool = $Matches[1] }
                elseif ($tool -eq "intent-cli" -and $line -match '^- itt(\.exe)?$') { $legacy = $true }
            }
            if ($legacy) {
                Info "Removing the previous intent-cli installation (uv)..."
                & uv tool uninstall intent-cli *> $null
            }
        }
        if (Test-Command "pipx") {
            try {
                $old = ((& pipx list --json 2>$null) -join "`n" | ConvertFrom-Json).venvs.'intent-cli'
                $apps = @($old.metadata.main_package.apps)
                if ($old -and (($apps -contains "itt") -or ($apps -contains "itt.exe"))) {
                    Info "Removing the previous intent-cli installation (pipx)..."
                    & pipx uninstall intent-cli *> $null
                }
            } catch { }
        }
    }

    if (Test-Command "uv") {
        Info "Installing Intent $ReleaseTag with uv..."
        & uv tool install --force "$Spec"
    } elseif (Test-Command "pipx") {
        Info "Installing Intent $ReleaseTag with pipx..."
        & pipx install --force "$Spec"
    } else {
        Info "uv and pipx not found; installing Intent $ReleaseTag into $VenvDir..."
        & $py -m venv --clear "$VenvDir"
        if ($LASTEXITCODE -ne 0) { throw "Could not create a virtual environment in $VenvDir." }
        & (Join-Path $VenvDir "Scripts\python.exe") -m pip install --quiet --disable-pip-version-check "$Spec"
        $scripts = Join-Path $VenvDir "Scripts"
        $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        if (-not (($userPath -split ";") -contains $scripts)) {
            [Environment]::SetEnvironmentVariable("PATH", "$scripts;$userPath", "User")
            Info "Added $scripts to your user PATH (open a new terminal to use it)."
        }
        $env:PATH = "$scripts;$env:PATH"
    }
    if ($LASTEXITCODE -ne 0) { throw "Installing Intent $ReleaseTag failed." }

    & itt version *> $null
    if ($LASTEXITCODE -ne 0) { throw "Installation finished, but 'itt version' failed. Open a new terminal and retry." }
    Info "Installed Intent $ReleaseTag. Next: run 'itt init' in a project."
    Info "Agent skill (needs Node.js): npx skills add dozybot001/Intent -g -a claude-code -a codex"
}

try {
    Install-IntentCli
} catch {
    Write-Host "[intent] $($_.Exception.Message)" -ForegroundColor Red
}
