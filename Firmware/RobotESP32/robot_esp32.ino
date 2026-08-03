/**
 * ============================================================
 * CYNEXIS — Robot ESP32 Firmware
 * Version: 1.0
 * File: robot_esp32.ino
 * ------------------------------------------------------------
 * Hardware:
 *   - ESP32 (any 30-pin or 38-pin variant)
 *   - BTS7960 dual H-bridge motor driver (left side + right side)
 *   - PCA9685 16-channel PWM servo driver (I2C)
 *   - 2x LM2596 buck converters (12V→7.5V servos, 12V→5V logic)
 *   - HC-SR04 ultrasonic sensor
 *   - Voltage sensor / voltage divider on battery rail
 *   - Emergency stop button (NC momentary to GND)
 *
 * Libraries required:
 *   - Adafruit PWM Servo Driver  (search: "Adafruit PCA9685")
 *   - esp_now.h  (built-in)
 *   - WiFi.h     (built-in)
 *   - esp_task_wdt.h  (built-in)
 *
 * Pin mapping (ESP32 WROOM-32):
 *   BTS7960 LEFT  RPWM  → GPIO 26  (left motors, forward)
 *   BTS7960 LEFT  LPWM  → GPIO 27  (left motors, reverse)
 *   BTS7960 LEFT  R_EN  → GPIO 14  (left enable)
 *   BTS7960 LEFT  L_EN  → GPIO 14  (tied to R_EN)
 *   BTS7960 RIGHT RPWM  → GPIO 12  (right motors, forward)
 *   BTS7960 RIGHT LPWM  → GPIO 13  (right motors, reverse)
 *   BTS7960 RIGHT R_EN  → GPIO 15  (right enable)
 *   BTS7960 RIGHT L_EN  → GPIO 15  (tied to R_EN)
 *   PCA9685 SDA         → GPIO 21
 *   PCA9685 SCL         → GPIO 22
 *   HC-SR04 TRIG        → GPIO 5
 *   HC-SR04 ECHO        → GPIO 18  (use 1kΩ+2kΩ divider: 5V→3.3V)
 *   Battery sense       → GPIO 36  (VP, ADC1_CH0)
 *   E-stop button       → GPIO 4   (NC to GND, internal pullup)
 *   Status LED          → GPIO 2
 * ============================================================
 */

// ============================================================
// INCLUDES
// ============================================================

#include <WiFi.h>
#include <esp_now.h>
#include <esp_task_wdt.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

#include "../../Protocol/cynexis_protocol.h"
#include "../../Protocol/cynexis_mac.h"

// ============================================================
// PIN DEFINITIONS
// ============================================================

// BTS7960 — LEFT side (controls left 2 motors)
#define PIN_L_RPWM   26
#define PIN_L_LPWM   27
#define PIN_L_EN     14

// BTS7960 — RIGHT side (controls right 2 motors)
#define PIN_R_RPWM   12
#define PIN_R_LPWM   13
#define PIN_R_EN     15

// HC-SR04
#define PIN_TRIG     5
#define PIN_ECHO     18

// Sensors / controls
#define PIN_BATT     36   // Battery voltage divider
#define PIN_ESTOP    4    // Emergency stop button (NC to GND)
#define PIN_LED      2

// ============================================================
// SERVO CHANNEL ASSIGNMENTS ON PCA9685
// ============================================================

#define SERVO_BASE      0   // Channel 0: base rotation
#define SERVO_SHOULDER  1   // Channel 1: shoulder
#define SERVO_ELBOW     2   // Channel 2: elbow
#define SERVO_GRIPPER   3   // Channel 3: gripper

// PCA9685 PWM values for servo 0° and 180°
// MG996R: 1ms (0°) → 2ms (180°) pulse, at 50Hz (20ms period)
// PCA9685 at 50Hz: 4096 counts = 20ms → 1 count ≈ 4.88µs
// 1ms / 4.88µs ≈ 205 counts → 0°
// 2ms / 4.88µs ≈ 410 counts → 180°
#define SERVO_MIN_PULSE  150   // 0°   (tune to your servo)
#define SERVO_MAX_PULSE  600   // 180° (tune to your servo)

// ============================================================
// CONFIGURATION
// ============================================================

#define WATCHDOG_TIMEOUT_S   5       // Software watchdog
#define MOTOR_MAX_PWM        255     // Maximum motor PWM value (0–255)
#define MOTOR_MIN_SPEED      80      // Minimum PWM to overcome stiction
#define OBSTACLE_STOP_DIST   20      // cm
#define BATT_VOLTAGE_DIVIDER 4.0f    // Adjust to match your divider
#define BATT_MAX_V           12.6f
#define BATT_MIN_V           9.0f
#define ADC_REF_V            3.3f
#define ADC_MAX              4095

// ============================================================
// GLOBALS
// ============================================================

Adafruit_PWMServoDriver pca9685 = Adafruit_PWMServoDriver(0x40);

// Current system state
volatile cynexis_state_t current_state = STATE_INITIALIZATION;

// Last received glove packet
GloveToRobotPacket last_glove_pkt;
volatile bool new_packet_available = false;
volatile unsigned long last_packet_ms = 0;

// Outgoing status packet
RobotToStatusPacket status_pkt;
uint16_t status_pkt_counter = 0;

// Outgoing ACK packet
AckPacket ack_pkt;

// ESP-NOW peers
esp_now_peer_info_t peer_glove;
esp_now_peer_info_t peer_status;

// Servo current angles (for smooth movement and hold-on-emergency)
uint8_t servo_angle[4] = {90, 90, 90, 90};  // Start at midpoint

// Obstacle state
volatile bool obstacle_detected = false;

// E-stop state
volatile bool estop_pressed = false;

unsigned long last_status_send_ms = 0;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================

void init_espnow();
void init_motors();
void init_servos();
void init_sensors();
void init_safety();
void run_self_test();
void process_glove_packet();
void execute_motor_command(uint8_t cmd);
void execute_arm_command(const cynexis_arm_cmd_t& arm);
void set_servo_angle(uint8_t channel, uint8_t angle_deg);
void stop_all_motors();
void disable_motors();
void enable_motors();
void send_ack(uint16_t pkt_id);
void send_status();
void check_watchdog();
void check_estop();
void check_obstacle();
float read_distance_cm();
float read_battery_voltage();
uint8_t voltage_to_percent(float v);
void enter_state(cynexis_state_t new_state);
void enter_emergency(cynexis_error_t reason);
void on_data_recv(const uint8_t* mac, const uint8_t* data, int len);
void on_data_sent(const uint8_t* mac, esp_now_send_status_t status);
void blink(int n, int ms);
void IRAM_ATTR estop_isr();

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(115200);
    Serial.println("[CYNEXIS] Robot ESP32 booting...");

    pinMode(PIN_LED,   OUTPUT);
    blink(3, 200);

    // --------------------------------------------------------
    // Software watchdog
    // --------------------------------------------------------
    esp_task_wdt_init(WATCHDOG_TIMEOUT_S, true);
    esp_task_wdt_add(NULL);

    // --------------------------------------------------------
    // I2C for PCA9685
    // --------------------------------------------------------
    Wire.begin(21, 22);

    // --------------------------------------------------------
    // Subsystem init
    // --------------------------------------------------------
    init_safety();    // E-stop first — always
    init_motors();
    init_servos();
    init_sensors();
    init_espnow();

    // --------------------------------------------------------
    // Self-test
    // --------------------------------------------------------
    run_self_test();

    enter_state(STATE_IDLE);
    Serial.println("[CYNEXIS] Robot ready.");
    blink(2, 500);
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
    esp_task_wdt_reset();   // Feed watchdog

    // --- Safety checks (run every iteration) ---
    check_estop();
    check_watchdog();

    // --- State machine ---
    switch (current_state) {

        case STATE_IDLE:
            // Motors stopped, arm in home position — wait for packet
            break;

        case STATE_MANUAL:
            // Process incoming gesture commands
            if (new_packet_available) {
                new_packet_available = false;
                process_glove_packet();
            }
            check_obstacle();
            break;

        case STATE_OBJECT_DETECTION:
            // Commands come from laptop via serial (future)
            // For now, behave like MANUAL until laptop integration
            if (new_packet_available) {
                new_packet_available = false;
                process_glove_packet();
            }
            break;

        case STATE_EMERGENCY:
            // Do nothing — wait for manual reset
            // Motors are already stopped in enter_emergency()
            break;

        case STATE_SHUTDOWN:
            stop_all_motors();
            disable_motors();
            Serial.println("[CYNEXIS] Shutdown complete. Safe to cut power.");
            while (true) blink(1, 2000);
            break;

        default:
            break;
    }

    // --- Send status telemetry ---
    unsigned long now = millis();
    if (now - last_status_send_ms >= STATUS_SEND_INTERVAL_MS) {
        last_status_send_ms = now;
        send_status();
    }
}

// ============================================================
// PACKET PROCESSING
// ============================================================

void process_glove_packet() {
    // Emergency flag overrides everything
    if (last_glove_pkt.emergency) {
        enter_emergency(ERR_ESTOP_PRESSED);
        return;
    }

    // Transition from IDLE to MANUAL on first packet
    if (current_state == STATE_IDLE) {
        enter_state(STATE_MANUAL);
    }

    execute_motor_command(last_glove_pkt.motor_cmd);
    execute_arm_command(last_glove_pkt.arm);
}

// ============================================================
// MOTOR CONTROL
// ============================================================

void execute_motor_command(uint8_t cmd) {
    if (obstacle_detected && (cmd == MOTOR_FORWARD)) {
        stop_all_motors();
        return;
    }

    switch (cmd) {
        case MOTOR_FORWARD:
            // Both sides forward
            ledcWrite(0, MOTOR_MAX_PWM);  // L_RPWM
            ledcWrite(1, 0);              // L_LPWM
            ledcWrite(2, MOTOR_MAX_PWM);  // R_RPWM
            ledcWrite(3, 0);              // R_LPWM
            break;

        case MOTOR_REVERSE:
            ledcWrite(0, 0);
            ledcWrite(1, MOTOR_MAX_PWM);
            ledcWrite(2, 0);
            ledcWrite(3, MOTOR_MAX_PWM);
            break;

        case MOTOR_SPIN_LEFT:
            // Left backward, right forward
            ledcWrite(0, 0);
            ledcWrite(1, MOTOR_MAX_PWM);
            ledcWrite(2, MOTOR_MAX_PWM);
            ledcWrite(3, 0);
            break;

        case MOTOR_SPIN_RIGHT:
            // Left forward, right backward
            ledcWrite(0, MOTOR_MAX_PWM);
            ledcWrite(1, 0);
            ledcWrite(2, 0);
            ledcWrite(3, MOTOR_MAX_PWM);
            break;

        case MOTOR_STOP:
        default:
            stop_all_motors();
            break;
    }
}

void stop_all_motors() {
    ledcWrite(0, 0);
    ledcWrite(1, 0);
    ledcWrite(2, 0);
    ledcWrite(3, 0);
}

void disable_motors() {
    digitalWrite(PIN_L_EN, LOW);
    digitalWrite(PIN_R_EN, LOW);
}

void enable_motors() {
    digitalWrite(PIN_L_EN, HIGH);
    digitalWrite(PIN_R_EN, HIGH);
}

// ============================================================
// SERVO CONTROL
// ============================================================

void execute_arm_command(const cynexis_arm_cmd_t& arm) {
    set_servo_angle(SERVO_BASE,     arm.base);
    set_servo_angle(SERVO_SHOULDER, arm.shoulder);
    set_servo_angle(SERVO_ELBOW,    arm.elbow);
    set_servo_angle(SERVO_GRIPPER,  arm.gripper);
}

void set_servo_angle(uint8_t channel, uint8_t angle_deg) {
    angle_deg = constrain(angle_deg, 0, 180);
    servo_angle[channel] = angle_deg;

    uint16_t pulse = map(angle_deg, 0, 180, SERVO_MIN_PULSE, SERVO_MAX_PULSE);
    pca9685.setPWM(channel, 0, pulse);
}

void move_arm_to_home() {
    set_servo_angle(SERVO_BASE,     90);
    set_servo_angle(SERVO_SHOULDER, 90);
    set_servo_angle(SERVO_ELBOW,    90);
    set_servo_angle(SERVO_GRIPPER, 180);  // Fully open
}

// ============================================================
// SAFETY & WATCHDOG
// ============================================================

void check_watchdog() {
    if (current_state != STATE_MANUAL && current_state != STATE_OBJECT_DETECTION)
        return;

    unsigned long age = millis() - last_packet_ms;

    if (age > COMMS_WATCHDOG_MS) {
        Serial.printf("[WATCHDOG] No packet for %lums. Entering EMERGENCY.\n", age);
        enter_emergency(ERR_COMMS_TIMEOUT);
    }
}

void check_estop() {
    // E-stop is NC — LOW means button pressed
    if (digitalRead(PIN_ESTOP) == LOW) {
        if (!estop_pressed) {
            estop_pressed = true;
            enter_emergency(ERR_ESTOP_PRESSED);
        }
    } else {
        estop_pressed = false;
    }
}

void check_obstacle() {
    float dist = read_distance_cm();

    if (dist > 0 && dist < OBSTACLE_STOP_DIST) {
        if (!obstacle_detected) {
            obstacle_detected = true;
            stop_all_motors();
            Serial.printf("[OBSTACLE] Detected at %.1fcm. Auto-stopped.\n", dist);
        }
    } else {
        obstacle_detected = false;
    }
}

// ============================================================
// STATE MACHINE
// ============================================================

void enter_state(cynexis_state_t new_state) {
    Serial.printf("[STATE] %u → %u\n", (uint8_t)current_state, (uint8_t)new_state);
    current_state = new_state;

    switch (new_state) {
        case STATE_IDLE:
            stop_all_motors();
            move_arm_to_home();
            break;

        case STATE_MANUAL:
            enable_motors();
            break;

        case STATE_EMERGENCY:
            // (handled in enter_emergency)
            break;

        default:
            break;
    }
}

void enter_emergency(cynexis_error_t reason) {
    Serial.printf("[EMERGENCY] Reason: 0x%02X\n", (uint8_t)reason);

    stop_all_motors();
    disable_motors();

    current_state = STATE_EMERGENCY;

    // Fill status packet with error and send immediately
    status_pkt.error_code = (uint8_t)reason;
    send_status();

    // Blink LED rapidly to signal emergency
    for (int i = 0; i < 10; i++) blink(1, 100);
}

// ============================================================
// ESP-NOW — ACK and STATUS
// ============================================================

void send_ack(uint16_t pkt_id) {
    ack_pkt.magic         = PACKET_MAGIC_ACK;
    ack_pkt.protocol_ver  = CYNEXIS_PROTOCOL_VERSION;
    ack_pkt.ack_packet_id = pkt_id;
    ack_pkt.state         = (uint8_t)current_state;
    ack_pkt.rssi          = (int8_t)WiFi.RSSI();
    ack_pkt.reserved      = 0;
    ack_set_checksum(&ack_pkt);

    esp_now_send(MAC_GLOVE_CONTROL, (const uint8_t*)&ack_pkt, sizeof(AckPacket));
}

void send_status() {
    memset(&status_pkt, 0, sizeof(RobotToStatusPacket));

    status_pkt.magic             = PACKET_MAGIC_ROBOT_TO_STATUS;
    status_pkt.protocol_ver      = CYNEXIS_PROTOCOL_VERSION;
    status_pkt.packet_id         = status_pkt_counter++;
    status_pkt.timestamp_ms      = millis();
    status_pkt.robot_battery_pct = voltage_to_percent(read_battery_voltage());
    status_pkt.rssi              = (int8_t)WiFi.RSSI();
    status_pkt.state             = (uint8_t)current_state;

    status_pkt.flags.camera_ok   = 0;   // Camera is on laptop (not monitored here)
    status_pkt.flags.arm_ok      = 1;   // Updated if servo fault detected
    status_pkt.flags.motors_ok   = (current_state != STATE_EMERGENCY);
    status_pkt.flags.esp_now_ok  = (millis() - last_packet_ms < 1000);
    status_pkt.flags.watchdog_ok = 1;
    status_pkt.flags.obstacle    = obstacle_detected ? 1 : 0;

    status_pkt.motor_cmd         = last_glove_pkt.motor_cmd;
    status_pkt.arm               = last_glove_pkt.arm;

    // error_code is set by enter_emergency() — clear on healthy send
    if (current_state != STATE_EMERGENCY) {
        status_pkt.error_code = ERR_NONE;
    }

    rts_set_checksum(&status_pkt);

    esp_now_send(MAC_GLOVE_STATUS,
                 (const uint8_t*)&status_pkt,
                 sizeof(RobotToStatusPacket));
}

// ============================================================
// SENSORS
// ============================================================

float read_distance_cm() {
    // Send 10µs trigger pulse
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    // Measure echo pulse width (timeout 30ms = ~5m max range)
    long duration = pulseIn(PIN_ECHO, HIGH, 30000);
    if (duration == 0) return -1.0f;  // No echo (out of range)

    return (duration / 2.0f) / 29.1f;  // Convert µs to cm
}

float read_battery_voltage() {
    int raw = 0;
    for (int i = 0; i < 8; i++) raw += analogRead(PIN_BATT);
    raw /= 8;

    float adc_v = (raw / (float)ADC_MAX) * ADC_REF_V;
    return adc_v * BATT_VOLTAGE_DIVIDER;
}

uint8_t voltage_to_percent(float v) {
    float pct = (v - BATT_MIN_V) / (BATT_MAX_V - BATT_MIN_V) * 100.0f;
    return (uint8_t)constrain((int)pct, 0, 100);
}

// ============================================================
// INITIALISATION HELPERS
// ============================================================

void init_safety() {
    pinMode(PIN_ESTOP, INPUT_PULLUP);
    // attachInterrupt is optional — polled in loop() for reliability
    Serial.println("[SAFETY] E-stop pin configured.");
}

void init_motors() {
    pinMode(PIN_L_EN, OUTPUT);
    pinMode(PIN_R_EN, OUTPUT);
    disable_motors();  // Start disabled

    // Use LEDC for PWM on motor pins (ESP32 has no analogWrite)
    ledcSetup(0, 20000, 8);  // Channel 0, 20kHz, 8-bit (BTS7960 prefers high freq)
    ledcSetup(1, 20000, 8);
    ledcSetup(2, 20000, 8);
    ledcSetup(3, 20000, 8);

    ledcAttachPin(PIN_L_RPWM, 0);
    ledcAttachPin(PIN_L_LPWM, 1);
    ledcAttachPin(PIN_R_RPWM, 2);
    ledcAttachPin(PIN_R_LPWM, 3);

    stop_all_motors();
    Serial.println("[MOTORS] BTS7960 initialised.");
}

void init_servos() {
    pca9685.begin();
    pca9685.setOscillatorFrequency(27000000);  // Calibrate for your board
    pca9685.setPWMFreq(50);                    // 50Hz for servos
    delay(10);

    move_arm_to_home();
    Serial.println("[ARM] PCA9685 initialised. Arm at home position.");
}

void init_sensors() {
    pinMode(PIN_TRIG, OUTPUT);
    pinMode(PIN_ECHO, INPUT);
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    Serial.println("[SENSORS] HC-SR04 and battery sense initialised.");
}

void init_espnow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[FATAL] ESP-NOW init failed.");
        while (true) blink(3, 100);
    }

    esp_now_register_recv_cb(on_data_recv);
    esp_now_register_send_cb(on_data_sent);

    // Register control glove as peer (for ACK replies)
    memset(&peer_glove, 0, sizeof(peer_glove));
    memcpy(peer_glove.peer_addr, MAC_GLOVE_CONTROL, 6);
    peer_glove.channel = ESPNOW_WIFI_CHANNEL;
    peer_glove.encrypt = false;
    esp_now_add_peer(&peer_glove);

    // Register status glove as peer (for telemetry)
    memset(&peer_status, 0, sizeof(peer_status));
    memcpy(peer_status.peer_addr, MAC_GLOVE_STATUS, 6);
    peer_status.channel = ESPNOW_WIFI_CHANNEL;
    peer_status.encrypt = false;
    esp_now_add_peer(&peer_status);

    Serial.println("[ESP-NOW] Both peers registered.");
}

void run_self_test() {
    Serial.println("[SELFTEST] Running self-test...");

    // Battery check
    float batt = read_battery_voltage();
    Serial.printf("[SELFTEST] Battery: %.2fV\n", batt);
    if (batt < 9.5f) {
        Serial.println("[SELFTEST FAIL] Battery critically low. Aborting.");
        enter_emergency(ERR_BATTERY_CRITICAL);
        while (true) blink(5, 200);
    }

    // HC-SR04 check
    float dist = read_distance_cm();
    Serial.printf("[SELFTEST] HC-SR04: %.1fcm\n", dist);

    // Servo check — small sweep
    set_servo_angle(SERVO_GRIPPER, 160);
    delay(200);
    set_servo_angle(SERVO_GRIPPER, 180);
    delay(200);

    Serial.println("[SELFTEST] PASSED.");
}

// ============================================================
// ESP-NOW CALLBACKS
// ============================================================

void on_data_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (len != sizeof(GloveToRobotPacket)) return;

    const GloveToRobotPacket* pkt = (const GloveToRobotPacket*)data;

    if (!gtr_validate(pkt)) {
        Serial.println("[ESP-NOW] Invalid packet (checksum/magic fail).");
        return;
    }

    // Copy to global buffer (interrupt-safe via bool flag)
    memcpy(&last_glove_pkt, pkt, sizeof(GloveToRobotPacket));
    new_packet_available = true;
    last_packet_ms = millis();

    // Send ACK immediately
    send_ack(pkt->packet_id);
}

void on_data_sent(const uint8_t* mac, esp_now_send_status_t status) {
    // Silent — don't print on every send to avoid serial flooding
}

// ============================================================
// UTILITY
// ============================================================

void blink(int n, int ms) {
    for (int i = 0; i < n; i++) {
        digitalWrite(PIN_LED, HIGH); delay(ms / 2);
        digitalWrite(PIN_LED, LOW);  delay(ms / 2);
    }
}

// ============================================================
// END OF robot_esp32.ino
// ============================================================
