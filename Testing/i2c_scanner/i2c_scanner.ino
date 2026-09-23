/*
 * CYNEXIS Subsystem Validation: PCA9685 I2C Address Verification
 * Target Hardware: ESP32 Dev Module (WROOM-32)
 * Serial Baud: 115200
 * Pins: SDA = GPIO 21, SCL = GPIO 22
 * Expected Address: 0x40
 */

#include <Wire.h>

#define SDA_PIN 21
#define SCL_PIN 22

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); } // Short wait for serial
  
  Serial.println("\n==========================================");
  Serial.println("   CYNEXIS I2C SCANNER — PCA9685 CHECK   ");
  Serial.println("==========================================");
  Serial.println("Target: PCA9685 PWM Driver");
  Serial.println("Expected Address: 0x40");
  Serial.println("Pins: SDA=21, SCL=22");
  Serial.println("------------------------------------------");
  
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); // 100 kHz standard I2C speed
}

void loop() {
  byte error, address;
  int nDevices = 0;

  Serial.println("\n[SCAN] Scanning I2C bus...");

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("  [FOUND] Device detected at I2C address 0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      if (address == 0x40) {
        Serial.print("  <-- PCA9685 CONFIRMED!");
      }
      Serial.println();
      nDevices++;
    } else if (error == 4) {
      Serial.print("  [ERROR] Unknown error at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }

  if (nDevices == 0) {
    Serial.println("  [WARNING] No I2C devices found on SDA=21, SCL=22!");
  } else {
    Serial.print("  [SUMMARY] Total devices found: ");
    Serial.println(nDevices);
  }

  delay(3000); // Rescan every 3 seconds
}
