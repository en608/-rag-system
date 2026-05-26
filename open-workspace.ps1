# 在 Cursor 中打开本项目的 RAG 工作区
$workspaceFile = "D:\cursor\project\rag-system.code-workspace"

if (-not (Test-Path $workspaceFile)) {
    Write-Error "找不到工作区文件: $workspaceFile"
    exit 1
}

$cursorCmd = Get-Command cursor -ErrorAction SilentlyContinue
if ($cursorCmd) {
    & cursor $workspaceFile
    Write-Host "已启动 Cursor 并打开工作区: $workspaceFile"
} else {
    Write-Host "未找到 cursor 命令，请手动操作："
    Write-Host "  Cursor -> 文件 -> 打开工作区来自文件 -> 选择:"
    Write-Host "  $workspaceFile"
    Start-Process $workspaceFile
}
