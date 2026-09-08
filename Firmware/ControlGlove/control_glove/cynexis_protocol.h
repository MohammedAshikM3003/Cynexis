/**
 * ============================================================
 * CYNEXIS — ESP-NOW Communication Protocol
 * Version: 1.0
 * File: cynexis_protocol.h
 * ------------------------------------------------------------
 * Shared header included by ALL three ESP32 nodes:
 *   1. Control Glove   (transmitter)
 *   2. Robot ESP32     (receiver + transmitter)
 *   3. Status Glove    (receiver)
 *
 * This file is the SINGLE SOURCE OF TRUTH for the protocol.
 * Never define packet structures anywhere else.
 * ============================================================
 */

#pragma once

#include <stdint.h>

// ============================================================
// PROTOCOL CONSTANTS
// ============================================================

#define CYNEXIS_PROTOCOL_VERSION    0x01   // Increment on breaking changes

/** Wi-Fi channel for ESP-NOW. Must be the same on ALL nodes. */
#define ESPNOW_WIFI_CHANNEL         1

/**
 * Communication watchdog timeout (milliseconds).
 * If the robot does not receive a glove packet within this
 * period, it must stop all motors and enter EMERGENCY state.
 */
#define COMMS_WATCHDOG_MS           500

/**
 * Maximum number of consecutive lost packets before
 * the robot enters EMERGENCY state.
 */
#define MAX_MISSED_PACKETS          5

/**
 * Packet send interval from the control glove (milliseconds).
 * 20ms = 50Hz update rate.
 * Do not go below 10ms — ESP-NOW has a ~10ms minimum interval.
 */
#define GLOVE_SEND_INTERVAL_MS      20

/**
 * Status glove expected update rate from robot (milliseconds).
 * 100ms = 10Hz — sufficient for telemetry display.
 */
#define STATUS_SEND_INTERVAL_MS     100

/** Obstacle auto-stop threshold in centimetres. */
#define OBSTACLE_STOP_CM            20

/** Battery critical threshold (percentage). */
#define BATTERY_CRITICAL_PCT        15

/** Battery warning threshold (percentage). */
#define BATTERY_WARNING_PCT         30

// ============================================================
// CHECKSUM UTILITY
// ============================================================

/**
 * Simple XOR checksum over a byte array.
 * Called before sending and after receiving to validate integrity.
 *
 * @param data  Pointer to the byte array.
 * @param len   Number of bytes to checksum.
 * @return      XOR checksum byte.
 */
inline uint8_t cynexis_checksum(const uint8_t* data, size_t len) {
    uint8_t cs = 0;
    for (size_t i = 0; i < len; i++) cs ^= data[i];
    return cs;
}

// ============================================================
// PACKET MAGIC BYTES
// Used to quickly reject corrupted or foreign packets.
// ============================================================

#define PACKET_MAGIC_GLOVE_TO_ROBOT   0xC1   // Control Glove  -> Robot
#define PACKET_MAGIC_ROBOT_TO_STATUS  0xC2   // Robot          -> Status Glove
#define PACKET_MAGIC_ACK              0xC3   // Acknowledgement packet

// ============================================================
// OPERATING STATES
// Must be identical on all nodes.
// ============================================================

typedef enum : uint8_t {
    STATE_INITIALIZATION   = 0x00,
    STATE_IDLE             = 0x01,
    STATE_MANUAL           = 0x02,
    STATE_OBJECT_DETECTION = 0x03,
    STATE_EMERGENCY        = 0x04,
    STATE_SHUTDOWN         = 0x05
} cynexis_state_t;

// ============================================================
// GESTURE IDs
// Sent from control glove to robot.
// ============================================================

typedef enum : uint8_t {
    GESTURE_NONE            = 0x00,
    GESTURE_FIST            = 0x01,   // Gripper close
    GESTURE_OPEN_HAND       = 0x02,   // Gripper open
    GESTURE_POINT_UP        = 0x03,   // Arm raise
    GESTURE_POINT_DOWN      = 0x04,   // Arm lower
    GESTURE_THUMBS_UP       = 0x05,   // Mode switch
    GESTURE_PEACE           = 0x06,   // Reserved
    GESTURE_EMERGENCY_STOP  = 0xFF    // All stop — highest priority
} cynexis_gesture_t;

// ============================================================
// MOTOR COMMAND FLAGS
// Bit-field packed into a single uint8_t.
//
//   Bit 7: reserved
//   Bit 6: reserved
//   Bit 5: reserved
//   Bit 4: reserved
//   Bit 3: spin right
//   Bit 2: spin left
//   Bit 1: reverse
//   Bit 0: forward
//
// Mutually exclusive combinations are enforced by the robot.
// ============================================================

#define MOTOR_STOP          0x00
#define MOTOR_FORWARD       0x01
#define MOTOR_REVERSE       0x02
#define MOTOR_SPIN_LEFT     0x04
#define MOTOR_SPIN_RIGHT    0x08

// ============================================================
// ARM COMMAND
// Packed servo angles for all 4 DOF.
// Each angle is 0–180 degrees, stored as uint8_t.
// ============================================================

typedef struct __attribute__((packed)) {
    uint8_t base;       // Joint 1: base rotation (0–180°)
    uint8_t shoulder;   // Joint 2: shoulder      (0–180°)
    uint8_t elbow;      // Joint 3: elbow         (0–180°)
    uint8_t gripper;    // Joint 4: gripper       (0° = closed, 180° = open)
} cynexis_arm_cmd_t;

// ============================================================
// PACKET 1 — CONTROL GLOVE → ROBOT
// Size: 24 bytes (verify with sizeof assertion at runtime)
//
// Transmission rate: every GLOVE_SEND_INTERVAL_MS (20ms, 50Hz)
// ============================================================

typedef struct __attribute__((packed)) {

    // --- Header (3 bytes) ---
    uint8_t  magic;           // PACKET_MAGIC_GLOVE_TO_ROBOT (0xC1)
    uint8_t  protocol_ver;    // CYNEXIS_PROTOCOL_VERSION
    uint16_t packet_id;       // Rolling counter 0–65535, wraps around

    // --- Timing (4 bytes) ---
    uint32_t timestamp_ms;    // millis() at time of send

    // --- Finger data (5 bytes) ---
    uint8_t  flex[5];         // Raw 0–100% bend per finger:
                              //   [0]=thumb [1]=index [2]=middle
                              //   [3]=ring  [4]=pinky

    // --- IMU data (6 bytes) ---
    int16_t  roll_x10;        // Roll  * 10  (e.g. 453 = 45.3°)
    int16_t  pitch_x10;       // Pitch * 10
    int16_t  yaw_x10;         // Yaw   * 10

    // --- Commands (2 bytes) ---
    uint8_t  motor_cmd;       // MOTOR_xxx flags
    uint8_t  gesture_id;      // cynexis_gesture_t

    // --- Arm (4 bytes) ---
    cynexis_arm_cmd_t arm;    // Joint angles

    // --- Flags (1 byte) ---
    uint8_t  emergency : 1;   // 1 = E-stop requested
    uint8_t  reserved  : 7;

    // --- Battery (1 byte) ---
    uint8_t  glove_battery_pct;  // 0–100%

    // --- Checksum (1 byte) ---
    // XOR of all bytes preceding this field.
    uint8_t  checksum;

} GloveToRobotPacket;

// ============================================================
// PACKET 2 — ROBOT → STATUS GLOVE
// Size: 20 bytes
//
// Transmission rate: every STATUS_SEND_INTERVAL_MS (100ms, 10Hz)
// ============================================================

typedef struct __attribute__((packed)) {

    // --- Header (3 bytes) ---
    uint8_t  magic;           // PACKET_MAGIC_ROBOT_TO_STATUS (0xC2)
    uint8_t  protocol_ver;    // CYNEXIS_PROTOCOL_VERSION
    uint16_t packet_id;       // Rolling counter

    // --- Timing (4 bytes) ---
    uint32_t timestamp_ms;    // millis() at time of send

    // --- Robot battery (1 byte) ---
    uint8_t  robot_battery_pct;  // 0–100%

    // --- Signal (1 byte) ---
    int8_t   rssi;            // dBm, signed (-100 to 0)

    // --- State (1 byte) ---
    uint8_t  state;           // cynexis_state_t

    // --- Subsystem status flags (2 bytes) ---
    struct __attribute__((packed)) {
        uint8_t camera_ok   : 1;
        uint8_t arm_ok      : 1;
        uint8_t motors_ok   : 1;
        uint8_t esp_now_ok  : 1;
        uint8_t watchdog_ok : 1;
        uint8_t obstacle    : 1;   // 1 = obstacle detected
        uint8_t reserved    : 2;
    } flags;

    // --- Motor direction (1 byte) ---
    // Current active MOTOR_xxx flag
    uint8_t  motor_cmd;       

    // --- Arm angles (4 bytes) ---
    cynexis_arm_cmd_t arm;    // Current servo positions

    // --- Error code (1 byte) ---
    uint8_t  error_code;      // 0x00 = no error (see error table below)

    // --- Checksum (1 byte) ---
    uint8_t  checksum;

} RobotToStatusPacket;

// ============================================================
// PACKET 3 — ACK (Robot → Control Glove)
// Lightweight acknowledgement — confirms last packet received.
// Size: 8 bytes
// ============================================================

typedef struct __attribute__((packed)) {
    uint8_t  magic;           // PACKET_MAGIC_ACK (0xC3)
    uint8_t  protocol_ver;
    uint16_t ack_packet_id;   // packet_id of the packet being acknowledged
    uint8_t  state;           // cynexis_state_t — current robot state
    int8_t   rssi;            // dBm — robot's received signal strength
    uint8_t  reserved;
    uint8_t  checksum;
} AckPacket;

// ============================================================
// ERROR CODES
// Reported in RobotToStatusPacket.error_code
// ============================================================

typedef enum : uint8_t {
    ERR_NONE              = 0x00,
    ERR_COMMS_TIMEOUT     = 0x01,   // No glove packet within watchdog window
    ERR_WATCHDOG_RESET    = 0x02,   // Software watchdog fired
    ERR_BATTERY_CRITICAL  = 0x03,   // Battery below BATTERY_CRITICAL_PCT
    ERR_I2C_FAIL          = 0x04,   // PCA9685 or MPU6050 not responding
    ERR_OBSTACLE          = 0x05,   // HC-SR04 triggered auto-stop
    ERR_SERVO_STALL       = 0x06,   // Servo overcurrent / stall detected
    ERR_MOTOR_OVERCURRENT = 0x07,   // BTS7960 overcurrent flag
    ERR_ESTOP_PRESSED     = 0x08,   // Physical E-stop button pressed
    ERR_INIT_FAIL         = 0x09,   // Initialisation self-test failed
    ERR_UNKNOWN           = 0xFF
} cynexis_error_t;

// ============================================================
// PACKET SIZE ASSERTIONS
// These will cause a compile-time error if the struct sizes
// drift due to accidental padding or modification.
// ============================================================

static_assert(sizeof(GloveToRobotPacket) == 28,
    "GloveToRobotPacket size mismatch — check struct layout");

static_assert(sizeof(RobotToStatusPacket) == 19,
    "RobotToStatusPacket size mismatch — check struct layout");

static_assert(sizeof(AckPacket) == 8,
    "AckPacket size mismatch — check struct layout");

// ============================================================
// CHECKSUM HELPERS
// ============================================================

/**
 * Compute and fill the checksum field of a GloveToRobotPacket.
 * Call this immediately before esp_now_send().
 */
inline void gtr_set_checksum(GloveToRobotPacket* p) {
    p->checksum = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(GloveToRobotPacket) - 1   // exclude checksum byte itself
    );
}

/**
 * Validate a received GloveToRobotPacket.
 * Returns true if magic, protocol version, and checksum are all valid.
 */
inline bool gtr_validate(const GloveToRobotPacket* p) {
    if (p->magic        != PACKET_MAGIC_GLOVE_TO_ROBOT) return false;
    if (p->protocol_ver != CYNEXIS_PROTOCOL_VERSION)    return false;
    uint8_t expected = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(GloveToRobotPacket) - 1
    );
    return (p->checksum == expected);
}

/**
 * Compute and fill the checksum field of a RobotToStatusPacket.
 */
inline void rts_set_checksum(RobotToStatusPacket* p) {
    p->checksum = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(RobotToStatusPacket) - 1
    );
}

/**
 * Validate a received RobotToStatusPacket.
 */
inline bool rts_validate(const RobotToStatusPacket* p) {
    if (p->magic        != PACKET_MAGIC_ROBOT_TO_STATUS) return false;
    if (p->protocol_ver != CYNEXIS_PROTOCOL_VERSION)     return false;
    uint8_t expected = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(RobotToStatusPacket) - 1
    );
    return (p->checksum == expected);
}

/**
 * Compute and fill the checksum field of an AckPacket.
 */
inline void ack_set_checksum(AckPacket* p) {
    p->checksum = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(AckPacket) - 1
    );
}

/**
 * Validate a received AckPacket.
 */
inline bool ack_validate(const AckPacket* p) {
    if (p->magic        != PACKET_MAGIC_ACK)          return false;
    if (p->protocol_ver != CYNEXIS_PROTOCOL_VERSION)  return false;
    uint8_t expected = cynexis_checksum(
        (const uint8_t*)p,
        sizeof(AckPacket) - 1
    );
    return (p->checksum == expected);
}