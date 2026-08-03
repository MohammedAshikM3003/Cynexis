/**
 * ============================================================
 * CYNEXIS — Wokwi Simulation: Phase 1 Milestone
 * File: phase1_test.ino
 * ------------------------------------------------------------
 * This sketch is the FIRST milestone:
 *   1. LED blinks to prove the ESP32 is alive
 *   2. Serial monitor prints system info
 *   3. MAC address is printed (needed for cynexis_mac.h)
 *
 * Use this BEFORE uploading any CYNEXIS firmware.
 * Simulate at: https://wokwi.com
 * ============================================================
 */

#include <WiFi.h>

#define PIN_LED 2

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_LED, OUTPUT);

    // --------------------------------------------------
    // Banner
    // --------------------------------------------------
    Serial.println("============================================================");
    Serial.println("  CYNEXIS — Phase 1 Milestone Test");
    Serial.println("  Version: 1.0 | Date: 2026-08-03");
    Serial.println("============================================================");

    // --------------------------------------------------
    // MAC Address (critical — needed for cynexis_mac.h)
    // --------------------------------------------------
    WiFi.mode(WIFI_STA);
    String mac = WiFi.macAddress();
    Serial.println("\n[MAC ADDRESS] This ESP32 MAC:");
    Serial.println("  " + mac);
    Serial.println("\n  Copy this into cynexis_mac.h as the correct node.");

    // --------------------------------------------------
    // System info
    // --------------------------------------------------
    Serial.println("\n[SYSTEM INFO]");
    Serial.printf("  Chip model:     %s\n", ESP.getChipModel());
    Serial.printf("  Chip revision:  %d\n", ESP.getChipRevision());
    Serial.printf("  CPU frequency:  %d MHz\n", ESP.getCpuFreqMHz());
    Serial.printf("  Flash size:     %d bytes\n", ESP.getFlashChipSize());
    Serial.printf("  Free heap:      %d bytes\n", ESP.getFreeHeap());
    Serial.printf("  SDK version:    %s\n", ESP.getSdkVersion());

    // --------------------------------------------------
    // GPIO test
    // --------------------------------------------------
    Serial.println("\n[GPIO TEST] Blinking LED on GPIO 2...");
    Serial.println("  If the LED blinks, GPIO output is working.\n");

    // Blink 5 times fast to signal ready
    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_LED, HIGH);
        delay(100);
        digitalWrite(PIN_LED, LOW);
        delay(100);
    }
}

void loop() {
    // Slow blink (1Hz) = system alive
    digitalWrite(PIN_LED, HIGH);
    delay(500);
    digitalWrite(PIN_LED, LOW);
    delay(500);

    // Print heartbeat every 5 seconds
    static unsigned long last_print = 0;
    if (millis() - last_print >= 5000) {
        last_print = millis();
        Serial.printf("[HEARTBEAT] Uptime: %lus | Free heap: %d bytes\n",
                      millis() / 1000, ESP.getFreeHeap());
    }
}
