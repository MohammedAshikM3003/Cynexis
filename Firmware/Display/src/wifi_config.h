#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

// ====================================================================
// CYNEXIS WI-FI & NTP TIME CONFIGURATION
// ====================================================================
// Enter your local Wi-Fi router SSID and Password below to enable
// automatic NTP real-time clock synchronization.
// ====================================================================

#define WIFI_SSID "WhiteShadow"
#define WIFI_PASS "No Password"

// Timezone Configuration: Asia/Kolkata (UTC +05:30)
// 5 hours + 30 minutes = 19,800 seconds
#define GMT_OFFSET_SEC      (5 * 3600 + 30 * 60)
#define DAYLIGHT_OFFSET_SEC 0

// Primary and Backup NTP Time Servers
#define NTP_SERVER1 "pool.ntp.org"
#define NTP_SERVER2 "time.nist.gov"
#define NTP_SERVER3 "time.google.com"

#endif // WIFI_CONFIG_H
