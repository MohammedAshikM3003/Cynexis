/*
 * CYNEXIS - ESP-NOW RECEIVER
 *
 * Status Glove / Receiver ESP32
 *
 * Receives 5 flex sensor values from the
 * Control Glove / Sender ESP32.
 *
 * Sender data:
 *   Thumb
 *   Index
 *   Middle
 *   Ring
 *   Pinky
 *
 * ESP32 Arduino Core 3.x compatible
 */

#include <WiFi.h>
#include <esp_now.h>
#include "cynexis_protocol.h"

// Operating state names matching cynexis_state_t
const char* cynexisStateNames[] = {
  "INITIALIZATION",
  "IDLE",
  "MANUAL",
  "OBJECT_DETECTION",
  "EMERGENCY",
  "SHUTDOWN"
};

const char* getCynexisStateName(uint8_t stateId) {
  if (stateId <= 5) return cynexisStateNames[stateId];
  return "UNKNOWN";
}

// Error names matching cynexis_error_t
const char* getCynexisErrorName(uint8_t errorCode) {
  switch (errorCode) {
    case ERR_NONE:              return "NONE";
    case ERR_COMMS_TIMEOUT:     return "COMMS_TIMEOUT";
    case ERR_WATCHDOG_RESET:    return "WATCHDOG_RESET";
    case ERR_BATTERY_CRITICAL:  return "BATTERY_CRITICAL";
    case ERR_I2C_FAIL:          return "I2C_FAIL";
    case ERR_OBSTACLE:          return "OBSTACLE";
    case ERR_SERVO_STALL:       return "SERVO_STALL";
    case ERR_MOTOR_OVERCURRENT: return "MOTOR_OVERCURRENT";
    case ERR_ESTOP_PRESSED:     return "ESTOP_PRESSED";
    case ERR_INIT_FAIL:         return "INIT_FAIL";
    default:                    return "UNKNOWN";
  }
}

// Helper: Get motor command name
const char* getMotorCmdName(uint8_t cmd) {
  switch (cmd) {
    case MOTOR_STOP:       return "STOP";
    case MOTOR_FORWARD:    return "FORWARD";
    case MOTOR_REVERSE:    return "REVERSE";
    case MOTOR_SPIN_LEFT:  return "SPIN_LEFT";
    case MOTOR_SPIN_RIGHT: return "SPIN_RIGHT";
    default:               return "UNKNOWN";
  }
}

// =====================================================
// ESP-NOW RECEIVE CALLBACK
// Compatible with ESP32 Arduino Core 3.x
// =====================================================

#include <esp_arduino_version.h>

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataRecv(const esp_now_recv_info *info,
                const uint8_t *incomingData,
                int len) {
#else
void OnDataRecv(const uint8_t *mac,
                const uint8_t *incomingData,
                int len) {
#endif

  // Cast incoming data to RobotToStatusPacket
  const RobotToStatusPacket* packet = (const RobotToStatusPacket*)incomingData;

  // Check packet size
  if (len != sizeof(RobotToStatusPacket)) {
    Serial.printf("ERROR: Invalid packet size (Received: %d, Expected: %d)\n", len, (int)sizeof(RobotToStatusPacket));
    return;
  }

  // Validate magic, protocol version, and CRC checksum
  if (!rts_validate(packet)) {
    Serial.println("ERROR: Packet validation failed (CRC or Magic mismatch)!");
    return;
  }

  // ===================================================
  // DISPLAY RECEIVED ROBOT STATUS TELEMETRY
  // ===================================================

  Serial.println();
  Serial.printf("=== RECEIVED STATUS PACKET #%u ===\n", packet->packet_id);
  Serial.printf("Timestamp   : %u ms\n", packet->timestamp_ms);
  Serial.printf("Robot State : %s (ID: %d)\n", getCynexisStateName(packet->state), packet->state);
  Serial.printf("Robot Batt  : %d%%\n", packet->robot_battery_pct);
  Serial.printf("Signal RSSI : %d dBm\n", packet->rssi);
  Serial.printf("Error Code  : 0x%02X (%s)\n", packet->error_code, getCynexisErrorName(packet->error_code));
  
  Serial.printf("Subsystems  : Cam=%s | Arm=%s | Motors=%s | ESP-NOW=%s | WDT=%s | Obstacle=%s\n",
    packet->flags.camera_ok ? "OK" : "ERR",
    packet->flags.arm_ok ? "OK" : "ERR",
    packet->flags.motors_ok ? "OK" : "ERR",
    packet->flags.esp_now_ok ? "OK" : "ERR",
    packet->flags.watchdog_ok ? "OK" : "ERR",
    packet->flags.obstacle ? "DETECTED" : "NONE"
  );
  
  Serial.printf("Motor Cmd   : %s (0x%02X)\n", getMotorCmdName(packet->motor_cmd), packet->motor_cmd);
  Serial.printf("Arm Joints  : Base=%3d° | Shoulder=%3d° | Elbow=%3d° | Gripper=%3d°\n",
    packet->arm.base,
    packet->arm.shoulder,
    packet->arm.elbow,
    packet->arm.gripper
  );
}


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  // ---------------------------------------------------
  // WiFi Station Mode
  // ---------------------------------------------------

  WiFi.mode(WIFI_STA);

  delay(100);

  // ---------------------------------------------------
  // Header
  // ---------------------------------------------------

  Serial.println();
  Serial.println("========================================");
  Serial.println(" CYNEXIS - ESP-NOW RECEIVER");
  Serial.println("========================================");

  // ---------------------------------------------------
  // Print receiver MAC address
  // ---------------------------------------------------

  Serial.print("Receiver MAC: ");
  Serial.println(WiFi.macAddress());

  Serial.println("----------------------------------------");

  // ---------------------------------------------------
  // Initialize ESP-NOW
  // ---------------------------------------------------

  if (esp_now_init() != ESP_OK) {

    Serial.println("ERROR: ESP-NOW initialization failed!");

    return;
  }

  // ---------------------------------------------------
  // Register receive callback
  // ---------------------------------------------------

  esp_now_register_recv_cb(OnDataRecv);

  Serial.println("ESP-NOW initialized successfully.");
  Serial.println("ESP-NOW Receiver Ready");
  Serial.println("----------------------------------------");
  Serial.println("Waiting for sender data...");
  Serial.println("----------------------------------------");
}


// =====================================================
// LOOP
// =====================================================

void loop() {

  // ESP-NOW reception happens through callback.
  // Nothing else is required here.

  delay(100);
}
