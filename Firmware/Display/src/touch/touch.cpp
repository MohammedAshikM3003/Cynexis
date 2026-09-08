#include "touch.h"
#include "../display/display.h"

XPT2046_Touchscreen touch(TOUCH_CS, 255); // Use 255 for software polling mode

// Read callback for LVGL touch driver with robust software validation & debouncing
static void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data) {
    static bool is_pressed = false;
    static int32_t last_valid_x = 0;
    static int32_t last_valid_y = 0;
    static int consecutive_valid_count = 0;

    if (touch.touched()) {
        TS_Point p = touch.getPoint();

        // 1. Filter out invalid/saturated/glitched raw samples
        if ((p.x == 0 && p.y == 0) || p.z >= 4000 || p.x < 200 || p.x > 3900 || p.y < 200 || p.y > 3900) {
            static uint32_t last_rej_log = 0;
            if (millis() - last_rej_log > 500) {
                Serial.printf("[TOUCH] Invalid raw sample rejected (p.x:%d, p.y:%d, p.z:%d)\n", p.x, p.y, p.z);
                last_rej_log = millis();
            }
            consecutive_valid_count = 0;
            if (is_pressed) {
                is_pressed = false;
                Serial.println("[TOUCH] Touch released");
            }
            data->state = LV_INDEV_STATE_REL;
            return;
        }

        // 2. Convert raw readings using LOCKED verified mapping
        int32_t x = map(p.x, TOUCH_Y_MIN, TOUCH_Y_MAX, SCREEN_WIDTH - 1, 0);
        int32_t y = map(p.y, TOUCH_X_MIN, TOUCH_X_MAX, SCREEN_HEIGHT - 1, 0);

        x = constrain(x, 0, SCREEN_WIDTH - 1);
        y = constrain(y, 0, SCREEN_HEIGHT - 1);

        // 3. Multi-sample debouncing: Require 2 consecutive spatial-consistent samples before declaring PRESSED
        if (!is_pressed) {
            if (consecutive_valid_count == 0) {
                last_valid_x = x;
                last_valid_y = y;
                consecutive_valid_count = 1;
                data->state = LV_INDEV_STATE_REL;
                return;
            } else {
                if (abs(x - last_valid_x) <= 25 && abs(y - last_valid_y) <= 25) {
                    consecutive_valid_count++;
                    if (consecutive_valid_count >= 2) {
                        is_pressed = true;
                        last_valid_x = x;
                        last_valid_y = y;
                        Serial.printf("[TOUCH] Stable touch accepted: x=%d, y=%d\n", x, y);
                    }
                } else {
                    last_valid_x = x;
                    last_valid_y = y;
                    consecutive_valid_count = 1;
                    data->state = LV_INDEV_STATE_REL;
                    return;
                }
            }
        } else {
            // Smooth touch tracking while pressed
            last_valid_x = (last_valid_x + x) / 2;
            last_valid_y = (last_valid_y + y) / 2;
        }

        if (is_pressed) {
            data->point.x = last_valid_x;
            data->point.y = last_valid_y;
            data->state = LV_INDEV_STATE_PR;

            static uint32_t last_log = 0;
            if (millis() - last_log > 500) {
                Serial.printf("[TOUCH DIAG] getPoint raw (p.x:%d, p.y:%d, p.z:%d) -> supplied lv_indev (x:%d, y:%d) LVGL=PRESSED\n",
                              p.x, p.y, p.z, data->point.x, data->point.y);
                last_log = millis();
            }
        } else {
            data->state = LV_INDEV_STATE_REL;
        }
    } else {
        consecutive_valid_count = 0;
        if (is_pressed) {
            is_pressed = false;
            Serial.println("[TOUCH] Touch released");
        }
        data->state = LV_INDEV_STATE_REL;
    }
}

void touch_hardware_init() {
    touch.begin();
    touch.setRotation(1); // Aligned with TFT display landscape rotation (Rotation 1)
}

void touch_lvgl_init() {
    // Register LVGL Touch Input Driver (MUST be called AFTER lv_init())
    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = my_touchpad_read;
    lv_indev_drv_register(&indev_drv);
}

void touch_init() {
    touch_hardware_init();
    touch_lvgl_init();
}
