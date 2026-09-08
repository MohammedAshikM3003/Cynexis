#include <Arduino.h>
#include <lvgl.h>
#include "display/display.h"
#include "touch/touch.h"
#include "ui/ui.h"
#include "ui/ui_home.h"
#include "system/time_manager.h"

// System status with plain integer POD color representations
static SystemStatus sys_status = {
    .rover = {
        .title = "ROVER",
        .connected = true,
        .battery = 85,
        .state = "Ready",
        .hex_color = 0x2563EB // Vibrant Blue
    },
    .control_glove = {
        .title = "CONTROL GLOVE",
        .connected = true,
        .battery = 92,
        .state = "Ready",
        .hex_color = 0x0D9488 // Teal
    },
    .status_glove = {
        .title = "STATUS GLOVE",
        .connected = true,
        .battery = 78,
        .state = "Active",
        .hex_color = 0x4F46E5 // Indigo
    }
};

static TimeData g_time_data;

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("=========================================");
    Serial.println("   CYNEXIS ESP32 TOUCH DISPLAY SYSTEM    ");
    Serial.println("=========================================");

    // 1. Ensure TOUCH_CS is HIGH (deselected) before SPI initialization
    pinMode(TOUCH_CS, OUTPUT);
    digitalWrite(TOUCH_CS, HIGH);

    // 2. Hardware SPI touch setup FIRST (runs touch.begin())
    touch_hardware_init();

    // 3. Hardware TFT & LVGL setup SECOND (runs tft.init(), lv_init(), registers display driver)
    display_init();

    // 4. Register touch input driver with LVGL THIRD (after lv_init())
    touch_lvgl_init();

    // 5. Initialize Full UI (Home Screen + Wallpaper + Clock + Status Cards)
    ui_init(sys_status);

    // 6. Initialize Wi-Fi & NTP Time Manager
    time_manager_init();

    Serial.println("[SYSTEM] CYNEXIS Display Firmware Initialized Successfully!");
    Serial.println("=========================================");
}

void loop() {
    // 1. Precise millisecond tick increment for LVGL internal scheduler
    static uint32_t last_tick = millis();
    uint32_t now = millis();
    if (now != last_tick) {
        lv_tick_inc(now - last_tick);
        last_tick = now;
    }

    // 2. Execute LVGL internal task handler
    lv_timer_handler();

    // 3. Update NTP Time Manager & Refresh Home Clock UI
    if (time_manager_update(g_time_data)) {
        ui_home_update_clock(g_time_data);
    }

    delay(5);
}
