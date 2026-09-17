#include "ui.h"
#include "ui_home.h"
#include "ui_rover.h"
#include "ui_arm.h"
#include "ui_apps.h"

static lv_obj_t * screen_home = NULL;
static lv_obj_t * screen_rover = NULL;
static lv_obj_t * screen_arm = NULL;
static lv_obj_t * screen_apps = NULL;

void ui_init(const SystemStatus &initial_status) {
    // Create screens
    screen_home  = ui_home_create(initial_status);
    screen_rover = ui_rover_create();
    screen_arm   = ui_arm_create();
    screen_apps  = ui_apps_create();

    // Start non-blocking CYNEXIS boot animation (0.0s - 6.0s sequence)
    // Automatically transitions to screen_home when complete.
    ui_boot_start(screen_home);
}

void ui_switch_to(ScreenId screen) {
    switch (screen) {
        case SCREEN_HOME:
            if (screen_home) lv_scr_load(screen_home);
            break;
        case SCREEN_ROVER:
            if (screen_rover) lv_scr_load(screen_rover);
            break;
        case SCREEN_ARM:
            if (screen_arm) lv_scr_load(screen_arm);
            break;
        case SCREEN_APPS:
            if (screen_apps) lv_scr_load(screen_apps);
            break;
        case SCREEN_ASSISTANT:
            Serial.println("[UI NAV] Assistant App tapped (screen pending implementation)");
            break;
        case SCREEN_CAMERA:
            Serial.println("[UI NAV] Camera App tapped (screen pending implementation)");
            break;
        case SCREEN_DEMO:
            Serial.println("[UI NAV] Demo App tapped (screen pending implementation)");
            break;
        case SCREEN_GALLERY:
            Serial.println("[UI NAV] Gallery App tapped (screen pending implementation)");
            break;
        case SCREEN_CONTROL:
            Serial.println("[UI NAV] Control App tapped (screen pending implementation)");
            break;
        case SCREEN_STATUS:
            Serial.println("[UI NAV] Status App tapped (screen pending implementation)");
            break;
        case SCREEN_ALERTS:
            Serial.println("[UI NAV] Alerts App tapped (screen pending implementation)");
            break;
        case SCREEN_EMERGENCY:
            Serial.println("[APP DRAWER] Emergency selected");
            break;
        case SCREEN_SETTINGS:
            Serial.println("[APP DRAWER] Settings selected");
            break;
        case SCREEN_LOGS:
            Serial.println("[APP DRAWER] Logs selected");
            break;
        case SCREEN_CALIBRATION:
            Serial.println("[APP DRAWER] Calibration selected");
            break;
    }
}
