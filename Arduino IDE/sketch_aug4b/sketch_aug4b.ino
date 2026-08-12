#include <Wire.h>

void setup() {
    Serial.begin(115200);
    Wire.begin(21, 22);

    Serial.println("Scanning...");

    byte error;

    for (byte address = 1; address < 127; address++) {
        Wire.beginTransmission(address);
        error = Wire.endTransmission();

        if (error == 0) {
            Serial.print("Found device at 0x");
            Serial.println(address, HEX);
        }
    }

    Serial.println("Done.");
}

void loop() {
}