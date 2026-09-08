#include "ui_rover.h"
#include "ui.h"

static lv_obj_t * joystick_container;
static lv_obj_t * mode_label;

static void nav_home_cb(lv_event_t * e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        ui_switch_to(SCREEN_HOME);
    }
}

static void method_select_cb(lv_event_t * e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_VALUE_CHANGED) {
        lv_obj_t * dropdown = lv_event_get_target(e);
        char buf[32];
        lv_dropdown_get_selected_str(dropdown, buf, sizeof(buf));
        
        if (strcmp(buf, "Joystick") == 0) {
            lv_obj_clear_state(joystick_container, LV_STATE_DISABLED);
            lv_label_set_text(mode_label, "Control: JOYSTICK ACTIVE");
        } else {
            lv_obj_add_state(joystick_container, LV_STATE_DISABLED);
            if (strcmp(buf, "Gesture") == 0) {
                lv_label_set_text(mode_label, "Control: GESTURE MODE");
            } else {
                lv_label_set_text(mode_label, "Control: VOICE MODE");
            }
        }
    }
}

lv_obj_t* ui_rover_create() {
    lv_obj_t * scr = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr, lv_color_hex(0xE2E8F0), LV_PART_MAIN);

    // Top Header Bar
    lv_obj_t * header = lv_obj_create(scr);
    lv_obj_set_size(header, 312, 32);
    lv_obj_set_pos(header, 4, 4);
    lv_obj_set_style_bg_color(header, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_border_width(header, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(header, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(header, 4, LV_PART_MAIN);

    // Back Button
    lv_obj_t * btn_back = lv_btn_create(header);
    lv_obj_set_size(btn_back, 60, 24);
    lv_obj_align(btn_back, LV_ALIGN_LEFT_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_back, lv_color_hex(0x1D4ED8), LV_PART_MAIN);
    lv_obj_add_event_cb(btn_back, nav_home_cb, LV_EVENT_CLICKED, NULL);

    lv_obj_t * lbl_back = lv_label_create(btn_back);
    lv_label_set_text(lbl_back, "< HOME");
    lv_obj_set_style_text_color(lbl_back, lv_color_white(), LV_PART_MAIN);
    lv_obj_center(lbl_back);

    // Header Title
    lv_obj_t * title = lv_label_create(header);
    lv_label_set_text(title, "ROVER CONTROLLER");
    lv_obj_set_style_text_color(title, lv_color_white(), LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_CENTER, 0, 0);

    // E-STOP Button
    lv_obj_t * btn_estop = lv_btn_create(header);
    lv_obj_set_size(btn_estop, 65, 24);
    lv_obj_align(btn_estop, LV_ALIGN_RIGHT_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_estop, lv_color_hex(0xDC2626), LV_PART_MAIN); // Red

    lv_obj_t * lbl_estop = lv_label_create(btn_estop);
    lv_label_set_text(lbl_estop, "E-STOP");
    lv_obj_set_style_text_color(lbl_estop, lv_color_white(), LV_PART_MAIN);
    lv_obj_center(lbl_estop);

    // Telemetry Card
    lv_obj_t * telemetry = lv_obj_create(scr);
    lv_obj_set_size(telemetry, 312, 45);
    lv_obj_set_pos(telemetry, 4, 40);
    lv_obj_set_style_bg_color(telemetry, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_border_color(telemetry, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_border_width(telemetry, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(telemetry, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(telemetry, 4, LV_PART_MAIN);

    mode_label = lv_label_create(telemetry);
    lv_label_set_text(mode_label, "Control: JOYSTICK ACTIVE");
    lv_obj_set_style_text_color(mode_label, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_align(mode_label, LV_ALIGN_TOP_LEFT, 4, 0);

    lv_obj_t * status_txt = lv_label_create(telemetry);
    lv_label_set_text(status_txt, "Speed: 65% | Dist: 42cm | Bat: 85%");
    lv_obj_set_style_text_color(status_txt, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_align(status_txt, LV_ALIGN_BOTTOM_LEFT, 4, 0);

    // Control Method Selection Dropdown
    lv_obj_t * dropdown = lv_dropdown_create(scr);
    lv_dropdown_set_options(dropdown, "Joystick\nGesture\nVoice");
    lv_obj_set_size(dropdown, 110, 36);
    lv_obj_set_pos(dropdown, 4, 90);
    lv_obj_add_event_cb(dropdown, method_select_cb, LV_EVENT_VALUE_CHANGED, NULL);

    // Directional Joystick Container
    joystick_container = lv_obj_create(scr);
    lv_obj_set_size(joystick_container, 198, 140);
    lv_obj_set_pos(joystick_container, 118, 90);
    lv_obj_set_style_bg_color(joystick_container, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_border_color(joystick_container, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_border_width(joystick_container, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(joystick_container, 8, LV_PART_MAIN);

    // Joystick Direction Buttons
    lv_obj_t * btn_fwd = lv_btn_create(joystick_container);
    lv_obj_set_size(btn_fwd, 54, 38);
    lv_obj_align(btn_fwd, LV_ALIGN_TOP_MID, 0, 4);
    lv_obj_t * l_fwd = lv_label_create(btn_fwd);
    lv_label_set_text(l_fwd, "FWD");
    lv_obj_center(l_fwd);

    lv_obj_t * btn_rev = lv_btn_create(joystick_container);
    lv_obj_set_size(btn_rev, 54, 38);
    lv_obj_align(btn_rev, LV_ALIGN_BOTTOM_MID, 0, -4);
    lv_obj_t * l_rev = lv_label_create(btn_rev);
    lv_label_set_text(l_rev, "REV");
    lv_obj_center(l_rev);

    lv_obj_t * btn_left = lv_btn_create(joystick_container);
    lv_obj_set_size(btn_left, 54, 38);
    lv_obj_align(btn_left, LV_ALIGN_LEFT_MID, 4, 0);
    lv_obj_t * l_left = lv_label_create(btn_left);
    lv_label_set_text(l_left, "LEFT");
    lv_obj_center(l_left);

    lv_obj_t * btn_right = lv_btn_create(joystick_container);
    lv_obj_set_size(btn_right, 54, 38);
    lv_obj_align(btn_right, LV_ALIGN_RIGHT_MID, -4, 0);
    lv_obj_t * l_right = lv_label_create(btn_right);
    lv_label_set_text(l_right, "RIGHT");
    lv_obj_center(l_right);

    lv_obj_t * btn_stop = lv_btn_create(joystick_container);
    lv_obj_set_size(btn_stop, 54, 38);
    lv_obj_center(btn_stop);
    lv_obj_set_style_bg_color(btn_stop, lv_color_hex(0xDC2626), LV_PART_MAIN);
    lv_obj_t * l_stop = lv_label_create(btn_stop);
    lv_label_set_text(l_stop, "STOP");
    lv_obj_center(l_stop);

    return scr;
}
