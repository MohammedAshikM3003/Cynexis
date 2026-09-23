/*
 * CYNEXIS — 5-Servo Simultaneous Test (CH1, CH2, CH3, CH4, CH5)
 * 
 * Hardware Target:
 *   - ESP32: SDA = GPIO 21, SCL = GPIO 22
 *   - PCA9685 Address: 0x40
 *   - Active Channels: CH1, CH2, CH3, CH4, CH5 (MG996R #1..#5)
 *   - Inactive Channels: CH0, CH6..CH15 (Held OFF)
 *   - Servo Power: XL4016 = 5.00V External Servo Supply
 *   - Horn Status: DETACHED on ALL 5 Servos
 * 
 * Lockstep Simultaneous Sequence:
 *   START:      CH1..CH5 = 90°
 *   POSITION A: CH1..CH5 -> 60°
 *   POSITION B: CH1..CH5 -> 90°
 *   POSITION C: CH1..CH5 -> 120°
 *   POSITION D: CH1..CH5 -> 90°
 */

#include <Wire.h>

#define SDA_PIN       21
#define SCL_PIN       22
#define PCA9685_ADDR  0x40

#define MODE1         0x00
#define MODE2         0x01
#define PRESCALE      0xFE

#define MIN_US        500
#define MAX_US        2500

const uint8_t ACTIVE_CHANNELS[] = {1, 2, 3, 4, 5};
const uint8_t NUM_ACTIVE = 5;

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

// Move all 5 active channels simultaneously in lockstep
void moveAll5Simultaneous(float startAngle, float endAngle, int stepDelayMs) {
  float step = (endAngle > startAngle) ? 0.5 : -0.5;
  float current = startAngle;
  
  while ((step > 0 && current <= endAngle) || (step < 0 && current >= endAngle)) {
    for (uint8_t i = 0; i < NUM_ACTIVE; i++) {
      setServoAngle(ACTIVE_CHANNELS[i], current);
    }
    delay(stepDelayMs);
    current += step;
  }
  
  // Ensure exact final target angle on all 5 channels
  for (uint8_t i = 0; i < NUM_ACTIVE; i++) {
    setServoAngle(ACTIVE_CHANNELS[i], endAngle);
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); }

  Serial.println("\n==========================================");
  Serial.println(" CYNEXIS — 5-SERVO SIMULTANEOUS TEST     ");
  Serial.println("==========================================");
  Serial.println("Active Channels: CH1, CH2, CH3, CH4, CH5");
  Serial.println("Inactive Channels: CH0, CH6..CH15 (OFF)");
  Serial.println("Power: XL4016 = 5.00V");
  Serial.println("Horns: DETACHED on ALL servos");
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

  // Clear all channels (0..15) to OFF initially
  for (uint8_t ch = 0; ch < 16; ch++) {
    setPWM(ch, 0, 0);
  }

  Serial.println("\n[SETUP] Initializing all 5 active servos to 90° Center...");
  for (uint8_t i = 0; i < NUM_ACTIVE; i++) {
    setServoAngle(ACTIVE_CHANNELS[i], 90.0);
  }
  delay(2000);
}

void loop() {
  Serial.println("\n--- Starting 5-Servo Simultaneous Movement Cycle ---");

  // POSITION A: All move together to 60°
  Serial.println("[POSITION A] Moving CH1..CH5 together: 90° --> 60°");
  moveAll5Simultaneous(90.0, 60.0, 30);
  delay(2000);

  // POSITION B: All return together to 90°
  Serial.println("[POSITION B] Returning CH1..CH5 together: 60° --> 90°");
  moveAll5Simultaneous(60.0, 90.0, 30);
  delay(2000);

  // POSITION C: All move together to 120°
  Serial.println("[POSITION C] Moving CH1..CH5 together: 90° --> 120°");
  moveAll5Simultaneous(90.0, 120.0, 30);
  delay(2000);

  // POSITION D: All return together to 90°
  Serial.println("[POSITION D] Returning CH1..CH5 together: 120° --> 90°");
  moveAll5Simultaneous(120.0, 90.0, 30);
  delay(2000);

  Serial.println("[CYCLE COMPLETE] Pausing 5s before next cycle...");
  delay(5000);
}
