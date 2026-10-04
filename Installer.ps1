$ErrorActionPreference = 'Stop'
$bundlePath = Join-Path $PSScriptRoot 'dist\LaTexTEx'
if (-not (Test-Path -LiteralPath (Join-Path $bundlePath 'LaTexTEx.exe'))) {
    throw 'LaTexTEx.exe est absent. Construisez le logiciel avant de lancer cet installateur.'
}
$appPath = Join-Path $env:LOCALAPPDATA 'Programs\LaTexTEx'
New-Item -ItemType Directory -Path $appPath -Force | Out-Null
foreach ($name in @('LaTexTEx.exe', '_internal', 'app.ico')) {
    Copy-Item -LiteralPath (Join-Path $bundlePath $name) -Destination $appPath -Recurse -Force
}
$documentsPath = Join-Path $appPath 'documents'
New-Item -ItemType Directory -Path $documentsPath -Force | Out-Null
foreach ($name in @('Bienvenue.tex', 'Bienvenue.pdf')) {
    $targetPath = Join-Path $documentsPath $name
    if (-not (Test-Path -LiteralPath $targetPath)) {
        Copy-Item -LiteralPath (Join-Path $bundlePath "documents\$name") -Destination $targetPath
    }
}
$statePath = Join-Path $appPath 'workspace.json'
if (-not (Test-Path -LiteralPath $statePath)) {
    $stateJson = @{ recent = @((Join-Path $appPath 'documents\Bienvenue.tex'), (Join-Path $appPath 'documents\Bienvenue.pdf')) } | ConvertTo-Json
    [IO.File]::WriteAllText($statePath, $stateJson, (New-Object Text.UTF8Encoding($false)))
}
$shellObject = New-Object -ComObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath('Desktop')
$menuPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'LaTexTEx'
New-Item -ItemType Directory -Path $menuPath -Force | Out-Null
foreach ($shortcutPath in @((Join-Path $desktopPath 'LaTexTEx.lnk'), (Join-Path $menuPath 'LaTexTEx.lnk'))) {
    $shortcut = $shellObject.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $appPath 'LaTexTEx.exe'
    $shortcut.WorkingDirectory = $appPath
    $shortcut.IconLocation = (Join-Path $appPath 'LaTexTEx.exe') + ',0'
    $shortcut.Description = 'Éditeur LaTeX local avec compilation et aperçu PDF'
    $shortcut.Save()
}
Write-Output "Application installée : $appPath"
Write-Output "Raccourci Desktop : $(Join-Path $desktopPath 'LaTexTEx.lnk')"
Write-Output "Raccourci Démarrer : $(Join-Path $menuPath 'LaTexTEx.lnk')"
