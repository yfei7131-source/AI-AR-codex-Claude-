param(
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$Session,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Lceda,
    [ValidateSet('csv','xlsx')][string]$Format = 'csv',
    [switch]$BasisOnly
)

$ErrorActionPreference = 'Stop'
$boards = [ordered]@{
    'M-MAIN-L' = '4d38590959875927'
    'M-OPT-BRIDGE' = 'e00fbca5c08cc114'
    'M-AUD-R' = 'e98944c2045546cf'
}
$script = Join-Path $PSScriptRoot 'export_native_bom.js'
$exported = 0
New-Item -ItemType Directory -Path $Output | Out-Null
foreach ($board in $boards.Keys) {
    $root = $boards[$board]
    easyeda --project $Project doc switch $root --json 1> "$Output/$board.switch.json" 2> "$Output/$board.switch.stderr.log"
    if ($LASTEXITCODE -ne 0) {
        Write-Output "$board BLOCKED (cannot switch to root)"
        continue
    }
    $body = @{ projectId = $Project; rootPageId = $root; board = $board; fileType = $Format; basisOnly = $BasisOnly.IsPresent } |
        ConvertTo-Json -Compress
    $responseFile = "$Output/$board.response.json"
    & $Lceda invoke --session $Session --ext-uuid eda --args $body --code-file $script --timeout 18000 2> "$Output/$board.stderr.log" |
        Set-Content -LiteralPath $responseFile -Encoding utf8
    $raw = Get-Content -LiteralPath $responseFile -Raw -ErrorAction SilentlyContinue
    if (-not $raw) {
        Write-Output "$board BLOCKED (SDK returned no response)"
        continue
    }
    $result = $raw | ConvertFrom-Json
    if ($result.ok -ne $true -or $result.value.projectId -ne $Project -or
        $result.value.rootPageId -ne $root -or $result.value.board -ne $board -or -not $result.value.base64) {
        Write-Output "$board BLOCKED ($($result.error.code))"
        continue
    }
    $bytes = [Convert]::FromBase64String($result.value.base64)
    if ($bytes.Length -ne $result.value.size) {
        throw "$board native BOM size did not match the SDK receipt"
    }
    [IO.File]::WriteAllBytes((Join-Path (Resolve-Path $Output).Path "$board.$Format"), $bytes)
    $exported++
    Write-Output "$board EXPORTED ($($bytes.Length) bytes)"
}
if ($exported -ne $boards.Count) { exit 2 }
