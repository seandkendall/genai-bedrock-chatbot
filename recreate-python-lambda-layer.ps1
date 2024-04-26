# Remove the existing python directory
$pythonDir = Join-Path -Path ".\cdk\lambda_functions\python_layer\python" -Resolve
if (Test-Path $pythonDir) {
    Remove-Item -Recurse -Force $pythonDir
}

# Install boto3 and PyJWT in the python directory
$pipPath = (Get-Command pip).Source
$pipArgs = @(
    "install",
    "boto3",
    "PyJWT",
    "-t",
    ".\cdk\lambda_functions\python_layer\python",
    "--upgrade"
)
& $pipPath $pipArgs