/*
 * ============================================================
 * CYNEXIS — Dedicated LM393-LDR Light Sensor Isolated Test Sketch
 * ------------------------------------------------------------
 * Hardware Wiring:
 *   - LDR Module VCC : 3.3V
 *   - LDR Module GND : GND
 *   - LDR Module DO  : GPIO 2 (INPUT)
 * Baud Rate: 115200
 * ============================================================
 */

#include <Arduino.h>

#define PIN_LDR_DO 2

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n==================================================");
    Serial.println(" CYNEXIS — LM393 LDR SENSOR ISOLATED TEST ");
    Serial.println("==================================================");
    Serial.println("LDR DO Pin: GPIO 2");
    Serial.println("VCC       : 3.3V");
    Serial.println("Baud Rate : 115200");
    Serial.println("--------------------------------------------------");
    Serial.println("INSTRUCTIONS:");
    Serial.println(" 1. Observe state under normal room light.");
    Serial.println(" 2. Shine flashlight directly on LDR module.");
    Serial.println(" 3. Cover LDR sensor with hand to darken.");
    Serial.println(" 4. Adjust module potentiometer to tune sensitivity threshold.");
    Serial.println("--------------------------------------------------\n");

    pinMode(PIN_LDR_DO, INPUT);
    delay(100);
}

void loop() {
    int val = digitalRead(PIN_LDR_DO);

    if (val == HIGH) {
        Serial.println("LDR DO: HIGH | Raw Digital Output = 1");
    } else {
        Serial.println("LDR DO: LOW  | Raw Digital Output = 0");
    }

    delay(200); // Sample rate: ~5 Hz
}
