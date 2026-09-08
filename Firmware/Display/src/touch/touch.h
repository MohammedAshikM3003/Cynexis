#ifndef TOUCH_H
#define TOUCH_H

#include <Arduino.h>
#include <SPI.h>
#include <XPT2046_Touchscreen.h>
#include <lvgl.h>

#define TOUCH_CS  33
#define TOUCH_IRQ 34

// Hardware Calibration Bounds (Verified on real hardware in Phase 3)
#define TOUCH_X_MIN 450
#define TOUCH_X_MAX 3650
#define TOUCH_Y_MIN 950
#define TOUCH_Y_MAX 3600

// Relaxed Pressure Z-Threshold for Light Finger Touch Sensitivity (Default was 300)
#ifndef Z_THRESHOLD
#define Z_THRESHOLD 150
#endif

extern XPT2046_Touchscreen touch;

void touch_hardware_init();
void touch_lvgl_init();
void touch_init();

#endif // TOUCH_H
