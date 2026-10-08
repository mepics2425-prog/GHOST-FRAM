$ErrorActionPreference = "Stop"
$project = "C:\project\GHOST FARM"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Copy-Item "$here\README.md" "$project\README.md" -Force
New-Item -ItemType Directory -Path "$project\docs\assets" -Force | Out-Null
Copy-Item "$here\docs\architecture.md" "$project\docs\architecture.md" -Force
Copy-Item "$here\docs\detection-spec.md" "$project\docs\detection-spec.md" -Force
Copy-Item "$here\docs\assets\*" "$project\docs\assets\" -Force

Write-Host ""
Write-Host "GHOST FARM visual docs installed."
Write-Host ""
Write-Host "Next commands:"
Write-Host "cd `"C:\project\GHOST FARM`""
Write-Host "git add README.md docs"
Write-Host "git commit -m `"Add real game screenshots and architecture docs`""
Write-Host "git push"
