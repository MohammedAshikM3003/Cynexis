#ifndef UI_H
#define UI_H

#include <lvgl.h>
#include "ui_status_card.h"

enum ScreenId {
    SCREEN_HOME,
    SCREEN_ROVER,
    SCREEN_ARM,
    SCREEN_APPS,
    SCREEN_ASSISTANT,
    SCREEN_CAMERA,
    SCREEN_DEMO,
    SCREEN_GALLERY,
    SCREEN_CONTROL,
    SCREEN_STATUS,
    SCREEN_ALERTS,
    SCREEN_EMERGENCY,
    SCREEN_SETTINGS,
    SCREEN_LOGS,
    SCREEN_CALIBRATION
};

void ui_init(const SystemStatus &initial_status);
void ui_switch_to(ScreenId screen);

#endif // UI_H
