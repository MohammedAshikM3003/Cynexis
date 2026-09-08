#ifndef UI_STATUS_CARD_H
#define UI_STATUS_CARD_H

#include <lvgl.h>

enum IconType {
    ICON_ROVER = 0,
    ICON_CONTROL_GLOVE,
    ICON_STATUS_GLOVE
};

struct DeviceStatus {
    const char * title;
    bool connected;
    uint8_t battery;
    const char * state;
    uint32_t hex_color;
};

struct SystemStatus {
    DeviceStatus rover;
    DeviceStatus control_glove;
    DeviceStatus status_glove;
};

struct StatusCardUI {
    lv_obj_t * card_obj;
    lv_obj_t * status_dot;
    lv_obj_t * lbl_title;
    lv_obj_t * lbl_status;
    lv_obj_t * lbl_battery;
    lv_obj_t * bar_battery;
};

StatusCardUI ui_create_status_card(lv_obj_t * parent, int x, int y, int w, int h, const DeviceStatus &data, IconType icon_type);
void ui_update_status_card(StatusCardUI &ui, const DeviceStatus &data);

#endif // UI_STATUS_CARD_H
