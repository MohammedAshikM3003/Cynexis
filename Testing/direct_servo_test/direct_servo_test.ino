/*
 * CYNEXIS — Direct ESP32 GPIO Servo Diagnostic Test
 * 
 * Target: Test MG996R #1 directly from ESP32 GPIO 17
 * Purpose: Isolate whether issue is with MG996R servo vs PCA9685 driver output
 * 
 * Hardware Setup (DO NOT CONNECT YET):
 *   - Servo Signal (Yellow) -> ESP32 GPIO 17
 *   - Servo V+ (Red)        -> XL4016 5.01V Rail (UNCHANGED)
 *   - Servo GND (Brown)     -> Common GND Rail (UNCHANGED)
 * 
 * Pulse Width Range @ 50 Hz (20ms Period, 16-bit LEDC timer):
 *   - 1500 us (Center, ~90°)  = 4915 ticks
 *   - 1400 us (~81°)          = 4587 ticks
 *   - 1600 us (~99°)          = 5243 ticks
 */

#include <Arduino.h>

#define SERVO_PIN      17     // ESP32 GPIO 17
#define LEDC_CHANNEL   0      // LEDC Timer Channel 0
#define LEDC_FREQ      50     // 50 Hz Servo standard
#define LEDC_RES       16     // 16-bit resolution (0 - 65535)

// Microsecond to 16-bit tick conversion at 50 Hz (20,000 us period)
uint32_t usToTicks(uint32_t us) {
  return (uint32_t)((us / 20000.0) * 65535.0 + 0.5);
}

void writeServoUs(uint32_t us) {
  uint32_t ticks = usToTicks(us);
  ledcWrite(SERVO_PIN, ticks);
}

void moveGradualUs(uint32_t startUs, uint32_t endUs, int stepDelayMs) {
  int32_t step = (endUs > startUs) ? 10 : -10;
  int32_t current = startUs;

  while ((step > 0 && current <= (int32_t)endUs) || (step < 0 && current >= (int32_t)endUs)) {
    writeServoUs(current);
    delay(stepDelayMs);
    current += step;
  }
  writeServoUs(endUs);
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { delay(10); }

  Serial.println("\n==========================================");
  Serial.println("  CYNEXIS — DIRECT ESP32 SERVO DIAGNOSTIC ");
  Serial.println("==========================================");
  Serial.println("Target: MG996R #1 directly on GPIO 17");
  Serial.println("Power: XL4016 = 5.01V (External supply)");
  Serial.println("Horn: DETACHED");
  Serial.println("Sequence: 1500us -> 1400us -> 1500us -> 1600us -> 1500us");
  Serial.println("------------------------------------------");

  // Configure ESP32 LEDC hardware PWM (Core v3.x API)
  ledcAttach(SERVO_PIN, LEDC_FREQ, LEDC_RES);

  Serial.println("\n[SETUP] Initializing GPIO 17 PWM output at 1500us center...");
  writeServoUs(1500);
  delay(2000);
}

void loop() {
  Serial.println("\n--- Starting Direct Servo Pulse Sequence ---");

  Serial.println("[STEP 1] Holding 1500us (Center)...");
  writeServoUs(1500);
  delay(2000);

  Serial.println("[STEP 2] Moving Gradually: 1500us --> 1400us");
  moveGradualUs(1500, 1400, 20);
  delay(2000);

  Serial.println("[STEP 3] Moving Gradually: 1400us --> 1500us");
  moveGradualUs(1400, 1500, 20);
  delay(2000);

  Serial.println("[STEP 4] Moving Gradually: 1500us --> 1600us");
  moveGradualUs(1500, 1600, 20);
  delay(2000);

  Serial.println("[STEP 5] Returning to Center: 1600us --> 1500us");
  moveGradualUs(1600, 1500, 20);
  delay(2000);

  Serial.println("[CYCLE COMPLETE] Pausing 5s...");
  delay(5000);
}
