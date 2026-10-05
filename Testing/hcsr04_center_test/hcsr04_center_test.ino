/*
 * ============================================================
 * CYNEXIS — Dedicated Center HC-SR04 Ultrasonic Test Sketch
 * ------------------------------------------------------------
 * Pin Assignments:
 *   - TRIG : GPIO 5
 *   - ECHO : GPIO 18 (via 10kΩ/20kΩ voltage divider to 3.3V)
 * Baud Rate: 115200
 * ============================================================
 */

#include <Arduino.h>

#define PIN_TRIG 5
#define PIN_ECHO 18

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n==================================================");
    Serial.println(" CYNEXIS — CENTER HC-SR04 ULTRASONIC TEST ");
    Serial.println("==================================================");
    Serial.println("TRIG Pin : GPIO 5");
    Serial.println("ECHO Pin : GPIO 18");
    Serial.println("Baud Rate: 115200");
    Serial.println("--------------------------------------------------\n");

    pinMode(PIN_TRIG, OUTPUT);
    pinMode(PIN_ECHO, INPUT);
    digitalWrite(PIN_TRIG, LOW);

    delay(500);
}

void loop() {
    // Clear TRIG pin
    digitalWrite(PIN_TRIG, LOW);
    delayMicroseconds(2);

    // Send 10µs pulse to TRIG
    digitalWrite(PIN_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);

    // Read pulse duration on ECHO pin (25ms timeout ~ 430cm max range)
    long duration = pulseIn(PIN_ECHO, HIGH, 25000);

    if (duration == 0) {
        Serial.println("[HC-SR04 CENTER] TIMEOUT / NO ECHO (Sensor out of range or disconnected)");
    } else {
        float distanceCm = (duration * 0.0343f) / 2.0f;
        float distanceInches = distanceCm * 0.393701f;
        Serial.printf("[HC-SR04 CENTER] Distance: %.2f cm  (%.2f in)  [Pulse: %ld us]\n", 
                      distanceCm, distanceInches, duration);
    }

    delay(500); // Test loop rate: 2 Hz
}
