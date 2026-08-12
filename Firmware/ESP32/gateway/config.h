/**
 * ============================================================
 * CYNEXIS — Gateway ESP32 Configuration
 * File: config.h
 * ------------------------------------------------------------
 * Configuration for the USB-Serial to ESP-NOW gateway.
 * This ESP32 bridges laptop JSON commands to robot binary packets.
 * ============================================================
 */

#pragma once

#include <stdint.h>

// ============================================================
// SERIAL CONFIGURATION
// ============================================================

#define GATEWAY_BAUD_RATE     115200    // Must match laptop config
#define SERIAL_BUFFER_SIZE    512       // Max JSON message size
#define SERIAL_TIMEOUT_MS     100       // readline timeout

// ============================================================
// ESP-NOW CONFIGURATION
// ============================================================

#define ESPNOW_CHANNEL        1        // Must match robot ESP32

// ============================================================
// HEARTBEAT
// ============================================================

#define HEARTBEAT_LED_PIN     2        // Onboard LED
#define STATUS_SEND_MS        100      // Telemetry forward rate (10Hz)

// ============================================================
// MOTOR SAFETY
// ============================================================

/** 
 * When false, the gateway will ACK movement commands but 
 * NOT forward them to the robot ESP32 via ESP-NOW.
 * This allows communication testing without motor activation.
 */
#define DEFAULT_MOTORS_ENABLED  false

// ============================================================
// MAC ADDRESSES
// Replace with actual addresses from your ESP32 boards.
// ============================================================

// Robot ESP32 MAC address (the gateway sends ESP-NOW packets here)
static const uint8_t MAC_ROBOT[6] = {
    0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF   // <-- REPLACE THIS
};

// ============================================================
// PROTOCOL VERSION
// Must match the laptop-side PROTOCOL_VERSION in protocol.py
// ============================================================

#define JSON_PROTOCOL_VERSION   1
