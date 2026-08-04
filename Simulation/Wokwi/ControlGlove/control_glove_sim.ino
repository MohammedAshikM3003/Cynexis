/**
 * ============================================================
 * CYNEXIS — Wokwi Simulation: Control Glove Full Test
 * File: control_glove_sim.ino
 * ------------------------------------------------------------
 * PURPOSE: Simulate and verify the full control glove circuit
 *          before hardware arrives.
 *
 * Simulated hardware:
 *   - ESP32 DevKit V1
 *   - 5x Potentiometers (simulate flex sensors)
 *   - MPU6050 IMU
 *   - Status LED (GPIO2)
 *
 * GPIO mapping:
 *   Flex Thumb   → GPIO34 (ADC1_CH6, input only)
 *   Flex Index   → GPIO35 (ADC1_CH7, input only)
 *   Flex Middle  → GPIO32 (ADC1_CH4)
 *   Flex Ring    → GPIO33 (ADC1_CH5)
 *   Flex Pinky   → GPIO39 (VP, ADC1_CH3, input only)
 *   MPU6050 SDA  → GPIO21
 *   MPU6050 SCL  → GPIO22
 *   Status LED   → GPIO2
 *
 * HOW TO USE IN WOKWI:
 *   1. Open https://wokwi.com
 *   2. Load diagram.json and this file
 *   3. Turn potentiometer knobs to simulate finger bending
 *   4. Watch Serial Monitor for live sensor data
 *   5. Verify: ADC values + roll/pitch/yaw printing
 * ============================================================
 */

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ============================================================
// PIN DEFINITIONS
// ============================================================
#define PIN_FLEX_THUMB    34
#define PIN_FLEX_INDEX    35
#define PIN_FLEX_MIDDLE   32
#define PIN_FLEX_RING     33
#define PIN_FLEX_PINKY    39   // VP — input only
#define PIN_STATUS_LED    2

// ============================================================
// CALIBRATION (adjust these after real hardware testing)
// ============================================================
// ADC range: 0 (straight) to 4095 (fully bent)
// Wokwi potentiometer: 0.0 (min) to 1.0 (max) maps to 0–3.3V
#define FLEX_STRAIGHT_ADC  1500   // ~1.2V when straight
#define FLEX_BENT_ADC      3500   // ~2.8V when fully bent

// ============================================================
// TIMING
// ============================================================
const uint32_t LOOP_TIME = 50;   // ms per loop iteration (~20 Hz)

// ============================================================
// GESTURE ENUM
// ============================================================
enum Gesture {
    GESTURE_OPEN,
    GESTURE_FIST,
    GESTURE_POINT,
    GESTURE_PARTIAL
};

// ============================================================
// OBJECTS
// ============================================================
Adafruit_MPU6050 mpu;

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_STATUS_LED, OUTPUT);

    // --------------------------------------------------------
    // Banner
    // --------------------------------------------------------
    Serial.println("============================================================");
    Serial.println("  CYNEXIS — Control Glove Simulation");
    Serial.println("  GPIO39 = Pinky | MPU6050 + 5x Flex sensors");
    Serial.println("============================================================\n");

    // --------------------------------------------------------
    // MPU6050 init
    // --------------------------------------------------------
    if (!mpu.begin()) {
        Serial.println("[ERROR] MPU6050 not found! Check SDA/SCL wiring.");
        while (1) {
            digitalWrite(PIN_STATUS_LED, HIGH); delay(100);
            digitalWrite(PIN_STATUS_LED, LOW);  delay(100);
        }
    }
    Serial.println("[OK] MPU6050 detected.");
    mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
    mpu.setGyroRange(MPU6050_RANGE_250_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

    // --------------------------------------------------------
    // ADC config
    // --------------------------------------------------------
    // 12-bit resolution: ADC values range 0–4095
    analogReadResolution(12);

    // ADC_11db attenuation: full 0–3.3V input range
    // Required for flex sensors which swing up to ~3.0V
    analogSetPinAttenuation(PIN_FLEX_THUMB,   ADC_11db);
    analogSetPinAttenuation(PIN_FLEX_INDEX,   ADC_11db);
    analogSetPinAttenuation(PIN_FLEX_MIDDLE,  ADC_11db);
    analogSetPinAttenuation(PIN_FLEX_RING,    ADC_11db);
    analogSetPinAttenuation(PIN_FLEX_PINKY,   ADC_11db);

    Serial.println("[OK] ADC: 12-bit, 11dB attenuation (0-3.3V range).");
    Serial.println("[OK] All systems ready. Starting loop...\n");

    // Startup blink
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_STATUS_LED, HIGH); delay(200);
        digitalWrite(PIN_STATUS_LED, LOW);  delay(200);
    }
}

// ============================================================
// LOOP
// ============================================================
void loop() {
    // --------------------------------------------------------
    // Read flex sensors (ADC)
    // --------------------------------------------------------
    int flex[5];
    flex[0] = analogRead(PIN_FLEX_THUMB);
    flex[1] = analogRead(PIN_FLEX_INDEX);
    flex[2] = analogRead(PIN_FLEX_MIDDLE);
    flex[3] = analogRead(PIN_FLEX_RING);
    flex[4] = analogRead(PIN_FLEX_PINKY);

    // Map to 0-100% bend
    int bend[5];
    for (int i = 0; i < 5; i++) {
        bend[i] = map(flex[i], FLEX_STRAIGHT_ADC, FLEX_BENT_ADC, 0, 100);
        bend[i] = constrain(bend[i], 0, 100);
    }

    // --------------------------------------------------------
    // Read MPU6050
    // --------------------------------------------------------
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);

    // Calculate roll and pitch from accelerometer
    float ax = accel.acceleration.x;
    float ay = accel.acceleration.y;
    float az = accel.acceleration.z;

    float roll  = atan2(ay, az) * 180.0 / PI;
    float pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;

    // --------------------------------------------------------
    // Serial output
    // --------------------------------------------------------
    Serial.println("------------------------------------------------------------");
    Serial.println("FLEX SENSORS");
    Serial.printf("  Thumb  (GPIO34): ADC=%4d  Bend=%3d%%\n", flex[0], bend[0]);
    Serial.printf("  Index  (GPIO35): ADC=%4d  Bend=%3d%%\n", flex[1], bend[1]);
    Serial.printf("  Middle (GPIO32): ADC=%4d  Bend=%3d%%\n", flex[2], bend[2]);
    Serial.printf("  Ring   (GPIO33): ADC=%4d  Bend=%3d%%\n", flex[3], bend[3]);
    Serial.printf("  Pinky  (GPIO39): ADC=%4d  Bend=%3d%%\n", flex[4], bend[4]);

    Serial.println("MPU6050");
    Serial.printf("  Roll:  %7.2f deg\n", roll);
    Serial.printf("  Pitch: %7.2f deg\n", pitch);
    Serial.printf("  AccX:  %6.3f m/s2\n", ax);
    Serial.printf("  AccY:  %6.3f m/s2\n", ay);
    Serial.printf("  AccZ:  %6.3f m/s2\n", az);

    // Detect basic gestures
    bool allBent   = (bend[0]>60 && bend[1]>60 && bend[2]>60 && bend[3]>60 && bend[4]>60);
    bool allOpen   = (bend[0]<20 && bend[1]<20 && bend[2]<20 && bend[3]<20 && bend[4]<20);
    bool indexOnly = (bend[1]<20 && bend[2]>60 && bend[3]>60 && bend[4]>60);

    Gesture g;
    if      (allBent)   g = GESTURE_FIST;
    else if (allOpen)   g = GESTURE_OPEN;
    else if (indexOnly) g = GESTURE_POINT;
    else                g = GESTURE_PARTIAL;

    const char* gestureNames[] = { "OPEN", "FIST", "POINT", "PARTIAL" };
    Serial.printf("GESTURE: %s\n", gestureNames[g]);

    Serial.println();

    // Heartbeat LED
    digitalWrite(PIN_STATUS_LED, HIGH); delay(50);
    digitalWrite(PIN_STATUS_LED, LOW);

    delay(LOOP_TIME);  // 50ms = ~20 Hz update rate
}
