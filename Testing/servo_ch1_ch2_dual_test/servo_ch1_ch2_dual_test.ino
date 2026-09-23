/*
 * CYNEXIS — PCA9685 Dual Servo Simultaneous Test (CH1 + CH2)
 * 
 * Hardware Target:
 *   - ESP32: SDA = GPIO 21, SCL = GPIO 22
 *   - PCA9685 Address: 0x40
 *   - Active Channels: CH1 (MG996R #1) AND CH2 (MG996R #2)
 *   - Servo Power: XL4016 = 5.00V External Servo Supply
 *   - Horn Status: DETACHED on BOTH Servos
 * 
 * Simultaneous Sequence:
 *   START:   CH1 = 90°,  CH2 = 90°
 *   PHASE 1: CH1 = 60°,  CH2 = 120°
 *   PHASE 2: CH1 = 90°,  CH2 = 90°
 *   PHASE 3: CH1 = 120°, CH2 = 60°
 *   PHASE 4: CH1 = 90°,  CH2 = 90°
 */

#include <Wire.h>

#define SDA_PIN       21
#define SCL_PIN       22
#define PCA9685_ADDR  0x40

#define CH1           1      // MG996R #1
#define CH2           2      // MG996R #2

#define MODE1         0x00
#define MODE2         0x01
#define PRESCALE      0xFE

#define MIN_US        500
#define MAX_US        2500

void pcaWriteReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setPWM(uint8_t channel, uint16_t on, uint16_t off) {
  uint8_t reg = 0x06 + (4 * channel);
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  Wire.write(on & 0xFF);
  Wire.write(on >> 8);
  Wire.write(off & 0xFF);
  Wire.write(off >> 8);
  Wire.endTransmission();
}

uint16_t angleToTicks(float angle) {
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  
  float us = MIN_US + (angle / 180.0) * (MAX_US - MIN_US);
  uint16_t ticks = (uint16_t)((us / 20000.0) * 4096.0 + 0.5);
  return ticks;
}

void setServoAngle(uint8_t channel, float angle) {
  uint16_t ticks = angleToTicks(angle);
  setPWM(channel, 0, ticks);
}

void moveDualGradual(float start1, float end1, float start2, float end2, int stepDelayMs) {
  float step1 = (end1 > start1) ? 0.5 : -0.5;
  float step2 = (end2 > start2) ? 0.5 : -0.5;
  
  float current1 = start1;
  float current2 = start2;
  
  bool active1 = true;
  bool active2 = true;

  while (active1 || active2) {
    if (active1) {
      setServoAngle(CH1, current1);
      if ((step1 > 0 && current1 >= end1) || (step1 < 0 && current1 <= end1)) {
        current1 = end1;
        setServoAngle(CH1, current1);
        active1 = false;
      } else {
        current1 += step1;
      }
    }

    if (active2) {
      setServoAngle(CH2, current2);
      if ((step2 > 0 && current2 >= end2) || (step2 < 0 && current2 <= end2)) {
        current2 = end2;
        setServoAngle(CH2, current2);
        active2 = false;
      } else {
        current2 += step2;
      }
    }

    delay(stepDelayMs);
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); }

  Serial.println("\n==========================================");
  Serial.println(" CYNEXIS — DUAL SERVO TEST (CH1 + CH2)   ");
  Serial.println("==========================================");
  Serial.println("Target 1: MG996R #1 on PCA9685 CH1");
  Serial.println("Target 2: MG996R #2 on PCA9685 CH2");
  Serial.println("Power: XL4016 = 5.00V");
  Serial.println("Horns: DETACHED on BOTH servos");
  Serial.println("------------------------------------------");

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);

  // Initialize PCA9685
  pcaWriteReg(MODE1, 0x00);
  delay(10);

  // Set 50 Hz PWM frequency (Prescale 121 = 0x79)
  pcaWriteReg(MODE1, 0x10);          // Sleep mode
  pcaWriteReg(PRESCALE, 0x79);       // 50 Hz
  pcaWriteReg(MODE1, 0x00);          // Wake up
  delay(5);
  pcaWriteReg(MODE1, 0xA1);          // Auto-increment mode

  // Explicitly set MODE2 (0x01) = 0x04 (Totem-Pole output mode)
  pcaWriteReg(MODE2, 0x04);
  delay(5);

  // Clear all channels to OFF initially
  for (uint8_t ch = 0; ch < 16; ch++) {
    setPWM(ch, 0, 0);
  }

  Serial.println("\n[SETUP] Initializing CH1 and CH2 to 90° Center...");
  setServoAngle(CH1, 90.0);
  setServoAngle(CH2, 90.0);
  delay(2000);
}

void loop() {
  Serial.println("\n--- Starting Dual Servo Movement Cycle ---");

  // PHASE 1: CH1 -> 60°, CH2 -> 120°
  Serial.println("[PHASE 1] CH1 --> 60° | CH2 --> 120°");
  moveDualGradual(90.0, 60.0, 90.0, 120.0, 30);
  delay(2000);

  // PHASE 2: Both return to 90°
  Serial.println("[PHASE 2] CH1 --> 90° | CH2 --> 90°");
  moveDualGradual(60.0, 90.0, 120.0, 90.0, 30);
  delay(2000);

  // PHASE 3: CH1 -> 120°, CH2 -> 60°
  Serial.println("[PHASE 3] CH1 --> 120° | CH2 --> 60°");
  moveDualGradual(90.0, 120.0, 90.0, 60.0, 30);
  delay(2000);

  // PHASE 4: Both return to 90°
  Serial.println("[PHASE 4] CH1 --> 90° | CH2 --> 90°");
  moveDualGradual(120.0, 90.0, 60.0, 90.0, 30);
  delay(2000);

  Serial.println("[CYCLE COMPLETE] Pausing 5s before next cycle...");
  delay(5000);
}
