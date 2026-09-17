#include "FlexSensorManager.h"

FlexSensorManager::FlexSensorManager()
    : m_readings{0, 0, 0, 0, 0}
    , m_lastSampleTime(0)
    , m_sampleCount(0)
{
}

void FlexSensorManager::begin() {
    pinMode(PIN_FLEX_THUMB, INPUT);
    pinMode(PIN_FLEX_INDEX, INPUT);
    pinMode(PIN_FLEX_MIDDLE, INPUT);
    pinMode(PIN_FLEX_RING, INPUT);
    pinMode(PIN_FLEX_PINKY, INPUT);

#if defined(ESP32)
    analogReadResolution(12); // 12-bit ADC (0 - 4095)
#endif

    // Initial read to populate valid values immediately
    readRaw();
}

uint16_t FlexSensorManager::sampleAnalogPin(uint8_t pin) {
#if FLEX_OVERSAMPLE_COUNT > 1
    uint32_t sum = 0;
    for (uint8_t i = 0; i < FLEX_OVERSAMPLE_COUNT; ++i) {
        sum += analogRead(pin);
    }
    return static_cast<uint16_t>(sum / FLEX_OVERSAMPLE_COUNT);
#else
    return static_cast<uint16_t>(analogRead(pin));
#endif
}

void FlexSensorManager::readRaw() {
    m_readings.thumb  = sampleAnalogPin(PIN_FLEX_THUMB);
    m_readings.index  = sampleAnalogPin(PIN_FLEX_INDEX);
    m_readings.middle = sampleAnalogPin(PIN_FLEX_MIDDLE);
    m_readings.ring   = sampleAnalogPin(PIN_FLEX_RING);
    m_readings.pinky  = sampleAnalogPin(PIN_FLEX_PINKY);
}

bool FlexSensorManager::update() {
    unsigned long currentMs = millis();
    if (currentMs - m_lastSampleTime >= FLEX_SAMPLE_INTERVAL_MS) {
        m_lastSampleTime = currentMs;
        readRaw();
        m_sampleCount++;
        return true;
    }
    return false;
}

const FlexReadings& FlexSensorManager::getReadings() const {
    return m_readings;
}

void FlexSensorManager::printDiagnostics() const {
    char buffer[128];
    snprintf(buffer, sizeof(buffer),
        "[FLEX #%lu] T: %4u | I: %4u | M: %4u | R: %4u | P: %4u",
        m_sampleCount,
        m_readings.thumb,
        m_readings.index,
        m_readings.middle,
        m_readings.ring,
        m_readings.pinky
    );
    Serial.println(buffer);
}
