#include "time_manager.h"
#include <ctype.h>

static unsigned long last_check = 0;
static unsigned long last_ntp_sync_attempt = 0;
static unsigned long last_diag_log = 0;
static unsigned long wifi_connect_start = 0;
static bool ntp_synced = false;
static bool wifi_was_connected = false;
static bool tried_open_network = false;

void time_manager_init() {
    Serial.println("=========================================");
    Serial.printf("[TIME MANAGER] Initializing Wi-Fi connection to SSID: %s...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    
    // Check if password is "No Password" or empty (Open Wi-Fi Network)
    if (strcmp(WIFI_PASS, "No Password") == 0 || strlen(WIFI_PASS) == 0) {
        tried_open_network = true;
        WiFi.begin(WIFI_SSID);
    } else {
        tried_open_network = false;
        WiFi.begin(WIFI_SSID, WIFI_PASS);
    }

    wifi_connect_start = millis();
    Serial.println("[TIME MANAGER] Timezone: Asia/Kolkata (UTC+05:30)");
    Serial.printf("[TIME MANAGER] Primary NTP Server: %s\n", NTP_SERVER1);
    Serial.printf("[TIME MANAGER] Backup NTP Servers: %s, %s\n", NTP_SERVER2, NTP_SERVER3);
    Serial.println("=========================================");
}

bool time_manager_update(TimeData &out_data) {
    unsigned long now_ms = millis();
    if (now_ms - last_check < 1000) {
        return false;
    }
    last_check = now_ms;

    wl_status_t wifi_status = WiFi.status();

    // 1. Wi-Fi Connection State Machine
    if (wifi_status == WL_CONNECTED) {
        if (!wifi_was_connected) {
            wifi_was_connected = true;
            Serial.println("=========================================");
            Serial.println("[TIME MANAGER] WiFi status: CONNECTED");
            Serial.printf("[TIME MANAGER] IP address: %s\n", WiFi.localIP().toString().c_str());
            Serial.printf("[TIME MANAGER] Gateway: %s\n", WiFi.gatewayIP().toString().c_str());
            Serial.printf("[TIME MANAGER] DNS: %s\n", WiFi.dnsIP().toString().c_str());
            Serial.println("[TIME MANAGER] Starting NTP synchronization...");
            Serial.printf("[TIME MANAGER] NTP server: %s\n", NTP_SERVER1);
            Serial.println("[TIME MANAGER] Timezone: Asia/Kolkata");
            Serial.println("=========================================");

            // Configure NTP now that network interface & DNS are active
            configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER1, NTP_SERVER2, NTP_SERVER3);
            last_ntp_sync_attempt = now_ms;
        }
    } else {
        if (wifi_was_connected) {
            wifi_was_connected = false;
            ntp_synced = false;
            Serial.println("=========================================");
            Serial.printf("[TIME MANAGER] WiFi status: DISCONNECTED (Status code: %d)\n", wifi_status);
            Serial.println("=========================================");
            wifi_connect_start = now_ms;
        }

        // Retry connection logic every 15 seconds if stuck disconnected
        if (now_ms - wifi_connect_start > 15000) {
            wifi_connect_start = now_ms;
            if (tried_open_network) {
                // If open network attempt timed out, try with password string
                tried_open_network = false;
                Serial.printf("[TIME MANAGER] Retrying Wi-Fi connection with WPA password...\n");
                WiFi.begin(WIFI_SSID, WIFI_PASS);
            } else {
                // If WPA attempt timed out, try open network
                tried_open_network = true;
                Serial.printf("[TIME MANAGER] Retrying Wi-Fi connection as Open Network...\n");
                WiFi.begin(WIFI_SSID);
            }
        }
    }

    // 2. Query ESP32 system clock (updated by background SNTP worker)
    time_t now;
    time(&now);
    struct tm *timeinfo = localtime(&now);

    // tm_year > 120 means year >= 2021 (Valid NTP epoch time synced!)
    if (timeinfo && timeinfo->tm_year > 120) {
        if (!ntp_synced) {
            ntp_synced = true;
            Serial.println("=========================================");
            Serial.println("[NTP SUCCESS] Real-time clock synchronized via NTP!");
            Serial.printf("[NTP TIME] %02d:%02d:%02d\n", timeinfo->tm_hour, timeinfo->tm_min, timeinfo->tm_sec);
            Serial.println("=========================================");
        }

        out_data.is_synced = true;
        snprintf(out_data.hour_str, sizeof(out_data.hour_str), "%02d", timeinfo->tm_hour);
        snprintf(out_data.min_str, sizeof(out_data.min_str), "%02d", timeinfo->tm_min);
        snprintf(out_data.time_str, sizeof(out_data.time_str), "%02d:%02d", timeinfo->tm_hour, timeinfo->tm_min);

        strftime(out_data.day_str, sizeof(out_data.day_str), "%a", timeinfo);
        strftime(out_data.date_str, sizeof(out_data.date_str), "%d %b", timeinfo);
        return true;
    } else {
        // 3. Periodic NTP Retry & Diagnostic Logging when not synced
        if (wifi_status == WL_CONNECTED) {
            // Re-trigger NTP config every 10 seconds if not synced yet
            if (now_ms - last_ntp_sync_attempt > 10000) {
                last_ntp_sync_attempt = now_ms;
                configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER1, NTP_SERVER2, NTP_SERVER3);
            }

            // Diagnostic log every 5 seconds
            if (now_ms - last_diag_log > 5000) {
                last_diag_log = now_ms;
                Serial.printf("[TIME MANAGER] Awaiting NTP synchronization... (WiFi Status: CONNECTED, IP: %s, DNS: %s)\n",
                              WiFi.localIP().toString().c_str(),
                              WiFi.dnsIP().toString().c_str());
            }
        } else {
            // Diagnostic log every 5 seconds if Wi-Fi is disconnected
            if (now_ms - last_diag_log > 5000) {
                last_diag_log = now_ms;
                Serial.printf("[TIME MANAGER] WiFi status: DISCONNECTED (Status code: %d). Reconnecting to SSID '%s'...\n",
                              wifi_status, WIFI_SSID);
            }
        }

        out_data.is_synced = false;
        snprintf(out_data.hour_str, sizeof(out_data.hour_str), "SYNC...");
        snprintf(out_data.min_str, sizeof(out_data.min_str), "");
        snprintf(out_data.day_str, sizeof(out_data.day_str), "");
        snprintf(out_data.date_str, sizeof(out_data.date_str), "");
        snprintf(out_data.time_str, sizeof(out_data.time_str), "SYNC...");
        return true;
    }
}
