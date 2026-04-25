<#
.SYNOPSIS
    将 Markdown 文件中的 LaTeX 行间公式语法 \[ \] 转换为 Obsidian 识别的 $$ $$。
#>

param (
    [string]$SearchPath = ".", # 默认处理当前目录
    [switch]$Recursive = $true # 默认递归子目录
)

# 获取所有 .md 文件
$files = Get-ChildItem -Path $SearchPath -Filter "*.md" -Recurse:$Recursive

Write-Host "开始扫描 Markdown 文件..." -ForegroundColor Cyan

foreach ($file in $files) {
    # 以 UTF8 (无 BOM) 编码读取内容，防止中文乱码
    $content = Get-Content -Path $file.FullName -Raw -Encoding utf8
    
    # 使用正则表达式匹配 \[ 和 \]
    # \s*? 用于处理可能存在的空格或换行
    $newContent = $content -replace '\\\[', '$$' -replace '\\\]', '$$'

    if ($content -ne $newContent) {
        # 只有在发生变化时才写入文件，保护硬盘寿命
        Set-Content -Path $file.FullName -Value $newContent -Encoding utf8
        Write-Host "已修复: $($file.FullName)" -ForegroundColor Green
    }
}

Write-Host "清洗完成！" -ForegroundColor Cyan