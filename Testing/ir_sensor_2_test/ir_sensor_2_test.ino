/*
 * ============================================================
 * CYNEXIS — Dedicated IR Sensor #2 Isolated Test Sketch
 * ------------------------------------------------------------
 * Pin Assignments:
 *   - IR Sensor #2 OUT : GPIO 32 (INPUT)
 *   - VCC              : 3.3V
 *   - GND              : GND
 * Baud Rate: 115200
 * ============================================================
 */

#include <Arduino.h>

#define PIN_IR_SENSOR_2 32

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n==================================================");
    Serial.println(" CYNEXIS — IR SENSOR #2 TEST ");
    Serial.println("==================================================");
    Serial.println("GPIO: 32");
    Serial.println("VCC : 3.3V");
    Serial.println("Baud Rate: 115200");
    Serial.println("--------------------------------------------------\n");

    pinMode(PIN_IR_SENSOR_2, INPUT);
    delay(100);
}

void loop() {
    int val = digitalRead(PIN_IR_SENSOR_2);

    if (val == LOW) {
        Serial.println("IR: LOW  | OBJECT: DETECTED");
    } else {
        Serial.println("IR: HIGH | OBJECT: NOT DETECTED");
    }

    delay(200); // Sample rate: ~5 Hz
}
