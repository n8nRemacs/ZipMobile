/*
 * Frida script to capture cookies from Chrome browser
 * Usage: frida -U -f com.android.chrome -l capture_cookies.js
 */

Java.perform(function() {
    console.log("[*] Frida cookie capture started");

    // Hook CookieManager to capture cookies
    try {
        var CookieManager = Java.use("android.webkit.CookieManager");

        CookieManager.getCookie.overload("java.lang.String").implementation = function(url) {
            var cookies = this.getCookie(url);
            if (url && url.indexOf("moba.ru") !== -1) {
                console.log("\n[COOKIE GET] " + url);
                console.log("[COOKIES] " + cookies);
            }
            return cookies;
        };

        CookieManager.setCookie.overload("java.lang.String", "java.lang.String").implementation = function(url, value) {
            if (url && url.indexOf("moba.ru") !== -1) {
                console.log("\n[COOKIE SET] " + url);
                console.log("[VALUE] " + value);
            }
            return this.setCookie(url, value);
        };

        console.log("[+] CookieManager hooked");
    } catch(e) {
        console.log("[!] CookieManager hook failed: " + e);
    }

    // Hook URL connections to see requests
    try {
        var URL = Java.use("java.net.URL");
        var HttpURLConnection = Java.use("java.net.HttpURLConnection");

        URL.openConnection.overload().implementation = function() {
            var conn = this.openConnection();
            var url = this.toString();
            if (url.indexOf("moba.ru") !== -1) {
                console.log("\n[REQUEST] " + url);
            }
            return conn;
        };
        console.log("[+] URL.openConnection hooked");
    } catch(e) {
        console.log("[!] URL hook failed: " + e);
    }

    // Hook OkHttp (used by Chrome)
    try {
        var OkHttpClient = Java.use("okhttp3.OkHttpClient");
        var Request = Java.use("okhttp3.Request");
        var RequestBuilder = Java.use("okhttp3.Request$Builder");

        RequestBuilder.build.implementation = function() {
            var req = this.build();
            var url = req.url().toString();
            if (url.indexOf("moba.ru") !== -1) {
                console.log("\n[OKHTTP REQUEST] " + url);
                var headers = req.headers();
                for (var i = 0; i < headers.size(); i++) {
                    console.log("  " + headers.name(i) + ": " + headers.value(i));
                }
            }
            return req;
        };
        console.log("[+] OkHttp hooked");
    } catch(e) {
        console.log("[!] OkHttp hook failed: " + e);
    }

    console.log("\n[*] Now open moba.ru in Chrome browser");
    console.log("[*] Cookies will be captured automatically\n");
});
