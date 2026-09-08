/*
 * ============================================================
 * CYNEXIS - CONTROL GLOVE ESP32
 * ============================================================
 *
 * Hardware:
 *   Thumb  -> GPIO34
 *   Index  -> GPIO35
 *   Middle -> GPIO32
 *   Ring   -> GPIO33
 *   Pinky  -> GPIO39 / SVP
 *
 *   MPU6050:
 *     SDA -> GPIO21
 *     SCL -> GPIO22
 *     VCC -> 3.3V
 *     GND -> GND
 *
 * ESP-NOW:
 *   Control Glove -> Robot
 *
 * IMPORTANT:
 *   This sketch uses the supplied:
 *     cynexis_mac.h
 *     cynexis_protocol.h
 *
 * ============================================================
 */

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <math.h>

#include "cynexis_mac.h"
#include "cynexis_protocol.h"

// ============================================================
// PIN DEFINITIONS
// ============================================================

#define FLEX_THUMB   34
#define FLEX_INDEX   35
#define FLEX_MIDDLE  32
#define FLEX_RING    33
#define FLEX_PINKY   39

#define MPU_SDA      21
#define MPU_SCL      22

#define MPU_ADDR     0x68

// ============================================================
// FLEX CALIBRATION
//
// Pinky calibration is based on the SVP test:
//
//   Straight ~= 0-100
//   Bent     ~= 3150
//
// Other fingers use wider safe ranges initially.
// We can refine these after testing the actual glove.
// ============================================================

struct FlexCalibration {
  int straight;
  int bent;
};

FlexCalibration flexCal[5] = {
  {500, 3000},   // Thumb
  {500, 3000},   // Index
  {300, 3000},   // Middle
  {500, 3000},   // Ring
  {50,  3150}    // Pinky / GPIO39
};

// ============================================================
// MPU6050 VARIABLES
// ============================================================

float ax_g = 0.0f;
float ay_g = 0.0f;
float az_g = 0.0f;

float gx_dps = 0.0f;
float gy_dps = 0.0f;
float gz_dps = 0.0f;

float rollDeg = 0.0f;
float pitchDeg = 0.0f;
float yawDeg = 0.0f;

float rollZero = 0.0f;
float pitchZero = 0.0f;

bool mpuOK = false;

// ============================================================
// ESP-NOW VARIABLES
// ============================================================

volatile bool lastDeliveryOK = false;
volatile bool deliveryResultReceived = false;

uint16_t packetCounter = 0;

unsigned long lastSendTime = 0;
unsigned long lastPrintTime = 0;

// ============================================================
// OPERATING MODE
// ============================================================

enum ControlMode {
  DRIVE_MODE = 0,
  ARM_MODE   = 1
};

ControlMode controlMode = DRIVE_MODE;

// ============================================================
// MPU REGISTER HELPERS
// ============================================================

void mpuWriteByte(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

uint8_t mpuReadByte(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom(MPU_ADDR, (uint8_t)1);

  if (Wire.available()) {
    return Wire.read();
  }

  return 0xFF;
}

bool mpuReadRaw(
  int16_t &accX,
  int16_t &accY,
  int16_t &accZ,
  int16_t &gyroX,
  int16_t &gyroY,
  int16_t &gyroZ
) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(MPU_ADDR, (uint8_t)14) != 14) {
    return false;
  }

  accX = (Wire.read() << 8) | Wire.read();
  accY = (Wire.read() << 8) | Wire.read();
  accZ = (Wire.read() << 8) | Wire.read();

  Wire.read();
  Wire.read();

  gyroX = (Wire.read() << 8) | Wire.read();
  gyroY = (Wire.read() << 8) | Wire.read();
  gyroZ = (Wire.read() << 8) | Wire.read();

  return true;
}

// ============================================================
// MPU INITIALIZATION
// ============================================================

bool initMPU6050() {

  uint8_t whoAmI = mpuReadByte(0x75);

  if (whoAmI != 0x68 && whoAmI != 0x69) {
    Serial.print("[MPU6050] Not detected. WHO_AM_I = 0x");
    Serial.println(whoAmI, HEX);
    return false;
  }

  // Wake up
  mpuWriteByte(0x6B, 0x00);

  delay(100);

  // Accelerometer ±2g
  mpuWriteByte(0x1C, 0x00);

  // Gyroscope ±250 deg/s
  mpuWriteByte(0x1B, 0x00);

  // Digital low-pass filter
  mpuWriteByte(0x1A, 0x03);

  delay(100);

  Serial.println("[MPU6050] Found and initialized.");

  return true;
}

// ============================================================
// READ MPU
// ============================================================

void readMPU() {

  int16_t rawAx;
  int16_t rawAy;
  int16_t rawAz;

  int16_t rawGx;
  int16_t rawGy;
  int16_t rawGz;

  if (!mpuReadRaw(
        rawAx,
        rawAy,
        rawAz,
        rawGx,
        rawGy,
        rawGz
      )) {

    mpuOK = false;
    return;
  }

  mpuOK = true;

  // ±2g => 16384 LSB/g
  ax_g = rawAx / 16384.0f;
  ay_g = rawAy / 16384.0f;
  az_g = rawAz / 16384.0f;

  // ±250 deg/s => 131 LSB/(deg/s)
  gx_dps = rawGx / 131.0f;
  gy_dps = rawGy / 131.0f;
  gz_dps = rawGz / 131.0f;

  /*
   * Calculate accelerometer orientation.
   *
   * The important part is that we calculate a baseline during
   * startup, so the physical mounting orientation of the MPU
   * does not automatically trigger the emergency stop.
   */

  float rawRoll =
    atan2f(ay_g, az_g) * 180.0f / PI;

  float rawPitch =
    atan2f(
      ax_g,
      sqrtf(ay_g * ay_g + az_g * az_g)
    ) * 180.0f / PI;

  rollDeg = rawRoll - rollZero;
  pitchDeg = rawPitch - pitchZero;

  // No magnetometer, therefore yaw is relative/gyro only.
  yawDeg = gz_dps;
}

// ============================================================
// MPU CALIBRATION
// ============================================================

void calibrateMPU() {

  Serial.println();
  Serial.println("[MPU6050] Keep glove STILL.");
  Serial.println("[MPU6050] Calibrating orientation...");

  delay(1000);

  float rollSum = 0.0f;
  float pitchSum = 0.0f;

  const int samples = 100;

  int valid = 0;

  for (int i = 0; i < samples; i++) {

    int16_t rawAx;
    int16_t rawAy;
    int16_t rawAz;

    int16_t rawGx;
    int16_t rawGy;
    int16_t rawGz;

    if (mpuReadRaw(
          rawAx,
          rawAy,
          rawAz,
          rawGx,
          rawGy,
          rawGz
        )) {

      float ax = rawAx / 16384.0f;
      float ay = rawAy / 16384.0f;
      float az = rawAz / 16384.0f;

      float r =
        atan2f(ay, az) * 180.0f / PI;

      float p =
        atan2f(
          ax,
          sqrtf(ay * ay + az * az)
        ) * 180.0f / PI;

      rollSum += r;
      pitchSum += p;

      valid++;
    }

    delay(10);
  }

  if (valid > 0) {

    rollZero = rollSum / valid;
    pitchZero = pitchSum / valid;

    Serial.print("[MPU6050] Roll zero  = ");
    Serial.println(rollZero, 2);

    Serial.print("[MPU6050] Pitch zero = ");
    Serial.println(pitchZero, 2);

    Serial.println("[MPU6050] Calibration complete.");
  }
}

// ============================================================
// FLEX READ
// ============================================================

int readFlexADC(uint8_t pin) {

  long total = 0;

  // Small averaging filter
  for (int i = 0; i < 4; i++) {
    total += analogRead(pin);
    delayMicroseconds(300);
  }

  return total / 4;
}

// ============================================================
// FLEX PERCENTAGE
// ============================================================

uint8_t flexToPercent(
  int adc,
  int straight,
  int bent
) {

  if (bent == straight) {
    return 0;
  }

  long value = map(
    adc,
    straight,
    bent,
    0,
    100
  );

  value = constrain(value, 0, 100);

  return (uint8_t)value;
}

// ============================================================
// READ ALL FLEX SENSORS
// ============================================================

void readFlexSensors(
  int adc[5],
  uint8_t flex[5]
) {

  const uint8_t pins[5] = {
    FLEX_THUMB,
    FLEX_INDEX,
    FLEX_MIDDLE,
    FLEX_RING,
    FLEX_PINKY
  };

  for (int i = 0; i < 5; i++) {

    adc[i] = readFlexADC(pins[i]);

    flex[i] = flexToPercent(
      adc[i],
      flexCal[i].straight,
      flexCal[i].bent
    );
  }
}

// ============================================================
// GESTURE DETECTION
// ============================================================

uint8_t detectGesture(const uint8_t flex[5]) {

  uint8_t thumb = flex[0];
  uint8_t index = flex[1];
  uint8_t middle = flex[2];
  uint8_t ring = flex[3];
  uint8_t pinky = flex[4];

  // Emergency fist / all fingers strongly bent
  if (
    thumb > 90 &&
    index > 90 &&
    middle > 90 &&
    ring > 90 &&
    pinky > 90
  ) {
    return GESTURE_FIST;
  }

  // Open hand
  if (
    thumb < 30 &&
    index < 30 &&
    middle < 30 &&
    ring < 30 &&
    pinky < 30
  ) {
    return GESTURE_OPEN_HAND;
  }

  // Point up
  if (
    index < 35 &&
    middle > 65 &&
    ring > 65 &&
    pinky > 65
  ) {
    return GESTURE_POINT_UP;
  }

  // Point down
  if (
    index > 65 &&
    middle > 65 &&
    ring > 65 &&
    pinky > 65
  ) {
    return GESTURE_POINT_DOWN;
  }

  // Thumbs up
  if (
    thumb < 35 &&
    index > 70 &&
    middle > 70 &&
    ring > 70 &&
    pinky > 70
  ) {
    return GESTURE_THUMBS_UP;
  }

  return GESTURE_NONE;
}

// ============================================================
// MOTOR CONTROL FROM TILT
// ============================================================

uint8_t getMotorCommand() {

  /*
   * Dead zone prevents small hand movements from moving rover.
   */

  const float DEAD_ZONE = 15.0f;

  if (pitchDeg > DEAD_ZONE) {
    return MOTOR_FORWARD;
  }

  if (pitchDeg < -DEAD_ZONE) {
    return MOTOR_REVERSE;
  }

  if (rollDeg > DEAD_ZONE) {
    return MOTOR_SPIN_RIGHT;
  }

  if (rollDeg < -DEAD_ZONE) {
    return MOTOR_SPIN_LEFT;
  }

  return MOTOR_STOP;
}

// ============================================================
// ARM COMMAND
// ============================================================

void createArmCommand(
  cynexis_arm_cmd_t &arm,
  uint8_t gesture
) {

  // Safe home position
  arm.base = 90;
  arm.shoulder = 90;
  arm.elbow = 90;
  arm.gripper = 180;

  if (controlMode != ARM_MODE) {
    return;
  }

  /*
   * Base follows roll.
   */
  float baseAngle =
    90.0f + rollDeg * 1.0f;

  /*
   * Shoulder follows pitch.
   */
  float shoulderAngle =
    90.0f + pitchDeg * 1.0f;

  arm.base =
    (uint8_t)constrain(
      (int)baseAngle,
      0,
      180
    );

  arm.shoulder =
    (uint8_t)constrain(
      (int)shoulderAngle,
      0,
      180
    );

  if (gesture == GESTURE_POINT_UP) {
    arm.elbow = 130;
  }

  if (gesture == GESTURE_POINT_DOWN) {
    arm.elbow = 50;
  }

  if (gesture == GESTURE_FIST) {
    arm.gripper = 20;
  }

  if (gesture == GESTURE_OPEN_HAND) {
    arm.gripper = 180;
  }
}

// ============================================================
// ESP-NOW SEND CALLBACK
// ============================================================

#if defined(ESP_IDF_VERSION_MAJOR) && ESP_IDF_VERSION_MAJOR >= 5

void onDataSent(
  const wifi_tx_info_t *info,
  esp_now_send_status_t status
) {

  lastDeliveryOK =
    (status == ESP_NOW_SEND_SUCCESS);

  deliveryResultReceived = true;
}

#else

void onDataSent(
  const uint8_t *mac_addr,
  esp_now_send_status_t status
) {

  lastDeliveryOK =
    (status == ESP_NOW_SEND_SUCCESS);

  deliveryResultReceived = true;
}

#endif

// ============================================================
// ESP-NOW INITIALIZATION
// ============================================================

bool initESPNow() {

  WiFi.mode(WIFI_STA);

  delay(100);

  // Force channel 1
  esp_wifi_set_channel(
    ESPNOW_WIFI_CHANNEL,
    WIFI_SECOND_CHAN_NONE
  );

  Serial.print("[SYSTEM] Control MAC: ");
  Serial.println(WiFi.macAddress());

  Serial.print("[SYSTEM] Wi-Fi channel: ");
  Serial.println(ESPNOW_WIFI_CHANNEL);

  if (esp_now_init() != ESP_OK) {

    Serial.println(
      "[ESP-NOW] Initialization FAILED."
    );

    return false;
  }

  esp_now_register_send_cb(onDataSent);

  esp_now_peer_info_t peerInfo = {};

  memcpy(
    peerInfo.peer_addr,
    MAC_ROBOT,
    6
  );

  peerInfo.channel =
    ESPNOW_WIFI_CHANNEL;

  peerInfo.encrypt = false;

  if (esp_now_is_peer_exist(MAC_ROBOT)) {
    esp_now_del_peer(MAC_ROBOT);
  }

  esp_err_t result =
    esp_now_add_peer(&peerInfo);

  if (result != ESP_OK) {

    Serial.print(
      "[ESP-NOW] Robot peer registration FAILED: "
    );

    Serial.println(result);

    return false;
  }

  Serial.println(
    "[ESP-NOW] Robot peer registered."
  );

  Serial.println(
    "[ESP-NOW] Initialized successfully."
  );

  return true;
}

// ============================================================
// SEND CONTROL PACKET
// ============================================================

bool sendControlPacket(
  const uint8_t flex[5],
  uint8_t gesture,
  uint8_t motorCommand,
  const cynexis_arm_cmd_t &arm,
  bool emergency
) {

  GloveToRobotPacket packet = {};

  packet.magic =
    PACKET_MAGIC_GLOVE_TO_ROBOT;

  packet.protocol_ver =
    CYNEXIS_PROTOCOL_VERSION;

  packet.packet_id =
    packetCounter++;

  packet.timestamp_ms =
    millis();

  for (int i = 0; i < 5; i++) {
    packet.flex[i] = flex[i];
  }

  packet.roll_x10 =
    (int16_t)constrain(
      (int)(rollDeg * 10.0f),
      -32768,
      32767
    );

  packet.pitch_x10 =
    (int16_t)constrain(
      (int)(pitchDeg * 10.0f),
      -32768,
      32767
    );

  packet.yaw_x10 =
    (int16_t)constrain(
      (int)(yawDeg * 10.0f),
      -32768,
      32767
    );

  packet.motor_cmd =
    motorCommand;

  packet.gesture_id =
    gesture;

  packet.arm =
    arm;

  packet.emergency =
    emergency ? 1 : 0;

  packet.glove_battery_pct =
    100;

  gtr_set_checksum(&packet);

  esp_err_t result =
    esp_now_send(
      MAC_ROBOT,
      (uint8_t *)&packet,
      sizeof(packet)
    );

  if (result != ESP_OK) {

    Serial.print(
      "[ESP-NOW] Queue send failed: "
    );

    Serial.println(result);

    return false;
  }

  return true;
}

// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  delay(1500);

  Serial.println();
  Serial.println(
    "========================================"
  );
  Serial.println(
    "[CYNEXIS] Control Glove booting..."
  );
  Serial.println(
    "========================================"
  );

  // ----------------------------------------------------------
  // ADC
  // ----------------------------------------------------------

  analogReadResolution(12);

  analogSetPinAttenuation(
    FLEX_THUMB,
    ADC_11db
  );

  analogSetPinAttenuation(
    FLEX_INDEX,
    ADC_11db
  );

  analogSetPinAttenuation(
    FLEX_MIDDLE,
    ADC_11db
  );

  analogSetPinAttenuation(
    FLEX_RING,
    ADC_11db
  );

  analogSetPinAttenuation(
    FLEX_PINKY,
    ADC_11db
  );

  Serial.println(
    "[SENSORS] 5 flex ADC inputs configured."
  );

  Serial.println(
    "[SENSORS] Pinky = GPIO39 / SVP."
  );

  // ----------------------------------------------------------
  // I2C / MPU6050
  // ----------------------------------------------------------

  Wire.begin(
    MPU_SDA,
    MPU_SCL
  );

  Wire.setClock(400000);

  mpuOK =
    initMPU6050();

  if (mpuOK) {

    calibrateMPU();

  } else {

    Serial.println(
      "[MPU6050] WARNING: IMU unavailable."
    );
  }

  // ----------------------------------------------------------
  // ESP-NOW
  // ----------------------------------------------------------

  bool espNowOK =
    initESPNow();

  if (!espNowOK) {

    Serial.println(
      "[ESP-NOW] WARNING: communication unavailable."
    );
  }

  Serial.println();
  Serial.println(
    "========================================"
  );
  Serial.println(
    "[CYNEXIS] Control Glove ready."
  );
  Serial.println(
    "========================================"
  );

  Serial.println();
  Serial.println(
    "Keep glove still for a moment."
  );
  Serial.println(
    "Move fingers and tilt the glove to test."
  );
  Serial.println();
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {

  unsigned long now =
    millis();

  // ----------------------------------------------------------
  // Send at 50 Hz
  // ----------------------------------------------------------

  if (
    now - lastSendTime >=
    GLOVE_SEND_INTERVAL_MS
  ) {

    lastSendTime = now;

    // --------------------------------------------------------
    // Read flex sensors
    // --------------------------------------------------------

    int adc[5];

    uint8_t flex[5];

    readFlexSensors(
      adc,
      flex
    );

    // --------------------------------------------------------
    // Read MPU6050
    // --------------------------------------------------------

    if (mpuOK) {
      readMPU();
    }

    // --------------------------------------------------------
    // Detect gesture
    // --------------------------------------------------------

    uint8_t gesture =
      detectGesture(flex);

    // --------------------------------------------------------
    // Toggle drive/arm mode
    //
    // Thumbs-up must be held for several cycles so it does not
    // repeatedly toggle.
    // --------------------------------------------------------

    static bool thumbToggleLock = false;

    if (
      gesture == GESTURE_THUMBS_UP
    ) {

      if (!thumbToggleLock) {

        thumbToggleLock = true;

        if (controlMode == DRIVE_MODE) {
          controlMode = ARM_MODE;
        } else {
          controlMode = DRIVE_MODE;
        }

        Serial.println();
        Serial.println(
          "[MODE] CONTROL MODE CHANGED"
        );

        if (controlMode == DRIVE_MODE) {
          Serial.println(
            "[MODE] DRIVE MODE"
          );
        } else {
          Serial.println(
            "[MODE] ARM MODE"
          );
        }
      }

    } else {

      thumbToggleLock = false;
    }

    // --------------------------------------------------------
    // Emergency detection
    //
    // Only trigger on extreme DIFFERENTIAL tilt after
    // calibration, not on the physical mounting orientation.
    // --------------------------------------------------------

    bool emergency = false;

    if (
      fabsf(rollDeg) > 75.0f ||
      fabsf(pitchDeg) > 75.0f
    ) {

      emergency = true;
      gesture =
        GESTURE_EMERGENCY_STOP;
    }

    // --------------------------------------------------------
    // Motor command
    // --------------------------------------------------------

    uint8_t motorCommand =
      MOTOR_STOP;

    if (!emergency) {

      if (
        controlMode == DRIVE_MODE
      ) {

        motorCommand =
          getMotorCommand();

      } else {

        // Wheels locked during arm mode.
        motorCommand =
          MOTOR_STOP;
      }
    }

    // --------------------------------------------------------
    // Arm command
    // --------------------------------------------------------

    cynexis_arm_cmd_t arm;

    createArmCommand(
      arm,
      gesture
    );

    // --------------------------------------------------------
    // Emergency overrides everything
    // --------------------------------------------------------

    if (emergency) {

      motorCommand =
        MOTOR_STOP;

      arm.base = 90;
      arm.shoulder = 90;
      arm.elbow = 90;
      arm.gripper = 180;
    }

    // --------------------------------------------------------
    // Send packet
    // --------------------------------------------------------

    sendControlPacket(
      flex,
      gesture,
      motorCommand,
      arm,
      emergency
    );

    // --------------------------------------------------------
    // Serial diagnostics
    // --------------------------------------------------------

    if (
      now - lastPrintTime >= 200
    ) {

      lastPrintTime = now;

      Serial.println();

      Serial.print(
        "--- GLOVE OUT [Packet #"
      );

      Serial.print(packetCounter - 1);

      Serial.println("] ---");

      Serial.print(
        "Mode:     "
      );

      if (controlMode == DRIVE_MODE) {
        Serial.println(
          "DRIVE MODE (Rover)"
        );
      } else {
        Serial.println(
          "ARM MODE"
        );
      }

      Serial.print(
        "Flex ADC: T="
      );
      Serial.print(adc[0]);

      Serial.print(
        ", I="
      );
      Serial.print(adc[1]);

      Serial.print(
        ", M="
      );
      Serial.print(adc[2]);

      Serial.print(
        ", R="
      );
      Serial.print(adc[3]);

      Serial.print(
        ", P="
      );
      Serial.println(adc[4]);

      Serial.print(
        "Flex Map: T="
      );
      Serial.print(flex[0]);
      Serial.print("%, I=");
      Serial.print(flex[1]);
      Serial.print("%, M=");
      Serial.print(flex[2]);
      Serial.print("%, R=");
      Serial.print(flex[3]);
      Serial.print("%, P=");
      Serial.print(flex[4]);
      Serial.println("%");

      Serial.print(
        "IMU Map:  Roll="
      );
      Serial.print(rollDeg, 1);

      Serial.print(
        " deg | Pitch="
      );
      Serial.print(pitchDeg, 1);

      Serial.println(
        " deg"
      );

      Serial.print(
        "Cmds:     Motor=0x"
      );

      if (motorCommand < 16) {
        Serial.print("0");
      }

      Serial.print(
        motorCommand,
        HEX
      );

      Serial.print(
        " | Gesture="
      );

      Serial.print(
        gesture
      );

      Serial.print(
        " | E-Stop="
      );

      Serial.println(
        emergency ? 1 : 0
      );

      Serial.print(
        "Arm Jnt:  Base="
      );
      Serial.print(arm.base);

      Serial.print(
        " deg | Shldr="
      );
      Serial.print(arm.shoulder);

      Serial.print(
        " deg | Elbow="
      );
      Serial.print(arm.elbow);

      Serial.print(
        " deg | Grip="
      );
      Serial.print(arm.gripper);

      Serial.println(
        " deg"
      );

      if (deliveryResultReceived) {

        deliveryResultReceived = false;

        Serial.print(
          "DELIVERY: "
        );

        if (lastDeliveryOK) {
          Serial.println("OK");
        } else {
          Serial.println("FAILED");
        }
      }

      Serial.println(
        "----------------------------------------"
      );
    }
  }

  delay(1);
}