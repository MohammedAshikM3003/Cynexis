/*
 * CYNEXIS — PCA9685 Register Readback & Signal Diagnostic
 * 
 * Target: PCA9685 I2C Address 0x40
 * Purpose: Verify actual internal register values after setting CH1 to 1500us (307 ticks)
 */

#include <Wire.h>

#define SDA_PIN       21
#define SCL_PIN       22
#define PCA9685_ADDR  0x40
#define TARGET_CH     1      // CH1 ONLY

#define MODE1_REG     0x00
#define MODE2_REG     0x01
#define PRESCALE_REG  0xFE

void pcaWriteReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint8_t pcaReadReg(uint8_t reg, bool &success) {
  Wire.beginTransmission(PCA9685_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    success = false;
    return 0;
  }
  if (Wire.requestFrom((uint8_t)PCA9685_ADDR, (uint8_t)1) == 1) {
    success = true;
    return Wire.read();
  }
  success = false;
  return 0;
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

void printRegister(const char* name, uint8_t regAddr) {
  bool ok = false;
  uint8_t val = pcaReadReg(regAddr, ok);
  Serial.print("  [0x");
  if (regAddr < 16) Serial.print("0");
  Serial.print(regAddr, HEX);
  Serial.print("] ");
  Serial.print(name);
  Serial.print(": ");
  
  if (ok) {
    Serial.print("0x");
    if (val < 16) Serial.print("0");
    Serial.print(val, HEX);
    Serial.print(" (Dec: ");
    Serial.print(val);
    Serial.println(") -- READ SUCCESS");
  } else {
    Serial.println("READ FAILED!");
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); }

  Serial.println("\n==========================================");
  Serial.println(" CYNEXIS — PCA9685 REGISTER READBACK TEST ");
  Serial.println("==========================================");
  Serial.println("Address: 0x40 | SDA: 21 | SCL: 22");
  Serial.println("Target PWM: 50 Hz, CH1 = 1500us (307 ticks)");
  Serial.println("------------------------------------------");

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);

  // 1. Initialize PCA9685
  pcaWriteReg(MODE1_REG, 0x00);
  delay(10);

  // 2. Set 50 Hz PWM frequency (Prescale 121 = 0x79)
  pcaWriteReg(MODE1_REG, 0x10);          // Sleep mode
  pcaWriteReg(PRESCALE_REG, 0x79);       // 50 Hz
  pcaWriteReg(MODE1_REG, 0x00);          // Wake up
  delay(5);
  pcaWriteReg(MODE1_REG, 0xA1);          // Auto-increment mode

  // 3. Set MODE2 = 0x04 (Totem-pole)
  pcaWriteReg(MODE2_REG, 0x04);
  delay(5);

  // 4. Set CH1 to 1500us (307 ticks)
  setPWM(TARGET_CH, 0, 307);
  delay(10);

  Serial.println("\n--- READING BACK REGISTERS FROM PCA9685 ---");
  printRegister("MODE1    ", MODE1_REG);
  printRegister("MODE2    ", MODE2_REG);
  printRegister("PRESCALE ", PRESCALE_REG);
  
  // CH0 Base Registers (0x06 - 0x09)
  printRegister("CH0 ON_L ", 0x06);
  printRegister("CH0 ON_H ", 0x07);
  printRegister("CH0 OFF_L", 0x08);
  printRegister("CH0 OFF_H", 0x09);

  // CH1 Base Registers (0x0A - 0x0D)
  printRegister("CH1 ON_L ", 0x0A);
  printRegister("CH1 ON_H ", 0x0B);
  printRegister("CH1 OFF_L", 0x0C);
  printRegister("CH1 OFF_H", 0x0D);

  Serial.println("\n[DIAGNOSTIC COMPLETE] Static register dump finished.");
}

void loop() {
  // Static diagnostic -- no movement loops
  delay(5000);
}
