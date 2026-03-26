@echo off
chcp 65001 >nul
echo 清理藏经阁缓存...

taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq 藏经阁*" 2>nul
timeout /t 1 /nobreak >nul

rd /s /q "data\webview_storage\EBWebView\Default\Cache" 2>nul
rd /s /q "data\webview_storage\EBWebView\Default\Code Cache" 2>nul
rd /s /q "data\webview_storage\EBWebView\Default\GPUCache" 2>nul

echo 缓存已清理
echo 现在可以重新打开藏经阁.bat
pause
