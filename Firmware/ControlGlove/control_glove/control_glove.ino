/*
 * CYNEXIS - 3 FLEX SENSOR TEST
 *
 * Temporary diagnostic firmware.
 *
 * Connected sensors:
 *   Thumb  -> GPIO 34
 *   Index  -> GPIO 35
 *   Middle -> GPIO 32
 *
 * Ring and Pinky are intentionally ignored.
 *
 * ESP-NOW is intentionally disabled for this test.
 */

#define PIN_FLEX_THUMB   34
#define PIN_FLEX_INDEX   35
#define PIN_FLEX_MIDDLE  32

#define SERIAL_BAUD      115200

void setup() {
    Serial.begin(SERIAL_BAUD);

    delay(1000);

    // ESP32 ADC configuration
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    Serial.println();
    Serial.println("========================================");
    Serial.println(" CYNEXIS - 3 FLEX SENSOR TEST");
    Serial.println("========================================");
    Serial.println("Thumb  -> GPIO 34");
    Serial.println("Index  -> GPIO 35");
    Serial.println("Middle -> GPIO 32");
    Serial.println("Ring   -> NOT CONNECTED");
    Serial.println("Pinky  -> NOT CONNECTED");
    Serial.println("----------------------------------------");
    Serial.println("ESP-NOW: DISABLED");
    Serial.println("Reading raw ADC values...");
    Serial.println("----------------------------------------");
}

void loop() {

    // Read the three connected flex sensors
    int thumb  = analogRead(PIN_FLEX_THUMB);
    int index  = analogRead(PIN_FLEX_INDEX);
    int middle = analogRead(PIN_FLEX_MIDDLE);

    // Print raw readings
    Serial.print("Thumb: ");
    Serial.print(thumb);

    Serial.print(" | Index: ");
    Serial.print(index);

    Serial.print(" | Middle: ");
    Serial.println(middle);

    delay(100);
}