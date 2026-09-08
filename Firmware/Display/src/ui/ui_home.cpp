#include "ui_home.h"
#include "ui.h"
#include "cynexis_wallpaper.h"
#include "assets/arm_icon.h"
#include "assets/camera_icon.h"
#include "assets/app_icon.h"

// LVGL Clock Label Handles (LOCKED & UNTOUCHED)
static lv_obj_t *lbl_hour = NULL;
static lv_obj_t *lbl_minute = NULL;
static lv_obj_t *lbl_day = NULL;
static lv_obj_t *lbl_date = NULL;

// LVGL Status Card Handles (Phase 6C)
static StatusCardUI card_rover;
static StatusCardUI card_control;
static StatusCardUI card_status;

// Bottom Action Widgets Handles
static lv_obj_t *widget_arm = NULL;
static lv_obj_t *widget_camera = NULL;
static lv_obj_t *widget_apps = NULL;

void ui_home_update_clock(const TimeData &time_data) {
  if (!time_data.is_synced) {
    if (lbl_hour) {
      lv_label_set_text(lbl_hour, "SYNC...");
      lv_obj_invalidate(lbl_hour);
    }
    if (lbl_minute) {
      lv_label_set_text(lbl_minute, "");
      lv_obj_invalidate(lbl_minute);
    }
    if (lbl_day) {
      lv_label_set_text(lbl_day, "");
      lv_obj_invalidate(lbl_day);
    }
    if (lbl_date) {
      lv_label_set_text(lbl_date, "");
      lv_obj_invalidate(lbl_date);
    }
    return;
  }

  if (lbl_hour && time_data.hour_str) {
    lv_label_set_text(lbl_hour, time_data.hour_str);
    lv_obj_invalidate(lbl_hour);
  }
  if (lbl_minute && time_data.min_str) {
    lv_label_set_text(lbl_minute, time_data.min_str);
    lv_obj_invalidate(lbl_minute);
  }
  if (lbl_day && time_data.day_str) {
    lv_label_set_text(lbl_day, time_data.day_str);
    lv_obj_invalidate(lbl_day);
  }
  if (lbl_date && time_data.date_str) {
    lv_label_set_text(lbl_date, time_data.date_str);
    lv_obj_invalidate(lbl_date);
  }

  Serial.printf("[UI CLOCK UPDATE] Hour: %s | Min: %s | Day: %s | Date: %s\n",
                time_data.hour_str, time_data.min_str, time_data.day_str,
                time_data.date_str);
}

void ui_home_update_status(const SystemStatus &status) {
  ui_update_status_card(card_rover, status.rover);
  ui_update_status_card(card_control, status.control_glove);
  ui_update_status_card(card_status, status.status_glove);
}

static void bottom_widget_event_cb(lv_event_t * e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED) {
        ScreenId target = (ScreenId)(uintptr_t)lv_event_get_user_data(e);
        if (target == SCREEN_ARM) {
            Serial.println("[UI NAV] Navigating to ARM Screen...");
            ui_switch_to(SCREEN_ARM);
        } else if (target == SCREEN_APPS) {
            Serial.println("[UI NAV] Navigating to APPS Screen...");
            ui_switch_to(SCREEN_APPS);
        } else {
            Serial.println("[UI NAV] Camera Widget Clicked!");
        }
    }
}

static lv_obj_t* create_bottom_widget(lv_obj_t * parent, int x, int y, int w, int h,
                                      const char * title,
                                      const lv_img_dsc_t * icon_dsc, ScreenId target_screen) {
    // 1. Interactive Button Container (White Card, 90% opacity, 9px radius, soft drop shadow)
    lv_obj_t * card = lv_btn_create(parent);
    lv_obj_set_size(card, w, h);
    lv_obj_set_pos(card, x, y);

    lv_obj_set_style_bg_color(card, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(card, LV_OPA_90, LV_PART_MAIN);
    lv_obj_set_style_radius(card, 9, LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 0, LV_PART_MAIN);
    lv_obj_set_style_outline_width(card, 0, LV_PART_MAIN);

    // Soft, Diffused Drop Shadow
    lv_obj_set_style_shadow_width(card, 6, LV_PART_MAIN);
    lv_obj_set_style_shadow_spread(card, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_x(card, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_ofs_y(card, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(card, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(card, LV_OPA_30, LV_PART_MAIN);

    lv_obj_set_style_pad_all(card, 0, LV_PART_MAIN);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(card, LV_OBJ_FLAG_CLICKABLE);

    // Event Callback for Screen Navigation
    lv_obj_add_event_cb(card, bottom_widget_event_cb, LV_EVENT_CLICKED, (void*)(uintptr_t)target_screen);

    // 2. Render Converted PNG Icon Asset centered horizontally at top of card (28x28 icon)
    if (icon_dsc && icon_dsc->data) {
        lv_obj_t * icon_img = lv_img_create(card);
        lv_img_set_src(icon_img, icon_dsc);
        lv_obj_align(icon_img, LV_ALIGN_TOP_MID, 0, 2);
        lv_obj_clear_flag(icon_img, LV_OBJ_FLAG_CLICKABLE);
    }

    // 3. Title Label centered horizontally underneath icon with 1px gap (10px Montserrat Bold - Dark Navy #0F172A)
    lv_obj_t * lbl_title = lv_label_create(card);
    lv_label_set_text(lbl_title, title);
    lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_align(lbl_title, LV_ALIGN_TOP_MID, 0, 31);
    lv_obj_clear_flag(lbl_title, LV_OBJ_FLAG_CLICKABLE);

    return card;
}

lv_obj_t *ui_home_create(const SystemStatus &initial_status) {
  // 1. Create Base Screen Container
  lv_obj_t *scr = lv_obj_create(NULL);
  lv_obj_set_style_pad_all(scr, 0, LV_PART_MAIN);
  lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

  // 2. Render Full-Screen CYNEXIS Wallpaper (Base Background Layer, 320x240)
  lv_obj_t *bg_img = lv_img_create(scr);
  lv_img_set_src(bg_img, &cynexis_wallpaper);
  lv_obj_set_pos(bg_img, 0, 0);
  lv_obj_set_size(bg_img, 320, 240);
  lv_obj_set_style_pad_all(bg_img, 0, LV_PART_MAIN);
  lv_obj_set_style_border_width(bg_img, 0, LV_PART_MAIN);
  lv_obj_clear_flag(bg_img, LV_OBJ_FLAG_CLICKABLE);

  // 3. Left-Side Vertically Stacked Clock Overlay Labels (LOCKED & UNTOUCHED)

  // 3a. Hour Label (Large 48px Dark Navy - Bold)
  lbl_hour = lv_label_create(bg_img);
  lv_label_set_text(lbl_hour, "SYNC...");
  lv_obj_set_style_text_font(lbl_hour, &lv_font_montserrat_48, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_hour, lv_color_hex(0x0F172A),
                              LV_PART_MAIN); // Dark Navy
  lv_obj_set_style_bg_opa(lbl_hour, LV_OPA_TRANSP,
                          LV_PART_MAIN); // 100% Transparent
  lv_obj_set_pos(lbl_hour, 14, 38);

  // 3b. Minute Label (Large 48px Dark Navy - Bold)
  lbl_minute = lv_label_create(bg_img);
  lv_label_set_text(lbl_minute, "");
  lv_obj_set_style_text_font(lbl_minute, &lv_font_montserrat_48, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_minute, lv_color_hex(0x0F172A),
                              LV_PART_MAIN); // Dark Navy
  lv_obj_set_style_bg_opa(lbl_minute, LV_OPA_TRANSP,
                          LV_PART_MAIN); // 100% Transparent
  lv_obj_set_pos(lbl_minute, 14, 86);

  // 3c. Day of Week Label (20px Slate Gray - Semi-Bold)
  lbl_day = lv_label_create(bg_img);
  lv_label_set_text(lbl_day, "");
  lv_obj_set_style_text_font(lbl_day, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_day, lv_color_hex(0x334155),
                              LV_PART_MAIN); // Dark Slate
  lv_obj_set_style_bg_opa(lbl_day, LV_OPA_TRANSP,
                          LV_PART_MAIN); // 100% Transparent
  lv_obj_set_pos(lbl_day, 14, 138);

  // 3d. Day & Month Date Label (16px Slate Gray - Regular)
  lbl_date = lv_label_create(bg_img);
  lv_label_set_text(lbl_date, "");
  lv_obj_set_style_text_font(lbl_date, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_date, lv_color_hex(0x475569),
                              LV_PART_MAIN); // Slate Gray
  lv_obj_set_style_bg_opa(lbl_date, LV_OPA_TRANSP,
                          LV_PART_MAIN); // 100% Transparent
  lv_obj_set_pos(lbl_date, 14, 162);

  // 4. Right-Side CYNEXIS Status Cards (W=126 px, X=186 px - Fits CONTROL GLOVE text without truncation)
  // 4a. Rover Card (Top Right)
  card_rover = ui_create_status_card(bg_img, 186, 32, 126, 46,
                                     initial_status.rover, ICON_ROVER);

  // 4b. Control Glove Card (Middle Right)
  card_control =
      ui_create_status_card(bg_img, 186, 84, 126, 46,
                            initial_status.control_glove, ICON_CONTROL_GLOVE);

  // 4c. Status Glove Card (Bottom Right)
  card_status =
      ui_create_status_card(bg_img, 186, 136, 126, 46,
                            initial_status.status_glove, ICON_STATUS_GLOVE);

  // 5. Bottom Action Widgets Row (H=44 px, Y=190 px)
  widget_arm = create_bottom_widget(bg_img, 8, 190, 96, 44,
                                    "ARM", &arm_icon, SCREEN_ARM);

  widget_camera = create_bottom_widget(bg_img, 112, 190, 96, 44,
                                       "CAMERA", &camera_icon, SCREEN_HOME);

  widget_apps = create_bottom_widget(bg_img, 216, 190, 96, 44,
                                     "APPS", &app_icon, SCREEN_APPS);

  return scr;
}
