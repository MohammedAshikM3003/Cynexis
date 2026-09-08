#include "ui_status_card.h"
#include "assets/rover_icon.h"
#include "assets/control_glove_icon.h"
#include "assets/status_glove_icon.h"
#include <stdio.h>

StatusCardUI ui_create_status_card(lv_obj_t * parent, int x, int y, int w, int h, const DeviceStatus &data, IconType icon_type) {
    StatusCardUI ui;

    // 1. Outer Card Background Container (White Card, 90% opacity, 9px radius, soft drop shadow)
    ui.card_obj = lv_obj_create(parent);
    lv_obj_set_size(ui.card_obj, w, h);
    lv_obj_set_pos(ui.card_obj, x, y);
    lv_obj_set_style_bg_color(ui.card_obj, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(ui.card_obj, LV_OPA_90, LV_PART_MAIN);
    lv_obj_set_style_radius(ui.card_obj, 9, LV_PART_MAIN);

    // Border & Outline: NONE
    lv_obj_set_style_border_width(ui.card_obj, 0, LV_PART_MAIN);
    lv_obj_set_style_outline_width(ui.card_obj, 0, LV_PART_MAIN);

    // Soft, Diffused Native LVGL Drop Shadow
    lv_obj_set_style_shadow_width(ui.card_obj, 6, LV_PART_MAIN);
    lv_obj_set_style_shadow_spread(ui.card_obj, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_x(ui.card_obj, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_y(ui.card_obj, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(ui.card_obj, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(ui.card_obj, LV_OPA_30, LV_PART_MAIN);

    lv_obj_set_style_pad_all(ui.card_obj, 0, LV_PART_MAIN);
    lv_obj_clear_flag(ui.card_obj, LV_OBJ_FLAG_SCROLLABLE);

    // 2. Render Converted PNG Icon Asset (28 x 28 px) directly on card (transparent background)
    const lv_img_dsc_t * icon_dsc = NULL;
    if (icon_type == ICON_ROVER) {
        icon_dsc = &rover_icon;
    } else if (icon_type == ICON_CONTROL_GLOVE) {
        icon_dsc = &control_glove_icon;
    } else if (icon_type == ICON_STATUS_GLOVE) {
        icon_dsc = &status_glove_icon;
    }

    if (icon_dsc && icon_dsc->data) {
        lv_obj_t * icon_img = lv_img_create(ui.card_obj);
        lv_img_set_src(icon_img, icon_dsc);
        lv_obj_set_pos(icon_img, 5, 9);
    }

    // 3. Title Label (Font 10px - Dark Navy)
    ui.lbl_title = lv_label_create(ui.card_obj);
    lv_label_set_text(ui.lbl_title, data.title);
    lv_obj_set_style_text_font(ui.lbl_title, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(ui.lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_pos(ui.lbl_title, 35, 3);

    // 4. Dynamic Status Dot & Text
    ui.status_dot = lv_obj_create(ui.card_obj);
    lv_obj_set_size(ui.status_dot, 4, 4);
    lv_obj_set_pos(ui.status_dot, 35, 17);
    lv_obj_set_style_radius(ui.status_dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_border_width(ui.status_dot, 0, LV_PART_MAIN);

    ui.lbl_status = lv_label_create(ui.card_obj);
    lv_obj_set_style_text_font(ui.lbl_status, &lv_font_montserrat_8, LV_PART_MAIN);
    lv_obj_set_style_text_color(ui.lbl_status, lv_color_hex(0x475569), LV_PART_MAIN);
    lv_obj_set_pos(ui.lbl_status, 42, 14);

    // 5. Battery Info Text (Font 8px)
    ui.lbl_battery = lv_label_create(ui.card_obj);
    lv_obj_set_style_text_font(ui.lbl_battery, &lv_font_montserrat_8, LV_PART_MAIN);
    lv_obj_set_style_text_color(ui.lbl_battery, lv_color_hex(0x475569), LV_PART_MAIN);
    lv_obj_set_pos(ui.lbl_battery, 35, 25);

    // 6. Mini Horizontal Battery Bar (3px height, pill-rounded ends)
    ui.bar_battery = lv_bar_create(ui.card_obj);
    lv_obj_set_size(ui.bar_battery, w - 41, 3);
    lv_obj_set_pos(ui.bar_battery, 35, 37);
    lv_obj_set_style_bg_color(ui.bar_battery, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_radius(ui.bar_battery, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_radius(ui.bar_battery, LV_RADIUS_CIRCLE, LV_PART_INDICATOR);

    // Initial update of dynamic states
    ui_update_status_card(ui, data);

    return ui;
}

// Helper to check title
static bool icon_type_is_rover(const char * title) {
    return title && (title[0] == 'R' || title[0] == 'r');
}

void ui_update_status_card(StatusCardUI &ui, const DeviceStatus &data) {
    if (!ui.card_obj) return;

    // Title
    if (ui.lbl_title && data.title) {
        lv_label_set_text(ui.lbl_title, data.title);
    }

    // Status Dot Color & Text
    lv_color_t dot_color = data.connected ? lv_color_hex(0x10B981) : lv_color_hex(0xEF4444);
    lv_obj_set_style_bg_color(ui.status_dot, dot_color, LV_PART_MAIN);

    const char * status_txt = data.connected ?
                              (icon_type_is_rover(data.title) ? "Online" : "Connected") :
                              "Offline";
    lv_label_set_text(ui.lbl_status, status_txt);

    // Compact Battery Text (e.g. "85% | Ready")
    char buf[32];
    snprintf(buf, sizeof(buf), "%d%% | %s", data.battery, data.state ? data.state : "");
    lv_label_set_text(ui.lbl_battery, buf);

    // Battery Bar Value & Color
    lv_bar_set_value(ui.bar_battery, data.battery, LV_ANIM_OFF);

    lv_color_t bar_color;
    if (data.battery > 40) {
        bar_color = lv_color_hex(0x10B981); // High Battery: Green
    } else if (data.battery > 20) {
        bar_color = lv_color_hex(0xF59E0B); // Medium Battery: Amber
    } else {
        bar_color = lv_color_hex(0xEF4444); // Low Battery: Red
    }
    lv_obj_set_style_bg_color(ui.bar_battery, bar_color, LV_PART_INDICATOR);
}
