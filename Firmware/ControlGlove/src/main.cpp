#include <Arduino.h>
#include "FlexSensorManager.h"

FlexSensorManager flexManager;

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("====================================================");
    Serial.println("CYNEXIS CONTROL GLOVE - TASK 2.1 RAW FLEX DIAGNOSTICS");
    Serial.println("5 Analog Flex Sensors -> Fixed-Rate Raw Acquisition");
    Serial.println("Pins: Thumb(34), Index(35), Middle(32), Ring(33), Pinky(39)");
    Serial.println("====================================================");

    flexManager.begin();
    Serial.println("[SYSTEM] FlexSensorManager initialized. Streaming raw acquisition...");
}

void loop() {
    if (flexManager.update()) {
        flexManager.printDiagnostics();
    }
}
