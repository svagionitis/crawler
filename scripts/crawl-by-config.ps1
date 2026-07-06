param (
    [string]$ConfigPath = "config/news-sites-gr.json"
)

# Resolve config path relative to the script directory if it is not absolute
if (-not [System.IO.Path]::IsPathRooted($ConfigPath)) {
    # $PSScriptRoot is the directory of this script (e.g., repository/scripts)
    # The config directory is in the repository root, which is one level up from scripts
    $ConfigPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($PSScriptRoot, "..", $ConfigPath))
}

if (-not (Test-Path $ConfigPath)) {
    Write-Error "Configuration file not found: $ConfigPath"
    exit 1
}

# Resolve repository root directory
$RepoRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($PSScriptRoot, ".."))

# Change directory to the repository root so the python script runs in the correct context
Set-Location -Path $RepoRoot

# Execute the python crawler with the configuration file, forwarding any additional parameters
python.exe .\crawler_app.py --config $ConfigPath $args
