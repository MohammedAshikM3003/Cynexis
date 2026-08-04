/**
 * ============================================================
 * CYNEXIS — Control Glove Firmware
 * Version: 1.0
 * File: control_glove.ino
 * ------------------------------------------------------------
 * Hardware:
 *   - ESP32 (any 30-pin or 38-pin variant)
 *   - 5x Flex sensors (voltage dividers with 10kΩ resistors)
 *   - MPU6050 IMU (I2C)
 *   - 18650 battery + TP4056 charger
 *
 * Libraries required (install via Arduino Library Manager):
 *   - Adafruit MPU6050   (search: "Adafruit MPU6050")
 *   - Adafruit Unified Sensor
 *   - esp_now.h          (built into ESP32 Arduino core)
 *   - WiFi.h             (built into ESP32 Arduino core)
 *   - esp_task_wdt.h     (built into ESP32 Arduino core)
 *
 * Pin mapping (ESP32 WROOM-32):
 *   Flex sensor 0 (thumb)  → GPIO 34 (ADC1_CH6, input only)
 *   Flex sensor 1 (index)  → GPIO 35 (ADC1_CH7, input only)
 *   Flex sensor 2 (middle) → GPIO 32 (ADC1_CH4)
 *   Flex sensor 3 (ring)   → GPIO 33 (ADC1_CH5)
 *   Flex sensor 4 (pinky)  → GPIO 39 (VP, ADC1_CH3, input only)
 *   MPU6050 SDA            → GPIO 21
 *   MPU6050 SCL            → GPIO 22
 *   Battery voltage sense  → GPIO 36 (VP, ADC1_CH0, input only)
 *   Status LED             → GPIO 2  (onboard LED)
 * ============================================================
 */

// ============================================================
// INCLUDES
// ============================================================

#include <WiFi.h>
#include <esp_now.h>
#include <esp_task_wdt.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#include "../../Protocol/cynexis_protocol.h"
#include "../../Protocol/cynexis_mac.h"

// ============================================================
// PIN DEFINITIONS
// ============================================================

#define PIN_FLEX_THUMB    34
#define PIN_FLEX_INDEX    35
#define PIN_FLEX_MIDDLE   32
#define PIN_FLEX_RING     33
#define PIN_FLEX_PINKY    39   // VP — input only (changed from GPIO25, 2026-08-04)
#define PIN_BATT_SENSE    36   // Voltage divider: Vbatt -> 100kΩ -> pin -> 100kΩ -> GND
#define PIN_STATUS_LED    2

// ============================================================
// FLEX SENSOR CALIBRATION
// Adjust these values after physical calibration.
// Open = finger straight, Closed = finger fully bent.
// ============================================================

const int FLEX_OPEN[5]   = {2000, 2000, 2000, 2000, 2000};  // ADC value when straight
const int FLEX_CLOSED[5] = {3500, 3500, 3500, 3500, 3500};  // ADC value when bent

// ============================================================
// CONFIGURATION
// ============================================================

#define WATCHDOG_TIMEOUT_S    5       // Software watchdog timeout in seconds
#define BATT_VOLTAGE_DIVIDER  2.0f    // Voltage divider ratio (if using 100k+100k)
#define BATT_MAX_VOLTAGE      4.2f    // 18650 fully charged
#define BATT_MIN_VOLTAGE      3.0f    // 18650 minimum safe voltage
#define ADC_REF_VOLTAGE       3.3f    // ESP32 ADC reference
#define ADC_MAX_VALUE         4095    // 12-bit ADC

// ============================================================
// GLOBALS
// ============================================================

Adafruit_MPU6050 mpu;

// Outgoing packet (reused each send cycle)
GloveToRobotPacket glove_packet;

// Packet counter — increments every transmission
uint16_t packet_counter = 0;

// Last send timestamp
unsigned long last_send_ms = 0;

// ACK tracking
volatile bool ack_received = false;
volatile uint16_t last_ack_id = 0;
uint8_t missed_ack_count = 0;
const uint8_t MAX_MISSED_ACK = 10;

// Peer info for ESP-NOW
esp_now_peer_info_t robot_peer;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================

void init_espnow();
void send_glove_packet();
uint8_t read_flex_percent(int pin_index);
float read_battery_voltage();
uint8_t voltage_to_percent(float voltage);
cynexis_gesture_t detect_gesture(const uint8_t flex[5],
                                  float roll, float pitch);
void on_data_sent(const uint8_t* mac, esp_now_send_status_t status);
void on_data_recv(const uint8_t* mac, const uint8_t* data, int len);
void blink_status(int times, int period_ms);

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(115200);
    Serial.println("[CYNEXIS] Control Glove booting...");

    // Status LED
    pinMode(PIN_STATUS_LED, OUTPUT);
    blink_status(3, 200);

    // --------------------------------------------------------
    // Software watchdog — 5 second timeout
    // --------------------------------------------------------
    esp_task_wdt_init(WATCHDOG_TIMEOUT_S, true);  // panic=true causes reset
    esp_task_wdt_add(NULL);
    Serial.println("[WDT] Watchdog armed: " + String(WATCHDOG_TIMEOUT_S) + "s");

    // --------------------------------------------------------
    // MPU6050
    // --------------------------------------------------------
    Wire.begin(21, 22);  // SDA=21, SCL=22
    if (!mpu.begin()) {
        Serial.println("[ERROR] MPU6050 not found! Check wiring.");
        // Non-fatal on glove — continue without IMU
        blink_status(10, 100);
    } else {
        mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        Serial.println("[IMU] MPU6050 initialised.");
    }

    // --------------------------------------------------------
    // Flex sensor ADC pins (input-only, no pinMode needed for ADC)
    // --------------------------------------------------------
    analogReadResolution(12);   // 12-bit ADC (0–4095)
    analogSetAttenuation(ADC_11db);  // Full 0–3.3V range

    // --------------------------------------------------------
    // Wi-Fi in Station mode (required for ESP-NOW)
    // --------------------------------------------------------
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    // --------------------------------------------------------
    // ESP-NOW initialisation
    // --------------------------------------------------------
    init_espnow();

    // --------------------------------------------------------
    // Initialise packet template (fields that never change)
    // --------------------------------------------------------
    memset(&glove_packet, 0, sizeof(GloveToRobotPacket));
    glove_packet.magic        = PACKET_MAGIC_GLOVE_TO_ROBOT;
    glove_packet.protocol_ver = CYNEXIS_PROTOCOL_VERSION;

    Serial.println("[CYNEXIS] Control Glove ready. Sending at 50Hz.");
    blink_status(2, 500);
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
    // Feed the watchdog — must happen every iteration
    esp_task_wdt_reset();

    unsigned long now = millis();

    // Send packet at configured interval (default 20ms = 50Hz)
    if (now - last_send_ms >= GLOVE_SEND_INTERVAL_MS) {
        last_send_ms = now;
        send_glove_packet();
    }
}

// ============================================================
// PACKET CONSTRUCTION & SEND
// ============================================================

void send_glove_packet() {
    // --- Packet ID and timestamp ---
    glove_packet.packet_id    = packet_counter++;
    glove_packet.timestamp_ms = millis();

    // --- Read flex sensors (0–100% bend) ---
    glove_packet.flex[0] = read_flex_percent(0);  // thumb
    glove_packet.flex[1] = read_flex_percent(1);  // index
    glove_packet.flex[2] = read_flex_percent(2);  // middle
    glove_packet.flex[3] = read_flex_percent(3);  // ring
    glove_packet.flex[4] = read_flex_percent(4);  // pinky

    // --- Read IMU ---
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);

    // Compute roll and pitch from accelerometer (degrees)
    float roll  = atan2(accel.acceleration.y, accel.acceleration.z)
                  * 180.0f / PI;
    float pitch = atan2(-accel.acceleration.x,
                        sqrt(accel.acceleration.y * accel.acceleration.y +
                             accel.acceleration.z * accel.acceleration.z))
                  * 180.0f / PI;

    // Integrate gyro Z for yaw (simple integration, not filtered)
    // For production, replace with Madgwick or Mahony filter
    static float yaw = 0.0f;
    static unsigned long last_imu_ms = 0;
    unsigned long now = millis();
    float dt = (now - last_imu_ms) / 1000.0f;
    last_imu_ms = now;
    yaw += gyro.gyro.z * dt * (180.0f / PI);
    if (yaw >  180.0f) yaw -= 360.0f;
    if (yaw < -180.0f) yaw += 360.0f;

    // Store as integer * 10 to preserve one decimal place
    glove_packet.roll_x10  = (int16_t)(roll  * 10.0f);
    glove_packet.pitch_x10 = (int16_t)(pitch * 10.0f);
    glove_packet.yaw_x10   = (int16_t)(yaw   * 10.0f);

    // --- Motor command from IMU ---
    //
    // Mapping (adjustable to taste):
    //   Pitch > +15°  → FORWARD
    //   Pitch < -15°  → REVERSE
    //   Roll  > +20°  → SPIN_RIGHT
    //   Roll  < -20°  → SPIN_LEFT
    //   else          → STOP

    const float TILT_FWD_REV = 15.0f;
    const float TILT_TURN    = 20.0f;

    if      (pitch >  TILT_FWD_REV) glove_packet.motor_cmd = MOTOR_FORWARD;
    else if (pitch < -TILT_FWD_REV) glove_packet.motor_cmd = MOTOR_REVERSE;
    else if (roll  >  TILT_TURN)    glove_packet.motor_cmd = MOTOR_SPIN_RIGHT;
    else if (roll  < -TILT_TURN)    glove_packet.motor_cmd = MOTOR_SPIN_LEFT;
    else                             glove_packet.motor_cmd = MOTOR_STOP;

    // --- Detect gesture ---
    glove_packet.gesture_id = (uint8_t)detect_gesture(
        glove_packet.flex, roll, pitch
    );

    // --- Arm control from gesture / finger positions ---
    //
    // Simple mapping:
    //   Gripper angle = inverted thumb bend (thumb close → gripper close)
    //   Elbow         = index finger bend mapped to 0–120°
    //   Shoulder      = pitch mapped to 30–150°
    //   Base          = yaw  mapped to 0–180°

    glove_packet.arm.gripper  = map(glove_packet.flex[0],  0, 100, 180, 0);
    glove_packet.arm.elbow    = map(glove_packet.flex[1],  0, 100, 0, 120);
    glove_packet.arm.shoulder = (uint8_t)constrain(
        map((int)pitch, -45, 45, 30, 150), 0, 180
    );
    glove_packet.arm.base     = (uint8_t)constrain(
        map((int)yaw, -90, 90, 0, 180), 0, 180
    );

    // --- Emergency flag ---
    glove_packet.emergency = (glove_packet.gesture_id == GESTURE_EMERGENCY_STOP)
                             ? 1 : 0;

    // --- Battery ---
    float batt_v = read_battery_voltage();
    glove_packet.glove_battery_pct = voltage_to_percent(batt_v);

    // --- Checksum ---
    gtr_set_checksum(&glove_packet);

    // --- Send via ESP-NOW ---
    esp_err_t result = esp_now_send(
        MAC_ROBOT,
        (const uint8_t*)&glove_packet,
        sizeof(GloveToRobotPacket)
    );

    if (result != ESP_OK) {
        Serial.println("[ESP-NOW] Send failed: " + String(esp_err_to_name(result)));
    }

    // Debug print every 50 packets (~1s at 50Hz)
    if (packet_counter % 50 == 0) {
        Serial.printf("[PKT %5u] Flex: %3u %3u %3u %3u %3u | "
                      "Roll: %6.1f Pitch: %6.1f Yaw: %6.1f | "
                      "Motor: 0x%02X | Batt: %3u%% | Emg: %u\n",
                      packet_counter,
                      glove_packet.flex[0], glove_packet.flex[1],
                      glove_packet.flex[2], glove_packet.flex[3],
                      glove_packet.flex[4],
                      roll, pitch, yaw,
                      glove_packet.motor_cmd,
                      glove_packet.glove_battery_pct,
                      glove_packet.emergency);
    }
}

// ============================================================
// FLEX SENSOR READING
// Returns 0 (straight) to 100 (fully bent) as uint8_t.
// ============================================================

uint8_t read_flex_percent(int finger_index) {
    int pin;
    switch (finger_index) {
        case 0: pin = PIN_FLEX_THUMB;  break;
        case 1: pin = PIN_FLEX_INDEX;  break;
        case 2: pin = PIN_FLEX_MIDDLE; break;
        case 3: pin = PIN_FLEX_RING;   break;
        case 4: pin = PIN_FLEX_PINKY;  break;
        default: return 0;
    }

    // Average 4 samples to reduce noise
    int raw = 0;
    for (int i = 0; i < 4; i++) raw += analogRead(pin);
    raw /= 4;

    int mapped = map(raw,
                     FLEX_OPEN[finger_index],
                     FLEX_CLOSED[finger_index],
                     0, 100);

    return (uint8_t)constrain(mapped, 0, 100);
}

// ============================================================
// BATTERY VOLTAGE READING
// ============================================================

float read_battery_voltage() {
    // Average 8 samples
    int raw = 0;
    for (int i = 0; i < 8; i++) raw += analogRead(PIN_BATT_SENSE);
    raw /= 8;

    float adc_v = (raw / (float)ADC_MAX_VALUE) * ADC_REF_VOLTAGE;
    return adc_v * BATT_VOLTAGE_DIVIDER;
}

uint8_t voltage_to_percent(float voltage) {
    float pct = (voltage - BATT_MIN_VOLTAGE)
              / (BATT_MAX_VOLTAGE - BATT_MIN_VOLTAGE)
              * 100.0f;
    return (uint8_t)constrain((int)pct, 0, 100);
}

// ============================================================
// GESTURE DETECTION
// ============================================================

cynexis_gesture_t detect_gesture(const uint8_t flex[5],
                                   float roll, float pitch) {
    bool thumb_bent  = (flex[0] > 70);
    bool index_bent  = (flex[1] > 60);
    bool middle_bent = (flex[2] > 60);
    bool ring_bent   = (flex[3] > 60);
    bool pinky_bent  = (flex[4] > 60);

    bool all_bent    = index_bent && middle_bent && ring_bent && pinky_bent;
    bool all_open    = !index_bent && !middle_bent && !ring_bent && !pinky_bent;

    // FIST — all fingers closed
    if (thumb_bent && all_bent)   return GESTURE_FIST;

    // OPEN HAND — all fingers open
    if (!thumb_bent && all_open)  return GESTURE_OPEN_HAND;

    // THUMBS UP — only thumb extended, others bent
    if (!thumb_bent && all_bent)  return GESTURE_THUMBS_UP;

    // POINT UP — index only extended, hand pitched up
    if (!index_bent && middle_bent && ring_bent && pinky_bent && pitch > 20)
        return GESTURE_POINT_UP;

    // POINT DOWN — index only extended, hand pitched down
    if (!index_bent && middle_bent && ring_bent && pinky_bent && pitch < -20)
        return GESTURE_POINT_DOWN;

    // PEACE SIGN — index + middle extended, others bent
    if (!index_bent && !middle_bent && ring_bent && pinky_bent)
        return GESTURE_PEACE;

    return GESTURE_NONE;
}

// ============================================================
// ESP-NOW INITIALISATION
// ============================================================

void init_espnow() {
    if (esp_now_init() != ESP_OK) {
        Serial.println("[FATAL] ESP-NOW init failed. Halting.");
        while (true) {
            blink_status(1, 100);
            delay(400);
        }
    }

    // Register callbacks
    esp_now_register_send_cb(on_data_sent);
    esp_now_register_recv_cb(on_data_recv);

    // Register robot as peer
    memset(&robot_peer, 0, sizeof(robot_peer));
    memcpy(robot_peer.peer_addr, MAC_ROBOT, 6);
    robot_peer.channel = ESPNOW_WIFI_CHANNEL;
    robot_peer.encrypt = false;

    if (esp_now_add_peer(&robot_peer) != ESP_OK) {
        Serial.println("[FATAL] Failed to add robot peer. Halting.");
        while (true) {
            blink_status(2, 100);
            delay(400);
        }
    }

    Serial.printf("[ESP-NOW] Robot peer registered: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  MAC_ROBOT[0], MAC_ROBOT[1], MAC_ROBOT[2],
                  MAC_ROBOT[3], MAC_ROBOT[4], MAC_ROBOT[5]);
}

// ============================================================
// ESP-NOW CALLBACKS
// ============================================================

/**
 * Called after esp_now_send() completes.
 * Only confirms that the MAC layer sent the frame — NOT that
 * the robot received and processed it.
 */
void on_data_sent(const uint8_t* mac, esp_now_send_status_t status) {
    if (status != ESP_NOW_SEND_SUCCESS) {
        Serial.println("[ESP-NOW] MAC-layer send failed.");
    }
}

/**
 * Called when an ACK packet is received from the robot.
 * Runs in an ISR context — keep it short.
 */
void on_data_recv(const uint8_t* mac, const uint8_t* data, int len) {
    if (len != sizeof(AckPacket)) return;  // Wrong size — ignore

    const AckPacket* ack = (const AckPacket*)data;

    if (!ack_validate(ack)) {
        // Checksum or magic mismatch — corrupted packet
        return;
    }

    ack_received   = true;
    last_ack_id    = ack->ack_packet_id;
    missed_ack_count = 0;  // Reset miss counter on valid ACK

    // Flash LED briefly to show link is alive
    digitalWrite(PIN_STATUS_LED, HIGH);
    // (LED is turned off in next loop iteration — non-blocking)
}

// ============================================================
// UTILITY
// ============================================================

void blink_status(int times, int period_ms) {
    for (int i = 0; i < times; i++) {
        digitalWrite(PIN_STATUS_LED, HIGH);
        delay(period_ms / 2);
        digitalWrite(PIN_STATUS_LED, LOW);
        delay(period_ms / 2);
    }
}

// ============================================================
// END OF control_glove.ino
// ============================================================
