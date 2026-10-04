$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH = "$PSScriptRoot\.build-tools;$PSScriptRoot\.vendor"
python -m PyInstaller --noconfirm --onedir --windowed --name LaTexTEx --icon app.ico --add-data "assets\fontawesome;assets\fontawesome" --paths .vendor --exclude-module numpy --exclude-module pandas --exclude-module scipy --exclude-module pytest --exclude-module matplotlib --exclude-module torch --exclude-module tensorflow --exclude-module IPython --exclude-module cv2 --exclude-module openpyxl project_studio.py
if ($LASTEXITCODE -ne 0) { throw 'Construction échouée.' }
$destination = Join-Path $PSScriptRoot 'dist\LaTexTEx'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'app.ico') -Destination $destination
New-Item -ItemType Directory -Path (Join-Path $destination 'documents') -Force | Out-Null
foreach ($name in @('Bienvenue.tex', 'Bienvenue.pdf')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "documents\$name") -Destination (Join-Path $destination 'documents')
}
