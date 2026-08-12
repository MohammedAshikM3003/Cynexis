/**
 * ============================================================
 * CYNEXIS — Gateway ESP32 Firmware
 * Version: 1.0
 * File: gateway.ino
 * ------------------------------------------------------------
 * Purpose:
 *   Bridge between Laptop (USB Serial JSON) and Robot ESP32 (ESP-NOW binary).
 *
 * Architecture:
 *   Laptop  ─── USB Serial (JSON) ───>  Gateway ESP32
 *   Gateway ESP32  ─── ESP-NOW (binary) ───>  Robot ESP32
 *   Robot ESP32  ─── ESP-NOW (binary) ───>  Gateway ESP32
 *   Gateway ESP32  ─── USB Serial (JSON) ───>  Laptop
 *
 * Supported JSON message types:
 *   COMMAND  - Laptop → Gateway: execute a robot command
 *   PING     - Laptop → Gateway: heartbeat request
 *   STATUS   - Laptop → Gateway: status request
 *   ACK      - Gateway → Laptop: command accepted
 *   NAK      - Gateway → Laptop: command rejected
 *   PONG     - Gateway → Laptop: heartbeat response
 *   TELEMETRY- Gateway → Laptop: sensor data from robot
 *   ERROR    - Gateway → Laptop: error report
 *
 * Hardware:
 *   - Any ESP32 DevKit board
 *   - Connected to laptop via USB
 *   - No motors, servos, or sensors on this board
 *
 * Libraries required:
 *   - ArduinoJson (v7+)
 *   - esp_now.h (built-in)
 *   - WiFi.h (built-in)
 * ============================================================
 */

#include <WiFi.h>
#include <esp_now.h>
#include <ArduinoJson.h>

#include "config.h"
#include "../../Protocol/cynexis_protocol.h"

// ============================================================
// GLOBALS
// ============================================================

char serial_buffer[SERIAL_BUFFER_SIZE];
int serial_pos = 0;

// Motor-enabled flag (can be toggled via serial command)
bool motors_enabled = DEFAULT_MOTORS_ENABLED;

// ESP-NOW peer
esp_now_peer_info_t peer_robot;

// Connection tracking
volatile bool espnow_connected = false;
volatile unsigned long last_robot_seen_ms = 0;
volatile int8_t last_rssi = 0;

// Stats
uint32_t packets_sent = 0;
uint32_t packets_acked = 0;
uint32_t packets_failed = 0;
uint32_t uptime_start_ms = 0;

// Last received robot telemetry
volatile bool new_telemetry = false;
RobotToStatusPacket last_robot_status;

// ACK tracking
volatile bool espnow_send_ok = false;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================

void init_espnow();
void process_serial_line(const char* line);
void handle_command(JsonDocument& doc);
void handle_ping(JsonDocument& doc);
void handle_status_request(JsonDocument& doc);
void send_json_ack(const char* id, const char* status);
void send_json_nak(const char* id, const char* code);
void send_json_pong(const char* id);
void send_json_status(const char* id);
void send_json_telemetry();
void send_json_error(const char* code, const char* message);
void forward_to_robot(uint8_t motor_cmd, uint8_t speed);
void forward_arm_to_robot(uint8_t base, uint8_t shoulder, uint8_t elbow, uint8_t gripper);
void on_espnow_recv(const uint8_t* mac, const uint8_t* data, int len);
void on_espnow_sent(const uint8_t* mac, esp_now_send_status_t status);

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(GATEWAY_BAUD_RATE);
    delay(500);
    Serial.println("{\"type\":\"STATUS\",\"id\":\"boot\",\"data\":{\"message\":\"CYNEXIS Gateway booting...\"}}");

    pinMode(HEARTBEAT_LED_PIN, OUTPUT);
    uptime_start_ms = millis();

    // Initialize ESP-NOW
    init_espnow();

    Serial.println("{\"type\":\"STATUS\",\"id\":\"boot\",\"data\":{\"message\":\"CYNEXIS Gateway ready\"}}");
    digitalWrite(HEARTBEAT_LED_PIN, HIGH);
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
    // ---- Read serial input (line-by-line) ----
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (serial_pos > 0) {
                serial_buffer[serial_pos] = '\0';
                process_serial_line(serial_buffer);
                serial_pos = 0;
            }
        } else if (serial_pos < SERIAL_BUFFER_SIZE - 1) {
            serial_buffer[serial_pos++] = c;
        } else {
            // Buffer overflow — discard
            serial_pos = 0;
            send_json_error("BUFFER_OVERFLOW", "Serial buffer overflow");
        }
    }

    // ---- Forward robot telemetry to laptop ----
    if (new_telemetry) {
        new_telemetry = false;
        send_json_telemetry();
    }

    // ---- Heartbeat LED blink ----
    static unsigned long last_blink = 0;
    if (millis() - last_blink > 1000) {
        last_blink = millis();
        digitalWrite(HEARTBEAT_LED_PIN, !digitalRead(HEARTBEAT_LED_PIN));
    }
}

// ============================================================
// ESP-NOW INITIALIZATION
// ============================================================

void init_espnow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        send_json_error("ESPNOW_INIT", "ESP-NOW init failed");
        return;
    }

    esp_now_register_recv_cb(on_espnow_recv);
    esp_now_register_send_cb(on_espnow_sent);

    // Add robot as peer
    memcpy(peer_robot.peer_addr, MAC_ROBOT, 6);
    peer_robot.channel = ESPNOW_CHANNEL;
    peer_robot.encrypt = false;

    if (esp_now_add_peer(&peer_robot) != ESP_OK) {
        send_json_error("ESPNOW_PEER", "Failed to add robot peer");
    }
}

// ============================================================
// SERIAL JSON PROCESSING
// ============================================================

void process_serial_line(const char* line) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, line);

    if (err) {
        send_json_nak("unknown", "INVALID_JSON");
        return;
    }

    // Validate protocol version
    int version = doc["v"] | 0;
    if (version != JSON_PROTOCOL_VERSION) {
        const char* id = doc["id"] | "unknown";
        send_json_nak(id, "INVALID_VERSION");
        return;
    }

    const char* type = doc["type"] | "";

    if (strcmp(type, "COMMAND") == 0) {
        handle_command(doc);
    } else if (strcmp(type, "PING") == 0) {
        handle_ping(doc);
    } else if (strcmp(type, "STATUS") == 0) {
        handle_status_request(doc);
    } else {
        const char* id = doc["id"] | "unknown";
        send_json_nak(id, "UNKNOWN_TYPE");
    }
}

// ============================================================
// COMMAND HANDLER
// ============================================================

void handle_command(JsonDocument& doc) {
    const char* id = doc["id"] | "unknown";
    const char* cmd = doc["cmd"] | "";

    // ---- MOVEMENT COMMANDS ----
    if (strcmp(cmd, "FORWARD") == 0) {
        int speed = doc["params"]["speed"] | 150;
        if (motors_enabled) forward_to_robot(MOTOR_FORWARD, speed);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "BACKWARD") == 0) {
        int speed = doc["params"]["speed"] | 150;
        if (motors_enabled) forward_to_robot(MOTOR_REVERSE, speed);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "LEFT") == 0) {
        int speed = doc["params"]["speed"] | 150;
        if (motors_enabled) forward_to_robot(MOTOR_SPIN_LEFT, speed);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "RIGHT") == 0) {
        int speed = doc["params"]["speed"] | 150;
        if (motors_enabled) forward_to_robot(MOTOR_SPIN_RIGHT, speed);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "STOP") == 0) {
        forward_to_robot(MOTOR_STOP, 0);  // Always send STOP regardless of motor flag
        send_json_ack(id, "EXECUTED");
    }
    else if (strcmp(cmd, "EMERGENCY_STOP") == 0) {
        forward_to_robot(MOTOR_STOP, 0);  // Always execute — highest priority
        send_json_ack(id, "EXECUTED");
    }
    // ---- ARM COMMANDS ----
    else if (strcmp(cmd, "ARM_HOME") == 0) {
        if (motors_enabled) forward_arm_to_robot(90, 90, 90, 90);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "BASE") == 0) {
        int angle = doc["params"]["angle"] | 90;
        // Individual joint — send as arm packet with current values
        if (motors_enabled) forward_arm_to_robot(angle, 90, 90, 90);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "SHOULDER") == 0) {
        int angle = doc["params"]["angle"] | 90;
        if (motors_enabled) forward_arm_to_robot(90, angle, 90, 90);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "ELBOW") == 0) {
        int angle = doc["params"]["angle"] | 90;
        if (motors_enabled) forward_arm_to_robot(90, 90, angle, 90);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "WRIST") == 0) {
        int angle = doc["params"]["angle"] | 90;
        // Wrist maps to gripper channel for now (see protocol docs)
        if (motors_enabled) forward_arm_to_robot(90, 90, 90, angle);
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    // ---- GRIPPER ----
    else if (strcmp(cmd, "GRIP_OPEN") == 0) {
        if (motors_enabled) forward_arm_to_robot(90, 90, 90, 180);  // 180° = open
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    else if (strcmp(cmd, "GRIP_CLOSE") == 0) {
        if (motors_enabled) forward_arm_to_robot(90, 90, 90, 0);    // 0° = closed
        send_json_ack(id, motors_enabled ? "EXECUTED" : "MOTORS_DISABLED");
    }
    // ---- UNKNOWN ----
    else {
        send_json_nak(id, "INVALID_COMMAND");
    }
}

// ============================================================
// PING / STATUS HANDLERS
// ============================================================

void handle_ping(JsonDocument& doc) {
    const char* id = doc["id"] | "unknown";
    send_json_pong(id);
}

void handle_status_request(JsonDocument& doc) {
    const char* id = doc["id"] | "unknown";
    send_json_status(id);
}

// ============================================================
// JSON RESPONSE BUILDERS
// ============================================================

void send_json_ack(const char* id, const char* status) {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "ACK";
    doc["id"] = id;
    doc["ts"] = millis();
    doc["status"] = status;

    // Compute checksum placeholder (simplified for firmware)
    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
    packets_acked++;
}

void send_json_nak(const char* id, const char* code) {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "NAK";
    doc["id"] = id;
    doc["ts"] = millis();
    doc["code"] = code;
    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
}

void send_json_pong(const char* id) {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "PONG";
    doc["id"] = id;
    doc["ts"] = millis();
    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
}

void send_json_status(const char* id) {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "STATUS";
    doc["id"] = id;
    doc["ts"] = millis();

    JsonObject data = doc["data"].to<JsonObject>();
    data["firmware_version"] = "1.0.0";
    data["uptime_ms"] = millis() - uptime_start_ms;
    data["motors_enabled"] = motors_enabled;
    data["espnow_connected"] = espnow_connected;
    data["packets_sent"] = packets_sent;
    data["packets_acked"] = packets_acked;
    data["packets_failed"] = packets_failed;
    data["rssi"] = last_rssi;

    // Include last robot battery if available
    if (last_robot_seen_ms > 0) {
        data["robot_battery_pct"] = last_robot_status.robot_battery_pct;
        data["robot_state"] = last_robot_status.state;
    }

    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
}

void send_json_telemetry() {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "TELEMETRY";
    doc["id"] = "telem";
    doc["ts"] = millis();

    JsonObject data = doc["data"].to<JsonObject>();
    data["battery_pct"] = last_robot_status.robot_battery_pct;
    data["rssi"] = (int)last_robot_status.rssi;
    data["state"] = last_robot_status.state;
    data["motor_cmd"] = last_robot_status.motor_cmd;
    data["error_code"] = last_robot_status.error_code;
    data["motors_enabled"] = motors_enabled;

    // Arm positions
    JsonObject arm = data["arm"].to<JsonObject>();
    arm["base"] = last_robot_status.arm.base;
    arm["shoulder"] = last_robot_status.arm.shoulder;
    arm["elbow"] = last_robot_status.arm.elbow;
    arm["gripper"] = last_robot_status.arm.gripper;

    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
}

void send_json_error(const char* code, const char* message) {
    JsonDocument doc;
    doc["v"] = JSON_PROTOCOL_VERSION;
    doc["type"] = "ERROR";
    doc["id"] = "err";
    doc["ts"] = millis();
    doc["code"] = code;

    JsonObject data = doc["data"].to<JsonObject>();
    data["message"] = message;

    doc["cs"] = "00000000";

    serializeJson(doc, Serial);
    Serial.println();
}

// ============================================================
// ESP-NOW FORWARDING
// ============================================================

void forward_to_robot(uint8_t motor_cmd, uint8_t speed) {
    // Build a minimal GloveToRobotPacket
    GloveToRobotPacket pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.magic = PACKET_MAGIC_GLOVE_TO_ROBOT;
    pkt.protocol_ver = CYNEXIS_PROTOCOL_VERSION;
    pkt.packet_id = (uint16_t)(packets_sent & 0xFFFF);
    pkt.timestamp_ms = millis();
    pkt.motor_cmd = motor_cmd;
    pkt.gesture_id = GESTURE_NONE;

    // Set checksum
    gtr_set_checksum(&pkt);

    // Send via ESP-NOW
    esp_err_t result = esp_now_send(MAC_ROBOT, (uint8_t*)&pkt, sizeof(pkt));
    packets_sent++;

    if (result != ESP_OK) {
        packets_failed++;
    }
}

void forward_arm_to_robot(uint8_t base, uint8_t shoulder, uint8_t elbow, uint8_t gripper) {
    GloveToRobotPacket pkt;
    memset(&pkt, 0, sizeof(pkt));

    pkt.magic = PACKET_MAGIC_GLOVE_TO_ROBOT;
    pkt.protocol_ver = CYNEXIS_PROTOCOL_VERSION;
    pkt.packet_id = (uint16_t)(packets_sent & 0xFFFF);
    pkt.timestamp_ms = millis();
    pkt.motor_cmd = MOTOR_STOP;  // No movement during arm control
    pkt.gesture_id = GESTURE_NONE;
    pkt.arm.base = base;
    pkt.arm.shoulder = shoulder;
    pkt.arm.elbow = elbow;
    pkt.arm.gripper = gripper;

    gtr_set_checksum(&pkt);

    esp_err_t result = esp_now_send(MAC_ROBOT, (uint8_t*)&pkt, sizeof(pkt));
    packets_sent++;

    if (result != ESP_OK) {
        packets_failed++;
    }
}

// ============================================================
// ESP-NOW CALLBACKS
// ============================================================

void on_espnow_recv(const uint8_t* mac, const uint8_t* data, int len) {
    // Check for RobotToStatusPacket (telemetry from robot)
    if (len == sizeof(RobotToStatusPacket)) {
        const RobotToStatusPacket* pkt = (const RobotToStatusPacket*)data;
        if (rts_validate(pkt)) {
            memcpy((void*)&last_robot_status, pkt, sizeof(RobotToStatusPacket));
            last_robot_seen_ms = millis();
            espnow_connected = true;
            last_rssi = pkt->rssi;
            new_telemetry = true;
        }
    }
    // Check for AckPacket (acknowledgement from robot)
    else if (len == sizeof(AckPacket)) {
        const AckPacket* pkt = (const AckPacket*)data;
        if (ack_validate(pkt)) {
            last_robot_seen_ms = millis();
            espnow_connected = true;
        }
    }
}

void on_espnow_sent(const uint8_t* mac, esp_now_send_status_t status) {
    espnow_send_ok = (status == ESP_NOW_SEND_SUCCESS);
    if (!espnow_send_ok) {
        packets_failed++;
    }
}
