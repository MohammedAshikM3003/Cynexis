#include "ui_arm.h"
#include "ui.h"

static void nav_home_cb(lv_event_t * e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        ui_switch_to(SCREEN_HOME);
    }
}

lv_obj_t* ui_arm_create() {
    lv_obj_t * scr = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr, lv_color_hex(0xE2E8F0), LV_PART_MAIN);

    // Top Header Bar
    lv_obj_t * header = lv_obj_create(scr);
    lv_obj_set_size(header, 312, 32);
    lv_obj_set_pos(header, 4, 4);
    lv_obj_set_style_bg_color(header, lv_color_hex(0x0D9488), LV_PART_MAIN); // Teal Accent
    lv_obj_set_style_border_width(header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(header, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(header, 4, LV_PART_MAIN);

    // Back Button
    lv_obj_t * btn_back = lv_btn_create(header);
    lv_obj_set_size(btn_back, 60, 24);
    lv_obj_align(btn_back, LV_ALIGN_LEFT_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_back, lv_color_hex(0x0F766E), LV_PART_MAIN);
    lv_obj_add_event_cb(btn_back, nav_home_cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t * lbl_back = lv_label_create(btn_back);
    lv_label_set_text(lbl_back, "< HOME");
    lv_obj_set_style_text_color(lbl_back, lv_color_white(), LV_PART_MAIN);
    lv_obj_center(lbl_back);

    // Header Title
    lv_obj_t * title = lv_label_create(header);
    lv_label_set_text(title, "ROBOTIC ARM CONTROL");
    lv_obj_set_style_text_color(title, lv_color_white(), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_CENTER, 0, 0);

    // E-STOP Button
    lv_obj_t * btn_estop = lv_btn_create(header);
    lv_obj_set_size(btn_estop, 65, 24);
    lv_obj_align(btn_estop, LV_ALIGN_RIGHT_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_estop, lv_color_hex(0xDC2626), LV_PART_MAIN);

    lv_obj_t * lbl_estop = lv_label_create(btn_estop);
    lv_label_set_text(lbl_estop, "E-STOP");
    lv_obj_set_style_text_color(lbl_estop, lv_color_white(), LV_PART_MAIN);
    lv_obj_center(lbl_estop);

    // Arm Telemetry Card
    lv_obj_t * card = lv_obj_create(scr);
    lv_obj_set_size(card, 312, 190);
    lv_obj_set_pos(card, 4, 42);
    lv_obj_set_style_bg_color(card, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_border_color(card, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card, 8, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card, 8, LV_PART_MAIN);

    lv_obj_t * info1 = lv_label_create(card);
    lv_label_set_text(info1, "Arm Mode: GESTURE CONTROL ACTIVE");
    lv_obj_set_style_text_color(info1, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_align(info1, LV_ALIGN_TOP_LEFT, 4, 4);

    lv_obj_t * info2 = lv_label_create(card);
    lv_label_set_text(info2, "Arm Status: READY | Gripper: OPEN (45%)");
    lv_obj_set_style_text_color(info2, lv_color_hex(0x16A34A), LV_PART_MAIN);
    lv_obj_align(info2, LV_ALIGN_TOP_LEFT, 4, 30);

    lv_obj_t * info3 = lv_label_create(card);
    lv_label_set_text(info3, "Joint 1: 90 deg  |  Joint 2: 45 deg");
    lv_obj_set_style_text_color(info3, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_align(info3, LV_ALIGN_TOP_LEFT, 4, 56);

    lv_obj_t * info4 = lv_label_create(card);
    lv_label_set_text(info4, "Joint 3: 120 deg |  Gripper Pressure: Normal");
    lv_obj_set_style_text_color(info4, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_align(info4, LV_ALIGN_TOP_LEFT, 4, 82);

    // Quick Manual Gripper Action Buttons
    lv_obj_t * btn_open = lv_btn_create(card);
    lv_obj_set_size(btn_open, 130, 40);
    lv_obj_align(btn_open, LV_ALIGN_BOTTOM_LEFT, 8, -8);
    lv_obj_set_style_bg_color(btn_open, lv_color_hex(0x0D9488), LV_PART_MAIN);
    lv_obj_t * l_open = lv_label_create(btn_open);
    lv_label_set_text(l_open, "OPEN GRIPPER");
    lv_obj_center(l_open);

    lv_obj_t * btn_close = lv_btn_create(card);
    lv_obj_set_size(btn_close, 130, 40);
    lv_obj_align(btn_close, LV_ALIGN_BOTTOM_RIGHT, -8, -8);
    lv_obj_set_style_bg_color(btn_close, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_t * l_close = lv_label_create(btn_close);
    lv_label_set_text(l_close, "CLOSE GRIPPER");
    lv_obj_center(l_close);

    return scr;
}
