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
    0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF   // <-- REPLACE THIS
};

/**
 * MAC address of the Control Glove ESP32.
 * The robot sends AckPacket to this address.
 */
static const uint8_t MAC_GLOVE_CONTROL[6] = {
    0x11, 0x22, 0x33, 0x44, 0x55, 0x66   // <-- REPLACE THIS
};

/**
 * MAC address of the Status Glove ESP32.
 * The robot sends RobotToStatusPacket to this address.
 */
static const uint8_t MAC_GLOVE_STATUS[6] = {
    0x77, 0x88, 0x99, 0xAA, 0xBB, 0xCC   // <-- REPLACE THIS
};

// ============================================================
// END OF cynexis_mac.h
// ============================================================
