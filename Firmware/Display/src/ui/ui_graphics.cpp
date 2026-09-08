#include "ui_graphics.h"

void ui_draw_robotic_arm(lv_obj_t * parent) {
    // Canvas Container Box
    lv_obj_t * box = lv_obj_create(parent);
    lv_obj_set_size(box, 126, 76);
    lv_obj_align(box, LV_ALIGN_CENTER, 0, -4);
    lv_obj_set_style_bg_color(box, lv_color_hex(0xF8FAFC), LV_PART_MAIN); // Off-white / light slate
    lv_obj_set_style_border_color(box, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_border_width(box, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(box, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(box, 0, LV_PART_MAIN);
    lv_obj_clear_flag(box, LV_OBJ_FLAG_SCROLLABLE);

    // 1. Base Plate
    lv_obj_t * base = lv_obj_create(box);
    lv_obj_set_size(base, 50, 8);
    lv_obj_set_pos(base, 38, 60);
    lv_obj_set_style_bg_color(base, lv_color_hex(0x334155), LV_PART_MAIN); // Dark slate
    lv_obj_set_style_border_width(base, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(base, 2, LV_PART_MAIN);

    // 2. Shoulder Turret
    lv_obj_t * turret = lv_obj_create(box);
    lv_obj_set_size(turret, 26, 16);
    lv_obj_set_pos(turret, 50, 46);
    lv_obj_set_style_bg_color(turret, lv_color_hex(0x2563EB), LV_PART_MAIN); // Primary Blue
    lv_obj_set_style_border_width(turret, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(turret, 4, LV_PART_MAIN);

    // 3. Shoulder Joint Pivot (Circle)
    lv_obj_t * s_joint = lv_obj_create(box);
    lv_obj_set_size(s_joint, 10, 10);
    lv_obj_set_pos(s_joint, 58, 41);
    lv_obj_set_style_bg_color(s_joint, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_border_width(s_joint, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(s_joint, LV_RADIUS_CIRCLE, LV_PART_MAIN);

    // 4. Primary Arm Link (Angled up-right)
    lv_obj_t * arm_link = lv_obj_create(box);
    lv_obj_set_size(arm_link, 8, 34);
    lv_obj_set_pos(arm_link, 68, 14);
    lv_obj_set_style_bg_color(arm_link, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_border_width(arm_link, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(arm_link, 4, LV_PART_MAIN);

    // 5. Elbow Joint Pivot (Circle)
    lv_obj_t * e_joint = lv_obj_create(box);
    lv_obj_set_size(e_joint, 10, 10);
    lv_obj_set_pos(e_joint, 67, 10);
    lv_obj_set_style_bg_color(e_joint, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_border_width(e_joint, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(e_joint, LV_RADIUS_CIRCLE, LV_PART_MAIN);

    // 6. Forearm Link (Extending right)
    lv_obj_t * forearm = lv_obj_create(box);
    lv_obj_set_size(forearm, 30, 8);
    lv_obj_set_pos(forearm, 74, 11);
    lv_obj_set_style_bg_color(forearm, lv_color_hex(0x0D9488), LV_PART_MAIN); // Teal
    lv_obj_set_style_border_width(forearm, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(forearm, 3, LV_PART_MAIN);

    // 7. Wrist
    lv_obj_t * wrist = lv_obj_create(box);
    lv_obj_set_size(wrist, 6, 14);
    lv_obj_set_pos(wrist, 102, 8);
    lv_obj_set_style_bg_color(wrist, lv_color_hex(0x334155), LV_PART_MAIN);
    lv_obj_set_style_border_width(wrist, 0, LV_PART_MAIN);

    // 8. Gripper Claws (Red)
    lv_obj_t * claw_top = lv_obj_create(box);
    lv_obj_set_size(claw_top, 10, 3);
    lv_obj_set_pos(claw_top, 107, 6);
    lv_obj_set_style_bg_color(claw_top, lv_color_hex(0xDC2626), LV_PART_MAIN);

    lv_obj_t * claw_bot = lv_obj_create(box);
    lv_obj_set_size(claw_bot, 10, 3);
    lv_obj_set_pos(claw_bot, 107, 21);
    lv_obj_set_style_bg_color(claw_bot, lv_color_hex(0xDC2626), LV_PART_MAIN);
}

void ui_draw_rover_icon(lv_obj_t * parent, int x, int y) {
    lv_obj_t * chassis = lv_obj_create(parent);
    lv_obj_set_size(chassis, 14, 10);
    lv_obj_set_pos(chassis, x + 2, y + 2);
    lv_obj_set_style_bg_color(chassis, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_border_width(chassis, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(chassis, 2, LV_PART_MAIN);

    // Wheels
    int w_coords[4][2] = {{x, y}, {x + 14, y}, {x, y + 9}, {x + 14, y + 9}};
    for (int i = 0; i < 4; i++) {
        lv_obj_t * w = lv_obj_create(parent);
        lv_obj_set_size(w, 4, 5);
        lv_obj_set_pos(w, w_coords[i][0], w_coords[i][1]);
        lv_obj_set_style_bg_color(w, lv_color_hex(0x0F172A), LV_PART_MAIN);
        lv_obj_set_style_border_width(w, 0, LV_PART_MAIN);
        lv_obj_set_style_radius(w, 1, LV_PART_MAIN);
    }
}

void ui_draw_glove_icon(lv_obj_t * parent, int x, int y, lv_color_t color) {
    // Palm
    lv_obj_t * palm = lv_obj_create(parent);
    lv_obj_set_size(palm, 12, 9);
    lv_obj_set_pos(palm, x + 2, y + 5);
    lv_obj_set_style_bg_color(palm, color, LV_PART_MAIN);
    lv_obj_set_style_border_width(palm, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(palm, 2, LV_PART_MAIN);

    // Fingers
    for (int i = 0; i < 4; i++) {
        lv_obj_t * f = lv_obj_create(parent);
        lv_obj_set_size(f, 2, 5);
        lv_obj_set_pos(f, x + 2 + (i * 3), y);
        lv_obj_set_style_bg_color(f, color, LV_PART_MAIN);
        lv_obj_set_style_border_width(f, 0, LV_PART_MAIN);
        lv_obj_set_style_radius(f, 1, LV_PART_MAIN);
    }
}

void ui_draw_apps_icon(lv_obj_t * parent, int x, int y) {
    int grid_pos[4][2] = {{x, y}, {x + 7, y}, {x, y + 7}, {x + 7, y + 7}};
    for (int i = 0; i < 4; i++) {
        lv_obj_t * sq = lv_obj_create(parent);
        lv_obj_set_size(sq, 5, 5);
        lv_obj_set_pos(sq, grid_pos[i][0], grid_pos[i][1]);
        lv_obj_set_style_bg_color(sq, lv_color_hex(0x4F46E5), LV_PART_MAIN);
        lv_obj_set_style_border_width(sq, 0, LV_PART_MAIN);
        lv_obj_set_style_radius(sq, 1, LV_PART_MAIN);
    }
}
