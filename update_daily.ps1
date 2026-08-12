# Ежедневное обновление: парс пищевых категорий -> Parquet -> данные для сайта -> публикация.
# Запуск вручную или из Планировщика Windows:
#   powershell -ExecutionPolicy Bypass -File update_daily.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$log = "output\run_daily_$(Get-Date -Format yyyyMMdd).log"

python parse_food_categories.py *>> $log
if ($LASTEXITCODE -ne 0) { Add-Content $log 'FAIL: parse'; exit 1 }

$dir = Get-ChildItem output -Directory -Filter 'food-*' | Sort-Object Name | Select-Object -Last 1
python export_parquet.py $dir.FullName *>> $log
python build_site_data.py *>> $log
if ($LASTEXITCODE -ne 0) { Add-Content $log 'FAIL: build'; exit 1 }

# Публикация сайта: ветка gh-pages целиком из web/ (без роста истории).
# Работает только если настроен remote origin (git remote add origin <url>).
$hasRemote = (git remote) -contains 'origin'
if ($hasRemote) {
    git --work-tree=web add --all
    $tree = git --work-tree=web write-tree
    git read-tree HEAD  # вернуть индекс основной ветки
    $commit = git commit-tree $tree -m "site data $(Get-Date -Format yyyy-MM-dd)"
    git update-ref refs/heads/gh-pages $commit
    git push -f origin gh-pages *>> $log
    Add-Content $log 'published gh-pages'
} else {
    Add-Content $log 'no remote origin - публикация пропущена'
}
Add-Content $log "OK $(Get-Date)"
