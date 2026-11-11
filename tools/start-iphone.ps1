param([Parameter(Mandatory = $true)][string]$LanIp)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    # No external tunnel, certificate trust installation, or firewall changes.
    python -m app.phone_gateway --lan-ip $LanIp --serve-ca
} finally {
    Pop-Location
}
