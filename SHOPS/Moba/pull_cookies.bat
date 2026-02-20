@echo off
set ADB=C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe
set DEST=C:\Users\User\Documents\Revers\Site\Moba

echo [*] Copying Chrome cookies...
%ADB% shell "su -c 'cp /data/data/com.android.chrome/app_chrome/Default/Cookies /sdcard/cookies.db'"
%ADB% shell "su -c 'chmod 644 /sdcard/cookies.db'"

echo [*] Pulling to PC...
%ADB% pull /sdcard/cookies.db "%DEST%\cookies.db"

echo [*] Cleanup...
%ADB% shell "rm /sdcard/cookies.db"

echo [+] Done! cookies.db saved to %DEST%
