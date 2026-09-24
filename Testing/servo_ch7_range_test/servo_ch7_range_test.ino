/*
 * CYNEXIS — PCA9685 CH7 Range Test (MG996R #7)
 * 
 * Hardware Target:
 *   - ESP32: SDA = GPIO 21, SCL = GPIO 22
 *   - PCA9685 Address: 0x40
 *   - Target Channel: CH7 ONLY (MG996R #7)
 *   - Servo Power: XL4016 = 5.00V External Servo Supply
 *   - Horn Status: DETACHED (Mandatory unloaded safety)
 * 
 * Movement Sequence:
 *   90° --> 60° --> 90° --> 120° --> 90° (Gradual 0.5° steps @ 30ms)
 */

#include <Wire.h>

#define SDA_PIN       21
#define SCL_PIN       22
#define PCA9685_ADDR  0x40
#define TARGET_CH     7      // CH7 ONLY (MG996R #7)

#define MODE1         0x00
#define MODE2         0x01
#define PRESCALE      0xFE

// Microseconds for MG996R pulse width (500us = 0°, 1500us = 90°, 2500us = 180°)
#define MIN_US        500
#define MAX_US        2500

void pcaWriteReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setPWM(uint8_t channel, uint16_t on, uint16_t off) {
  uint8_t reg = 0x06 + (4 * channel); // For CH7: 0x06 + 4*7 = 0x22
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
  // 50 Hz period = 20,000 us across 4096 ticks
  uint16_t ticks = (uint16_t)((us / 20000.0) * 4096.0 + 0.5);
  return ticks;
}

void setServoAngle(float angle) {
  uint16_t ticks = angleToTicks(angle);
  setPWM(TARGET_CH, 0, ticks);
}

void moveGradual(float startAngle, float endAngle, int stepDelayMs) {
  float step = (endAngle > startAngle) ? 0.5 : -0.5;
  float current = startAngle;
  
  while ((step > 0 && current <= endAngle) || (step < 0 && current >= endAngle)) {
    setServoAngle(current);
    delay(stepDelayMs);
    current += step;
  }
  setServoAngle(endAngle);
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); }

  Serial.println("\n==========================================");
  Serial.println(" CYNEXIS — PCA9685 CH7 RANGE TEST (60-120°) ");
  Serial.println("==========================================");
  Serial.println("Target: MG996R #7 on PCA9685 CH7 ONLY");
  Serial.println("Power: XL4016 = 5.00V");
  Serial.println("Horn: DETACHED");
  Serial.println("Sequence: 90° -> 60° -> 90° -> 120° -> 90°");
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

  Serial.println("\n[SETUP] Initializing CH7 to 90° Center...");
  setServoAngle(90.0);
  delay(2000);
}

void loop() {
  Serial.println("\n--- Starting CH7 Range Test Cycle ---");

  Serial.println("[STEP 1] Moving Gradually: 90° --> 60°");
  moveGradual(90.0, 60.0, 30);
  delay(2000);

  Serial.println("[STEP 2] Moving Gradually: 60° --> 90°");
  moveGradual(60.0, 90.0, 30);
  delay(2000);

  Serial.println("[STEP 3] Moving Gradually: 90° --> 120°");
  moveGradual(90.0, 120.0, 30);
  delay(2000);

  Serial.println("[STEP 4] Returning to Center: 120° --> 90°");
  moveGradual(120.0, 90.0, 30);
  delay(2000);

  Serial.println("[CYCLE COMPLETE] Pausing 5s before next cycle...");
  delay(5000);
}
