@echo off
set ADB=C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe

echo [*] Tapping URL bar...
%ADB% shell input tap 540 150
timeout /t 1 >nul

echo [*] Selecting all...
%ADB% shell input keyevent 29
%ADB% shell input keyevent 31
timeout /t 1 >nul

echo [*] Typing JavaScript...
%ADB% shell input text "javascript:prompt('cookies',document.cookie)"
timeout /t 1 >nul

echo [*] Pressing Enter...
%ADB% shell input keyevent 66

echo [+] Check phone for prompt with cookies!
pause
