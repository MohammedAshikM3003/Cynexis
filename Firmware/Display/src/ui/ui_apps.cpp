#include <Arduino.h>
#include "ui_apps.h"
#include "ui.h"
#include "cynexis_wallpaper.h"

// LVGL Icon Asset Headers
#include "assets/rover_icon.h"
#include "assets/arm_icon.h"
#include "assets/assistant_icon.h"
#include "assets/camera_icon.h"
#include "assets/demo_icon.h"
#include "assets/gallery_icon.h"
#include "assets/control_glove_icon.h"
#include "assets/status_glove_icon.h"
#include "assets/alerts_icon.h"
#include "assets/emergency_icon.h"
#include "assets/settings_icon.h"
#include "assets/logs_icon.h"
#include "assets/calibration_icon.h"

// App Item Definition
struct AppItem {
    const char * name;
    const lv_img_dsc_t * icon;
    ScreenId target;
};

// App Drawer Page 1 — Exact 3x3 App Order (9 Apps)
static const AppItem page1_apps[9] = {
    // Row 1
    {"Rover",     &rover_icon,         SCREEN_ROVER},
    {"Arm",       &arm_icon,           SCREEN_ARM},
    {"Assistant", &assistant_icon,     SCREEN_ASSISTANT},
    // Row 2
    {"Camera",    &camera_icon,        SCREEN_CAMERA},
    {"Demo",      &demo_icon,          SCREEN_DEMO},
    {"Gallery",   &gallery_icon,       SCREEN_GALLERY},
    // Row 3
    {"Control",   &control_glove_icon, SCREEN_CONTROL},
    {"Status",    &status_glove_icon,  SCREEN_STATUS},
    {"Alerts",    &alerts_icon,        SCREEN_ALERTS}
};

// App Drawer Page 2 — 4 Apps
static const AppItem page2_apps[4] = {
    // Row 1
    {"Emergency",   &emergency_icon,   SCREEN_EMERGENCY},
    {"Settings",    &settings_icon,    SCREEN_SETTINGS},
    {"Logs",        &logs_icon,        SCREEN_LOGS},
    // Row 2
    {"Calibration", &calibration_icon, SCREEN_CALIBRATION}
};

static lv_obj_t * page1_container = NULL;
static lv_obj_t * page2_container = NULL;
static lv_obj_t * btn_page_nav = NULL;
static lv_obj_t * lbl_page_nav = NULL;
static int current_page = 1;

static void update_page_view(int page) {
    current_page = page;
    if (page == 1) {
        if (page1_container) lv_obj_clear_flag(page1_container, LV_OBJ_FLAG_HIDDEN);
        if (page2_container) lv_obj_add_flag(page2_container, LV_OBJ_FLAG_HIDDEN);
        if (lbl_page_nav) lv_label_set_text(lbl_page_nav, "PAGE 2 >");
        Serial.println("[APP DRAWER] Page 1");
    } else {
        if (page1_container) lv_obj_add_flag(page1_container, LV_OBJ_FLAG_HIDDEN);
        if (page2_container) lv_obj_clear_flag(page2_container, LV_OBJ_FLAG_HIDDEN);
        if (lbl_page_nav) lv_label_set_text(lbl_page_nav, "PAGE 1 <");
        Serial.println("[APP DRAWER] Page 2");
    }
}

static void nav_home_cb(lv_event_t * e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        Serial.println("[UI NAV] Returning to HOME screen...");
        ui_switch_to(SCREEN_HOME);
    }
}

static void app_card_cb(lv_event_t * e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        ScreenId target = (ScreenId)(uintptr_t)lv_event_get_user_data(e);
        Serial.printf("[UI NAV] App Card Clicked! Target ScreenId: %d\n", (int)target);
        ui_switch_to(target);
    }
}

static bool page_nav_touched_down = false;

static void btn_page_nav_cb(lv_event_t * e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_PRESSED) {
        Serial.println("[APP DRAWER DEBUG] NAV BUTTON PRESSED");
    } else if (code == LV_EVENT_RELEASED) {
        Serial.println("[APP DRAWER] PAGE NAV RELEASED");
        page_nav_touched_down = false;
    } else if (code == LV_EVENT_CLICKED) {
        if (page_nav_touched_down) {
            page_nav_touched_down = false;
            return;
        }
        lv_obj_t * obj = lv_event_get_target(e);
        Serial.printf("[APP DRAWER DEBUG] NAV BUTTON CLICKED (obj x:%d, y:%d, w:%d, h:%d)\n",
                      lv_obj_get_x(obj), lv_obj_get_y(obj), lv_obj_get_width(obj), lv_obj_get_height(obj));
        if (current_page == 1) {
            Serial.println("[APP DRAWER] Next page");
            update_page_view(2);
        } else {
            Serial.println("[APP DRAWER] Previous page");
            update_page_view(1);
        }
    }
}

static void page_nav_screen_touch_cb(lv_event_t * e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_PRESSED) {
        lv_indev_t * indev = lv_indev_get_act();
        if (indev) {
            lv_point_t point;
            lv_indev_get_point(indev, &point);
            // Verified physical PAGE navigation touch coordinate region
            if (point.x >= 310 && point.x <= 319 && point.y >= 8 && point.y <= 24) {
                if (!page_nav_touched_down) {
                    page_nav_touched_down = true;
                    Serial.printf("[APP DRAWER] Direct touch in PAGE NAV region (x:%d, y:%d)\n", point.x, point.y);
                    if (current_page == 1) {
                        update_page_view(2);
                    } else {
                        update_page_view(1);
                    }
                }
            }
        }
    } else if (code == LV_EVENT_RELEASED) {
        page_nav_touched_down = false;
    }
}

static void drawer_gesture_cb(lv_event_t * e) {
    lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
    if (dir == LV_DIR_LEFT) {
        Serial.println("[APP DRAWER] Next page");
        update_page_view(2);
    } else if (dir == LV_DIR_RIGHT) {
        Serial.println("[APP DRAWER] Previous page");
        update_page_view(1);
    }
}

static lv_obj_t* create_header_button(lv_obj_t * parent, int x, int y, int w, int h, const char * text, lv_event_cb_t cb, lv_obj_t ** out_label) {
    lv_obj_t * btn = lv_btn_create(parent);
    lv_obj_set_size(btn, w, h);
    lv_obj_set_pos(btn, x, y);

    lv_obj_set_style_bg_color(btn, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn, LV_OPA_90, LV_PART_MAIN);
    lv_obj_set_style_radius(btn, 6, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn, 4, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(btn, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(btn, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_add_event_cb(btn, cb, LV_EVENT_ALL, NULL);

    lv_obj_t * lbl = lv_label_create(btn);
    lv_label_set_text(lbl, text);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_clear_flag(lbl, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_center(lbl);

    if (out_label) {
        *out_label = lbl;
    }

    return btn;
}

static void create_app_grid(lv_obj_t * parent_container, const AppItem * apps, int count) {
    Serial.printf("[APP DEBUG] create_app_grid BEGIN parent=%p, count=%d\n", parent_container, count);
    for (int i = 0; i < count; i++) {
        Serial.printf("[APP DEBUG] item %d BEGIN\n", i);
        Serial.printf("[APP DEBUG] name pointer = %p (%s)\n", apps[i].name, apps[i].name ? apps[i].name : "NULL");
        Serial.printf("[APP DEBUG] icon pointer = %p\n", apps[i].icon);
        if (apps[i].icon) {
            Serial.printf("[APP DEBUG] icon data = %p\n", apps[i].icon->data);
        }

        int col = i % 3;
        int row = i / 3;

        int x = 9 + col * 101; // Col 0: 9, Col 1: 110, Col 2: 211
        int y = 4 + row * 62;  // Row 0: 4 (abs Y=42), Row 1: 66 (abs Y=104), Row 2: 128 (abs Y=166)

        Serial.printf("[APP DEBUG] before card create i=%d parent=%p\n", i, parent_container);
        lv_obj_t * card = lv_btn_create(parent_container);
        Serial.printf("[APP DEBUG] card = %p\n", card);
        Serial.printf("[APP DEBUG] card parent = %p\n", card ? lv_obj_get_parent(card) : NULL);

        Serial.printf("[APP DEBUG] before card style setup i=%d\n", i);
        lv_obj_set_size(card, 92, 54);
        lv_obj_set_pos(card, x, y);

        // App Card Modern Rounded White Translucent Styling
        lv_obj_set_style_bg_color(card, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
        lv_obj_set_style_bg_opa(card, (lv_opa_t)217, LV_PART_MAIN); // ~85% opacity
        lv_obj_set_style_radius(card, 10, LV_PART_MAIN);
        lv_obj_set_style_border_width(card, 0, LV_PART_MAIN);
        lv_obj_set_style_outline_width(card, 0, LV_PART_MAIN);

        // Soft Drop Shadow
        lv_obj_set_style_shadow_width(card, 5, LV_PART_MAIN);
        lv_obj_set_style_shadow_spread(card, 0, LV_PART_MAIN);
        lv_obj_set_style_shadow_ofs_x(card, 0, LV_PART_MAIN);
        lv_obj_set_style_shadow_ofs_y(card, 2, LV_PART_MAIN);
        lv_obj_set_style_shadow_color(card, lv_color_hex(0x0F172A), LV_PART_MAIN);
        lv_obj_set_style_shadow_opa(card, (lv_opa_t)64, LV_PART_MAIN); // ~25% opacity

        lv_obj_set_style_pad_all(card, 0, LV_PART_MAIN);
        lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);

        // Event Callback for Touch Navigation
        lv_obj_add_event_cb(card, app_card_cb, LV_EVENT_CLICKED, (void*)(uintptr_t)apps[i].target);
        Serial.printf("[APP DEBUG] after card setup i=%d\n", i);

        // Render PNG Icon directly on Card (no icon background tile)
        if (apps[i].icon && apps[i].icon->data) {
            Serial.printf("[APP DEBUG] before icon create i=%d\n", i);
            lv_obj_t * icon_img = lv_img_create(card);
            Serial.printf("[APP DEBUG] icon_img = %p\n", icon_img);
            Serial.printf("[APP DEBUG] before icon source/align i=%d\n", i);
            lv_img_set_src(icon_img, apps[i].icon);
            lv_obj_align(icon_img, LV_ALIGN_TOP_MID, 0, 4);
            lv_obj_clear_flag(icon_img, LV_OBJ_FLAG_CLICKABLE);
            Serial.printf("[APP DEBUG] after icon source/align i=%d\n", i);
        }

        // App Name Label (Dark Navy #0F172A, Montserrat 10)
        Serial.printf("[APP DEBUG] before label create i=%d\n", i);
        lv_obj_t * lbl_title = lv_label_create(card);
        Serial.printf("[APP DEBUG] lbl_title = %p\n", lbl_title);
        Serial.printf("[APP DEBUG] before label align i=%d lbl_title=%p parent=%p\n",
                      i, lbl_title, lbl_title ? lv_obj_get_parent(lbl_title) : NULL);
        lv_label_set_text(lbl_title, apps[i].name);
        lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_10, LV_PART_MAIN);
        lv_obj_set_style_text_color(lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
        lv_obj_align(lbl_title, LV_ALIGN_TOP_MID, 0, 34);
        lv_obj_clear_flag(lbl_title, LV_OBJ_FLAG_CLICKABLE);
        Serial.printf("[APP DEBUG] after label align i=%d\n", i);

        Serial.printf("[APP DEBUG] item %d END\n", i);
    }
    Serial.printf("[APP DEBUG] create_app_grid END parent=%p\n", parent_container);
}

lv_obj_t* ui_apps_create() {
    Serial.println("[APP DEBUG] ui_apps_create BEGIN");
    // 1. Base Screen Container (320x240)
    lv_obj_t * scr = lv_obj_create(NULL);
    Serial.printf("[APP DEBUG] scr = %p\n", scr);
    lv_obj_set_style_pad_all(scr, 0, LV_PART_MAIN);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    // 2. Full-Screen CYNEXIS Wallpaper Base Layer (Child of scr)
    lv_obj_t * bg_img = lv_img_create(scr);
    lv_img_set_src(bg_img, &cynexis_wallpaper);
    lv_obj_set_pos(bg_img, 0, 0);
    lv_obj_set_size(bg_img, 320, 240);
    lv_obj_set_style_pad_all(bg_img, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(bg_img, 0, LV_PART_MAIN);
    lv_obj_clear_flag(bg_img, LV_OBJ_FLAG_CLICKABLE);

    // 3. Translucent Glass-morphism Drawer Background Panel (Child of scr, sitting on top of bg_img)
    lv_obj_t * glass_panel = lv_obj_create(scr);
    lv_obj_set_size(glass_panel, 312, 232);
    lv_obj_set_pos(glass_panel, 4, 4);
    lv_obj_set_style_bg_color(glass_panel, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(glass_panel, (lv_opa_t)140, LV_PART_MAIN); // 55% opacity white glass overlay
    lv_obj_set_style_radius(glass_panel, 12, LV_PART_MAIN);
    lv_obj_set_style_border_width(glass_panel, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(glass_panel, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_border_opa(glass_panel, LV_OPA_30, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(glass_panel, 8, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(glass_panel, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(glass_panel, (lv_opa_t)38, LV_PART_MAIN); // ~15% opacity shadow
    lv_obj_set_style_pad_all(glass_panel, 0, LV_PART_MAIN);
    lv_obj_clear_flag(glass_panel, LV_OBJ_FLAG_SCROLLABLE);

    // Enable gesture navigation & direct touch handling on glass panel & screen
    lv_obj_add_event_cb(glass_panel, drawer_gesture_cb, LV_EVENT_GESTURE, NULL);
    lv_obj_add_event_cb(scr, drawer_gesture_cb, LV_EVENT_GESTURE, NULL);
    lv_obj_add_event_cb(glass_panel, page_nav_screen_touch_cb, LV_EVENT_ALL, NULL);
    lv_obj_add_event_cb(scr, page_nav_screen_touch_cb, LV_EVENT_ALL, NULL);

    // 4. Page Content Containers (Positioned from Y=38 to Y=232 so they NEVER obscure header controls)
    page1_container = lv_obj_create(glass_panel);
    lv_obj_set_size(page1_container, 312, 194);
    lv_obj_set_pos(page1_container, 0, 38);
    lv_obj_set_style_bg_opa(page1_container, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(page1_container, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(page1_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(page1_container, LV_OBJ_FLAG_SCROLLABLE);

    page2_container = lv_obj_create(glass_panel);
    lv_obj_set_size(page2_container, 312, 194);
    lv_obj_set_pos(page2_container, 0, 38);
    lv_obj_set_style_bg_opa(page2_container, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(page2_container, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(page2_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(page2_container, LV_OBJ_FLAG_SCROLLABLE);

    // Populate Page 1 (9 Apps) & Page 2 (4 Apps)
    create_app_grid(page1_container, page1_apps, 9);
    create_app_grid(page2_container, page2_apps, 4);

    // 5. Header Navigation Bar (Rendered at top Y=0..37, fully touchable and unobstructed)
    // 5a. Back to Home Control Button (Left Header: local X=8, Y=6, W=66, H=26)
    lv_obj_t * btn_back = create_header_button(glass_panel, 8, 6, 66, 26, "< HOME", nav_home_cb, NULL);

    // 5b. Header Title Label (Centered between < HOME and PAGE NAV)
    lv_obj_t * title = lv_label_create(glass_panel);
    lv_label_set_text(title, "APPLICATIONS");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_style_text_color(title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_clear_flag(title, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 12);

    // 5c. Header Page Navigation Button (Right Header: PAGE 2 > / PAGE 1 <)
    // Matches < HOME exactly in visible size (W=66, H=26, Y=6, local X=238).
    // Extended click area (+25px) ensures physical touches up to X=319 / Y=22 are captured seamlessly.
    btn_page_nav = create_header_button(glass_panel, 238, 6, 66, 26, "PAGE 2 >", btn_page_nav_cb, &lbl_page_nav);
    lv_obj_set_ext_click_area(btn_page_nav, 25);

    // Move header buttons to top of z-index
    lv_obj_move_foreground(btn_back);
    lv_obj_move_foreground(btn_page_nav);

    // Log geometry diagnostics
    Serial.printf("[APP DRAWER GEOMETRY] glass_panel: x=%d, y=%d, w=%d, h=%d\n",
                  lv_obj_get_x(glass_panel), lv_obj_get_y(glass_panel),
                  lv_obj_get_width(glass_panel), lv_obj_get_height(glass_panel));
    Serial.printf("[APP DRAWER GEOMETRY] btn_back: parent=%p, x=%d, y=%d, w=%d, h=%d\n",
                  lv_obj_get_parent(btn_back), lv_obj_get_x(btn_back), lv_obj_get_y(btn_back),
                  lv_obj_get_width(btn_back), lv_obj_get_height(btn_back));
    Serial.printf("[APP DRAWER GEOMETRY] btn_page_nav: parent=%p, x=%d, y=%d, w=%d, h=%d\n",
                  lv_obj_get_parent(btn_page_nav), lv_obj_get_x(btn_page_nav), lv_obj_get_y(btn_page_nav),
                  lv_obj_get_width(btn_page_nav), lv_obj_get_height(btn_page_nav));

    // Initialize Page View to Page 1
    update_page_view(1);

    return scr;
}




