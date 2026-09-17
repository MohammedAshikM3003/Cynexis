#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

// ============================================================
// HARDWARE PIN DEFINITIONS - FLEX SENSORS (ADC1)
// ============================================================
#define PIN_FLEX_THUMB   34
#define PIN_FLEX_INDEX   35
#define PIN_FLEX_MIDDLE  32
#define PIN_FLEX_RING    33
#define PIN_FLEX_PINKY   39

// ============================================================
// ACQUISITION CONFIGURATION
// ============================================================
#define FLEX_SAMPLE_INTERVAL_MS 20  // 50 Hz acquisition rate
#define FLEX_NUM_SENSORS        5
#define FLEX_OVERSAMPLE_COUNT   4   // Number of samples for basic noise reduction

#endif // CONFIG_H
