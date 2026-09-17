#ifndef FLEX_SENSOR_MANAGER_H
#define FLEX_SENSOR_MANAGER_H

#include <Arduino.h>
#include "config.h"

/**
 * @brief Raw readings for all 5 flex sensors (12-bit ADC: 0 - 4095).
 */
struct FlexReadings {
    uint16_t thumb;
    uint16_t index;
    uint16_t middle;
    uint16_t ring;
    uint16_t pinky;

    uint16_t getByIndex(uint8_t idx) const {
        switch (idx) {
            case 0: return thumb;
            case 1: return index;
            case 2: return middle;
            case 3: return ring;
            case 4: return pinky;
            default: return 0;
        }
    }
};

/**
 * @brief Manages fixed-rate acquisition of 5 analog flex sensor channels.
 * 
 * Task 2.1 Scope: Fixed-rate raw acquisition -> uint16_t readings -> Serial diagnostics.
 */
class FlexSensorManager {
public:
    FlexSensorManager();

    /**
     * @brief Initializes GPIO pin modes and ADC settings.
     */
    void begin();

    /**
     * @brief Polls sensors at a fixed time interval (non-blocking).
     * @return true if a new sample was acquired in this call.
     */
    bool update();

    /**
     * @brief Forces an immediate raw sample read of all 5 flex channels.
     */
    void readRaw();

    /**
     * @brief Get the latest acquired raw readings.
     * @return Reference to current FlexReadings struct.
     */
    const FlexReadings& getReadings() const;

    /**
     * @brief Output formatted raw diagnostics over Serial.
     */
    void printDiagnostics() const;

private:
    FlexReadings m_readings;
    unsigned long m_lastSampleTime;
    uint32_t m_sampleCount;

    uint16_t sampleAnalogPin(uint8_t pin);
};

#endif // FLEX_SENSOR_MANAGER_H
