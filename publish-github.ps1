# 在 GitHub 创建仓库并推送（需已安装 GitHub CLI 且 gh auth login）
# 用法: .\publish-github.ps1
# 或指定仓库名: .\publish-github.ps1 -RepoName video-promo-pipeline -Public

param(
    [string]$RepoName = "video-promo-pipeline",
    [switch]$Public
)

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-Host "未安装 GitHub CLI。请先安装: winget install GitHub.cli"
    Write-Host "然后执行: gh auth login"
    Write-Host ""
    Write-Host "或手动在 https://github.com/new 创建空仓库 $RepoName ，再执行:"
    Write-Host "  git remote add origin https://github.com/<你的用户名>/$RepoName.git"
    Write-Host "  git branch -M main"
    Write-Host "  git push -u origin main"
    exit 1
}

$visibility = if ($Public) { "--public" } else { "--private" }
gh repo create $RepoName $visibility --source=. --remote=origin --push
Write-Host "完成。仓库地址:"
gh repo view --web 2>$null
