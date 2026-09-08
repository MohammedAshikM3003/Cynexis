/**
 * ============================================================
 * CYNEXIS — MAC Address Registry
 * File: cynexis_mac.h
 * ------------------------------------------------------------
 * Replace the placeholder MACs below with the ACTUAL MAC
 * addresses read from each ESP32's serial monitor at boot.
 *
 * How to find your ESP32's MAC address:
 *   Upload this one-liner sketch to each ESP32:
 *
 *     #include <WiFi.h>
 *     void setup() { Serial.begin(115200); WiFi.mode(WIFI_STA); Serial.println(WiFi.macAddress()); }
 *     void loop() {}
 *
 *   Record the output and paste the 6 bytes below.
 * ============================================================
 */

#pragma once
#include <stdint.h>

/**
 * MAC address of the Robot ESP32.
 * The control glove sends GloveToRobotPacket to this address.
 * The status glove listens for RobotToStatusPacket from this address.
 */
static const uint8_t MAC_ROBOT[6] = {
    0x04, 0xB2, 0x47, 0x82, 0x38, 0xFC
};

/**
 * MAC address of the Control Glove ESP32.
 * The robot sends AckPacket to this address.
 */
static const uint8_t MAC_GLOVE_CONTROL[6] = {
    0x04, 0xB2, 0x47, 0x82, 0x59, 0x18
};

/**
 * MAC address of the Status Glove ESP32.
 * The robot sends RobotToStatusPacket to this address.
 */
static const uint8_t MAC_GLOVE_STATUS[6] = {
    0x28, 0x05, 0xA5, 0xE2, 0x85, 0xB8
};

// ============================================================
// END OF cynexis_mac.h
// ============================================================
