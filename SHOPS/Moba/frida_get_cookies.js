/*
 * Frida script to get cookies from Android WebView/Chrome
 * Run: frida -U -f com.android.chrome -l frida_get_cookies.js
 */

setTimeout(function() {
    Java.perform(function() {
        console.log("[*] Getting cookies via CookieManager...");

        try {
            var CookieManager = Java.use("android.webkit.CookieManager");
            var instance = CookieManager.getInstance();

            var url = "https://moba.ru/";
            var cookies = instance.getCookie(url);

            console.log("\n[COOKIES] " + url);
            console.log(cookies);
            console.log("\n[END]");

        } catch(e) {
            console.log("[!] CookieManager error: " + e);
        }

        // Also try Chrome's internal cookie store
        try {
            var CookiesFetcher = Java.use("org.chromium.net.impl.CronetUrlRequestContext");
            console.log("[*] Found Cronet");
        } catch(e) {
            // Expected - Chrome uses different classes
        }
    });
}, 2000);
