#include "ui_rover.h"
#include "ui.h"
#include <Arduino.h>
#include <cstdio>

// LVGL Asset Headers for Rover Screen
#include "assets/arm_icon.h"
#include "assets/arrow_backward_icon.h"
#include "assets/arrow_forward_icon.h"
#include "assets/arrow_left_icon.h"
#include "assets/arrow_right_icon.h"
#include "assets/assistant_icon.h"
#include "assets/camera_icon.h"
#include "assets/gesture_black_icon.h"
#include "assets/gesture_white_icon.h"
#include "assets/joystick_black_icon.h"
#include "assets/joystick_white_icon.h"
#include "assets/rover_icon.h"
#include "assets/speaker_high_icon.h"
#include "assets/speaker_low_icon.h"
#include "assets/stop_icon.h"
#include "assets/voice_black_icon.h"
#include "assets/voice_white_icon.h"

// Hardware State Hook Architecture
struct RoverState {
  bool wifi_connected;
  uint8_t battery_pct;

  // Subsystem status: 0 = GREEN (Working), 1 = YELLOW (Warning), 2 = RED
  // (Stopped/Issue)
  uint8_t controller_status;
  uint8_t motors_status;
  uint8_t camera_status;
  uint8_t speaker_status;
  uint8_t fuse_status;

  bool headlight_on;

  uint16_t ultrasonic_cm;
  const char *ir_status;
  float imu_g;
  const char *ldr_status;

  uint8_t left_motor_speed;
  uint8_t left_motor_status;
  uint8_t right_motor_speed;
  uint8_t right_motor_status;

  uint8_t control_mode;  // 0: GESTURE, 1: VOICE, 2: JOYSTICK
  uint8_t speaker_level; // 0: MUTE, 1: LOW, 2: MEDIUM, 3: HIGH
};

static RoverState rover_state = {
    .wifi_connected = true,
    .battery_pct = 78,
    .controller_status = 0, // Green
    .motors_status = 0,     // Green
    .camera_status = 0,     // Green
    .speaker_status = 0,    // Green
    .fuse_status = 0,       // Green
    .headlight_on = true,
    .ultrasonic_cm = 120,
    .ir_status = "CLEAR",
    .imu_g = 0.02f,
    .ldr_status = "DARK",
    .left_motor_speed = 82,
    .left_motor_status = 0,
    .right_motor_speed = 79,
    .right_motor_status = 0,
    .control_mode = 0, // GESTURE
  };

// Live Rover State Getters for Arm App Integration
bool ui_rover_get_headlight() { return rover_state.headlight_on; }
float ui_rover_get_speed() { return 0.0f; } // Current speed display
uint8_t ui_rover_get_fuse() { return rover_state.fuse_status; }
uint8_t ui_rover_get_speaker_level() { return rover_state.speaker_level; }

// UI Object Pointers for Dynamic Updates
static lv_obj_t *btn_hl_on = NULL;
static lv_obj_t *btn_hl_off = NULL;
static lv_obj_t *btn_fwd = NULL;
static lv_obj_t *btn_bwd = NULL;
static lv_obj_t *btn_right = NULL;
static lv_obj_t *btn_left = NULL;
static lv_obj_t *btn_stop = NULL;
static lv_obj_t *mode_btns[3] = {NULL, NULL, NULL};
static lv_obj_t *mode_icons[3] = {NULL, NULL, NULL};
static lv_obj_t *vol_bars[3] = {NULL, NULL, NULL};
static lv_obj_t *action_btn_objs[3] = {NULL, NULL, NULL};

// Forward Declarations
static void update_headlight_ui(bool on);
static void update_control_mode_ui(uint8_t mode);
static void update_volume_ui(uint8_t level);

// Rover Unified Touch Router using Verified Physical Coordinate Regions
static uint32_t last_touch_cmd_ms = 0;

static void process_rover_touch_point(int16_t x, int16_t y) {
  uint32_t now = millis();
  if (now - last_touch_cmd_ms < 100) { // 100ms touch debounce guard (prevents
                                       // jitter, allows responsive tapping)
    return;
  }

  const char *action_name = NULL;

  // 1. D-PAD VERIFIED COMMAND REGIONS
  if (x >= 165 && x <= 205 && y >= 40 && y <= 72) {
    action_name = "FORWARD";
    if (btn_fwd) {
      lv_obj_add_state(btn_fwd, LV_STATE_PRESSED);
    }
    Serial.println("[ROVER CMD] FORWARD");
  } else if (x >= 165 && x <= 205 && y >= 75 && y <= 111) {
    action_name = "STOP";
    if (btn_stop) {
      lv_obj_add_state(btn_stop, LV_STATE_PRESSED);
    }
    Serial.println("[ROVER CMD] STOP");
  } else if (x >= 165 && x <= 205 && y >= 114 && y <= 152) {
    action_name = "BACKWARD";
    if (btn_bwd) {
      lv_obj_add_state(btn_bwd, LV_STATE_PRESSED);
    }
    Serial.println("[ROVER CMD] BACKWARD");
  } else if (x >= 120 && x <= 162 && y >= 75 && y <= 111) {
    action_name = "LEFT";
    if (btn_left) {
      lv_obj_add_state(btn_left, LV_STATE_PRESSED);
    }
    Serial.println("[ROVER CMD] LEFT");
  } else if (x >= 210 && x <= 250 && y >= 75 && y <= 111) {
    action_name = "RIGHT";
    if (btn_right) {
      lv_obj_add_state(btn_right, LV_STATE_PRESSED);
    }
    Serial.println("[ROVER CMD] RIGHT");
  }
  // 2. SPEAKER CONTROLS VERIFIED REGIONS
  else if (x >= 190 && x <= 215 && y >= 180 && y <= 208) {
    action_name = "SPEAKER LOW";
    if (rover_state.speaker_level > 0) {
      update_volume_ui(rover_state.speaker_level - 1);
    }
  } else if (x >= 305 && x <= 319 && y >= 180 && y <= 214) {
    action_name = "SPEAKER HIGH";
    if (rover_state.speaker_level < 3) {
      update_volume_ui(rover_state.speaker_level + 1);
    }
  } else if (x >= 220 && x <= 246 && y >= 170 && y <= 208) {
    action_name = "SPEAKER BAR 1";
    update_volume_ui(1);
  } else if (x >= 247 && x <= 274 && y >= 170 && y <= 208) {
    action_name = "SPEAKER BAR 2";
    update_volume_ui(2);
  } else if (x >= 275 && x <= 304 && y >= 170 && y <= 208) {
    action_name = "SPEAKER BAR 3";
    update_volume_ui(3);
  }
  // 3. BOTTOM ACTION BUTTONS VERIFIED REGIONS
  else if (x >= 0 && x <= 105 && y >= 214 && y <= 239) {
    action_name = "CAMERA";
    if (action_btn_objs[0]) {
      lv_obj_add_state(action_btn_objs[0], LV_STATE_PRESSED);
    }
    Serial.println("[ROVER UI] Navigating to CAMERA APP");
    ui_switch_to(SCREEN_CAMERA);
  } else if (x >= 120 && x <= 245 && y >= 214 && y <= 239) {
    action_name = "ARM";
    if (action_btn_objs[1]) {
      lv_obj_add_state(action_btn_objs[1], LV_STATE_PRESSED);
    }
    Serial.println("[ROVER UI] Navigating to ARM APP");
    ui_switch_to(SCREEN_ARM);
  } else if (x >= 255 && x <= 319 && y >= 214 && y <= 239) {
    action_name = "ASSISTANT";
    if (action_btn_objs[2]) {
      lv_obj_add_state(action_btn_objs[2], LV_STATE_PRESSED);
    }
    Serial.println("[ROVER UI] Navigating to ASSISTANT APP");
    ui_switch_to(SCREEN_ASSISTANT);
  }
  // 4. CONTROL MODE VERIFIED REGIONS
  else if (x >= 6 && x <= 52 && y >= 155 && y <= 195) {
    action_name = "GESTURE";
    update_control_mode_ui(0);
  } else if (x >= 53 && x <= 98 && y >= 155 && y <= 210) {
    action_name = "VOICE";
    if (mode_btns[1]) {
      lv_obj_add_state(mode_btns[1], LV_STATE_PRESSED);
    }
    update_control_mode_ui(1);
  } else if (x >= 99 && x <= 158 && y >= 155 && y <= 210) {
    action_name = "JOYSTICK";
    if (mode_btns[2]) {
      lv_obj_add_state(mode_btns[2], LV_STATE_PRESSED);
    }
    update_control_mode_ui(2);
  }
  // 5. HEADLIGHT VERIFIED REGIONS
  else if (x >= 6 && x <= 50 && y >= 115 && y <= 145) {
    action_name = "HEADLIGHT ON";
    update_headlight_ui(true);
  } else if (x >= 51 && x <= 98 && y >= 115 && y <= 145) {
    action_name = "HEADLIGHT OFF";
    update_headlight_ui(false);
  }
  // 6. NAVIGATION HEADER VERIFIED REGION
  else if (x >= 4 && x <= 62 && y >= 2 && y <= 30) {
    action_name = "< APPS";
    Serial.println("[ROVER UI] Navigating to APP DRAWER");
    ui_switch_to(SCREEN_APPS);
  }

  if (action_name) {
    last_touch_cmd_ms = now;
    Serial.printf("[ROVER TOUCH] x=%d y=%d -> %s\n", x, y, action_name);
  }
}

static void rover_screen_touch_cb(lv_event_t *e) {
  lv_event_code_t code = lv_event_get_code(e);
  if (code == LV_EVENT_PRESSED) {
    lv_indev_t *indev = lv_indev_get_act();
    if (indev) {
      lv_point_t point;
      lv_indev_get_point(indev, &point);
      process_rover_touch_point(point.x, point.y);
    }
  } else if (code == LV_EVENT_RELEASED) {
    if (btn_fwd) {
      lv_obj_clear_state(btn_fwd, LV_STATE_PRESSED);
    }
    if (btn_bwd) {
      lv_obj_clear_state(btn_bwd, LV_STATE_PRESSED);
    }
    if (btn_right) {
      lv_obj_clear_state(btn_right, LV_STATE_PRESSED);
    }
    if (btn_left) {
      lv_obj_clear_state(btn_left, LV_STATE_PRESSED);
    }
    if (btn_stop) {
      lv_obj_clear_state(btn_stop, LV_STATE_PRESSED);
    }
    for (int i = 0; i < 3; i++) {
      if (mode_btns[i]) {
        lv_obj_clear_state(mode_btns[i], LV_STATE_PRESSED);
      }
      if (action_btn_objs[i]) {
        lv_obj_clear_state(action_btn_objs[i], LV_STATE_PRESSED);
      }
    }
  }
}

static void update_headlight_ui(bool on) {
  rover_state.headlight_on = on;
  if (on) {
    lv_obj_set_style_bg_color(btn_hl_on, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_color(lv_obj_get_child(btn_hl_on, 0),
                                lv_color_white(), LV_PART_MAIN);

    lv_obj_set_style_bg_color(btn_hl_off, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_text_color(lv_obj_get_child(btn_hl_off, 0),
                                lv_color_hex(0x0F172A), LV_PART_MAIN);
  } else {
    lv_obj_set_style_bg_color(btn_hl_on, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_text_color(lv_obj_get_child(btn_hl_on, 0),
                                lv_color_hex(0x0F172A), LV_PART_MAIN);

    lv_obj_set_style_bg_color(btn_hl_off, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_color(lv_obj_get_child(btn_hl_off, 0),
                                lv_color_white(), LV_PART_MAIN);
  }
  Serial.printf("[ROVER] Headlight: %s\n", on ? "ON" : "OFF");
}

static void update_control_mode_ui(uint8_t mode) {
  rover_state.control_mode = mode;
  const lv_img_dsc_t *white_icons[3] = {&gesture_white_icon, &voice_white_icon,
                                        &joystick_white_icon};
  const lv_img_dsc_t *black_icons[3] = {&gesture_black_icon, &voice_black_icon,
                                        &joystick_black_icon};
  const char *mode_names[3] = {"GESTURE", "VOICE", "JOYSTICK"};

  for (int i = 0; i < 3; i++) {
    if (i == mode) {
      lv_obj_set_style_bg_color(mode_btns[i], lv_color_hex(0x2563EB),
                                LV_PART_MAIN);
      lv_img_set_src(mode_icons[i], white_icons[i]);
    } else {
      lv_obj_set_style_bg_color(mode_btns[i], lv_color_hex(0xF1F5F9),
                                LV_PART_MAIN);
      lv_img_set_src(mode_icons[i], black_icons[i]);
    }
    lv_img_set_zoom(mode_icons[i], 230);
  }
  Serial.printf("[ROVER] Control Mode: %s\n", mode_names[mode]);
}

static void update_volume_ui(uint8_t level) {
  if (level > 3)
    level = 3;
  rover_state.speaker_level = level;

  for (int i = 0; i < 3; i++) {
    if (i < level) {
      lv_obj_set_style_bg_color(vol_bars[i], lv_color_hex(0x2563EB),
                                LV_PART_MAIN);
    } else {
      lv_obj_set_style_bg_color(vol_bars[i], lv_color_hex(0xCBD5E1),
                                LV_PART_MAIN);
    }
  }

  const char *lvl_names[4] = {"MUTE", "LOW", "MEDIUM", "HIGH"};
  Serial.printf("[ROVER] Speaker Volume Level: %s (%d/3)\n", lvl_names[level],
                level);
}

// Helper: Card Container Creator with Subtle LVGL Box Shadow
static lv_obj_t *create_card(lv_obj_t *parent, int x, int y, int w, int h) {
  lv_obj_t *card = lv_obj_create(parent);
  lv_obj_set_pos(card, x, y);
  lv_obj_set_size(card, w, h);
  lv_obj_set_style_bg_color(card, lv_color_white(), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(card, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_radius(card, 8, LV_PART_MAIN);
  lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(card, lv_color_hex(0xE2E8F0), LV_PART_MAIN);

  // Subtle LVGL Box Shadow
  lv_obj_set_style_shadow_width(card, 4, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(card, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(card, (lv_opa_t)20, LV_PART_MAIN);

  lv_obj_set_style_pad_all(card, 3, LV_PART_MAIN);
  lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(
      card, LV_OBJ_FLAG_CLICKABLE); // Containers must not intercept touches
  return card;
}

// Helper: Section Title Label
static void create_card_title(lv_obj_t *parent, const char *title) {
  lv_obj_t *lbl = lv_label_create(parent);
  lv_label_set_text(lbl, title);
  lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 2, 0);
}

// Helper: Status Row Creator with Colored Dot ONLY (NO status words beside
// dots)
static void create_status_row(lv_obj_t *parent, int y, const char *name,
                              uint8_t status_state) {
  lv_obj_t *lbl_name = lv_label_create(parent);
  lv_label_set_text(lbl_name, name);
  lv_obj_set_style_text_font(lbl_name, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_name, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_name, 2, y);

  lv_obj_t *dot = lv_obj_create(parent);
  lv_obj_set_size(dot, 6, 6);
  lv_obj_set_pos(dot, lv_obj_get_width(parent) - 12, y + 2);
  lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);

  lv_color_t dot_color;
  if (status_state == 0) {
    dot_color = lv_color_hex(0x22C55E); // Green (Working)
  } else if (status_state == 1) {
    dot_color = lv_color_hex(0xEAB308); // Yellow (Warning)
  } else {
    dot_color = lv_color_hex(0xEF4444); // Red (Stopped / Issue)
  }

  lv_obj_set_style_bg_color(dot, dot_color, LV_PART_MAIN);
  lv_obj_set_style_border_width(dot, 0, LV_PART_MAIN);
}

// Helper: D-Pad Button Creator with Strict Event & Hitbox Isolation
static lv_obj_t *create_dpad_button(lv_obj_t *parent, int x, int y, int w,
                                    int h, const lv_img_dsc_t *icon,
                                    const char *label_text, lv_color_t bg_color,
                                    const char *cmd) {
  lv_obj_t *btn = lv_btn_create(parent);
  lv_obj_set_pos(btn, x, y);
  lv_obj_set_size(btn, w, h);
  lv_obj_set_style_bg_color(btn, bg_color, LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn, lv_color_hex(0x1D4ED8), LV_STATE_PRESSED);
  lv_obj_set_style_radius(btn, 6, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn, 0, LV_PART_MAIN);
  lv_obj_set_style_shadow_width(btn, 3, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(btn, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(btn, LV_OPA_30, LV_PART_MAIN);

  // Strict hitbox isolation: zero extended click area & no individual callback
  // interference
  lv_obj_set_ext_click_area(btn, 0);
  lv_obj_clear_flag(btn, LV_OBJ_FLAG_CLICKABLE);

  if (icon) {
    lv_obj_t *img = lv_img_create(btn);
    lv_img_set_src(img, icon);
    lv_obj_clear_flag(img, LV_OBJ_FLAG_CLICKABLE);
    if (label_text) {
      lv_obj_align(img, LV_ALIGN_CENTER, 0, -4);
      lv_obj_t *lbl = lv_label_create(btn);
      lv_label_set_text(lbl, label_text);
      lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, LV_PART_MAIN);
      lv_obj_set_style_text_color(lbl, lv_color_white(), LV_PART_MAIN);
      lv_obj_align(lbl, LV_ALIGN_BOTTOM_MID, 0, -1);
      lv_obj_clear_flag(lbl, LV_OBJ_FLAG_CLICKABLE);
    } else {
      lv_obj_center(img);
    }
  } else if (label_text) {
    lv_obj_t *lbl = lv_label_create(btn);
    lv_label_set_text(lbl, label_text);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl, lv_color_white(), LV_PART_MAIN);
    lv_obj_center(lbl);
    lv_obj_clear_flag(lbl, LV_OBJ_FLAG_CLICKABLE);
  }
  return btn;
}

lv_obj_t *ui_rover_create() {
  // 1. Base Screen Container (320x240 - Pure White Background, ABSOLUTELY NO
  // SCROLLING)
  lv_obj_t *scr = lv_obj_create(NULL);
  lv_obj_set_style_bg_color(scr, lv_color_white(), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_pad_all(scr, 0, LV_PART_MAIN);
  lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

  // Register Unified Screen Touch Event Handler
  lv_obj_add_event_cb(scr, rover_screen_touch_cb, LV_EVENT_ALL, NULL);

  // 2. Main Glass Panel Container (312x232 at X=4, Y=4 - Pure White Surface)
  lv_obj_t *glass_panel = lv_obj_create(scr);
  lv_obj_set_size(glass_panel, 312, 232);
  lv_obj_set_pos(glass_panel, 4, 4);
  lv_obj_set_style_bg_color(glass_panel, lv_color_white(), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(glass_panel, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_radius(glass_panel, 12, LV_PART_MAIN);
  lv_obj_set_style_border_width(glass_panel, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(glass_panel, lv_color_hex(0xE2E8F0),
                                LV_PART_MAIN);
  lv_obj_set_style_shadow_width(glass_panel, 6, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(glass_panel, lv_color_hex(0x0F172A),
                                LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(glass_panel, (lv_opa_t)20, LV_PART_MAIN);
  lv_obj_set_style_pad_all(glass_panel, 0, LV_PART_MAIN);
  lv_obj_clear_flag(glass_panel, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(glass_panel, LV_OBJ_FLAG_CLICKABLE);

  // 3. Compact Header Navigation Bar (Y=2..24)
  // 3a. Back to App Drawer Button (< APPS)
  lv_obj_t *btn_back = lv_btn_create(glass_panel);
  lv_obj_set_pos(btn_back, 4, 2);
  lv_obj_set_size(btn_back, 54, 22);
  lv_obj_set_style_bg_color(btn_back, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(btn_back, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_radius(btn_back, 5, LV_PART_MAIN);
  lv_obj_set_style_border_width(btn_back, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(btn_back, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
  lv_obj_set_style_shadow_width(btn_back, 2, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(btn_back, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(btn_back, LV_OPA_20, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_back, 0, LV_PART_MAIN);
  lv_obj_set_ext_click_area(btn_back, 0);
  lv_obj_clear_flag(btn_back, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_back = lv_label_create(btn_back);
  lv_label_set_text(lbl_back, "< APPS");
  lv_obj_set_style_text_font(lbl_back, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_back, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_center(lbl_back);

  // 3b. Wi-Fi Status Indicator
  lv_obj_t *wifi_dot = lv_obj_create(glass_panel);
  lv_obj_set_size(wifi_dot, 6, 6);
  lv_obj_set_pos(wifi_dot, 168, 9);
  lv_obj_set_style_radius(wifi_dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(wifi_dot, lv_color_hex(0x22C55E), LV_PART_MAIN);
  lv_obj_set_style_border_width(wifi_dot, 0, LV_PART_MAIN);
  lv_obj_clear_flag(wifi_dot, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_wifi = lv_label_create(glass_panel);
  lv_label_set_text(lbl_wifi, "CONNECTED");
  lv_obj_set_style_text_font(lbl_wifi, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_wifi, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_wifi, 178, 5);

  // 3c. Battery Icon & Percentage (Positioned at far right end of header)
  lv_obj_t *bat_body = lv_obj_create(glass_panel);
  lv_obj_set_pos(bat_body, 258, 7);
  lv_obj_set_size(bat_body, 13, 8);
  lv_obj_set_style_bg_color(bat_body, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(bat_body, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_border_width(bat_body, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(bat_body, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_radius(bat_body, 1, LV_PART_MAIN);
  lv_obj_set_style_pad_all(bat_body, 0, LV_PART_MAIN);
  lv_obj_clear_flag(bat_body, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(bat_body, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *bat_fill = lv_obj_create(bat_body);
  lv_obj_set_pos(bat_fill, 1, 1);
  lv_obj_set_size(bat_fill, 9, 4);
  lv_obj_set_style_bg_color(bat_fill, lv_color_hex(0x22C55E), LV_PART_MAIN);
  lv_obj_set_style_border_width(bat_fill, 0, LV_PART_MAIN);
  lv_obj_clear_flag(bat_fill, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *bat_tip = lv_obj_create(glass_panel);
  lv_obj_set_pos(bat_tip, 271, 9);
  lv_obj_set_size(bat_tip, 2, 4);
  lv_obj_set_style_bg_color(bat_tip, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_border_width(bat_tip, 0, LV_PART_MAIN);
  lv_obj_clear_flag(bat_tip, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_bat = lv_label_create(glass_panel);
  char bat_buf[16];
  snprintf(bat_buf, sizeof(bat_buf), "%d%%", rover_state.battery_pct);
  lv_label_set_text(lbl_bat, bat_buf);
  lv_obj_set_style_text_font(lbl_bat, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_bat, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_pos(lbl_bat, 276, 5);

  // 4. MAIN CONTENT GRID (Y = 26..150)
  // 4. MAIN CONTENT GRID (Y = 26..150)
  // -------------------------------------------------------------
  // COLUMN 1: ROVER STATUS & HEADLIGHT (Left: X=4, W=96, H=124)
  // -------------------------------------------------------------
  lv_obj_t *card_status = create_card(glass_panel, 4, 26, 96, 124);
  create_card_title(card_status, "ROVER STATUS");

  // All 5 fields with status dots ONLY (NO status words)
  create_status_row(card_status, 14, "Controller",
                    rover_state.controller_status);
  create_status_row(card_status, 26, "Motors", rover_state.motors_status);
  create_status_row(card_status, 38, "Camera", rover_state.camera_status);
  create_status_row(card_status, 50, "Speaker", rover_state.speaker_status);
  create_status_row(card_status, 62, "Fuse", rover_state.fuse_status);

  // Headlight Sub-Section inside Column 1
  lv_obj_t *lbl_hl = lv_label_create(card_status);
  lv_label_set_text(lbl_hl, "HEADLIGHT");
  lv_obj_set_style_text_font(lbl_hl, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_hl, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_pos(lbl_hl, 2, 78);

  // Continuous Segmented Selector [ ON | OFF ] (W=86, H=20)
  lv_obj_t *seg_hl = lv_obj_create(card_status);
  lv_obj_set_pos(seg_hl, 2, 92);
  lv_obj_set_size(seg_hl, 86, 20);
  lv_obj_set_style_bg_color(seg_hl, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
  lv_obj_set_style_radius(seg_hl, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(seg_hl, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(seg_hl, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
  lv_obj_set_style_pad_all(seg_hl, 0, LV_PART_MAIN);
  lv_obj_clear_flag(seg_hl, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(seg_hl, LV_OBJ_FLAG_CLICKABLE);

  btn_hl_on = lv_btn_create(seg_hl);
  lv_obj_set_pos(btn_hl_on, 0, 0);
  lv_obj_set_size(btn_hl_on, 43, 18);
  lv_obj_set_style_radius(btn_hl_on, 3, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_hl_on, 0, LV_PART_MAIN);
  lv_obj_set_ext_click_area(btn_hl_on, 0);
  lv_obj_clear_flag(btn_hl_on, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_on = lv_label_create(btn_hl_on);
  lv_label_set_text(lbl_on, "ON");
  lv_obj_set_style_text_font(lbl_on, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_center(lbl_on);

  btn_hl_off = lv_btn_create(seg_hl);
  lv_obj_set_pos(btn_hl_off, 43, 0);
  lv_obj_set_size(btn_hl_off, 43, 18);
  lv_obj_set_style_radius(btn_hl_off, 3, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_hl_off, 0, LV_PART_MAIN);
  lv_obj_set_ext_click_area(btn_hl_off, 0);
  lv_obj_clear_flag(btn_hl_off, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_off = lv_label_create(btn_hl_off);
  lv_label_set_text(lbl_off, "OFF");
  lv_obj_set_style_text_font(lbl_off, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_center(lbl_off);

  update_headlight_ui(rover_state.headlight_on);

  // -------------------------------------------------------------
  // COLUMN 2: ROVER CONTROL D-PAD (Center: X=104, W=104, H=124)
  // Non-overlapping isolated touch hitboxes
  // -------------------------------------------------------------
  lv_obj_t *card_dpad = create_card(glass_panel, 104, 26, 104, 124);
  lv_obj_set_style_pad_all(card_dpad, 0, LV_PART_MAIN);

  // Card title explicitly positioned to preserve visual alignment (X=5, Y=3)
  lv_obj_t *lbl_dpad_title = lv_label_create(card_dpad);
  lv_label_set_text(lbl_dpad_title, "ROVER CONTROL");
  lv_obj_set_style_text_font(lbl_dpad_title, &lv_font_montserrat_10,
                             LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_dpad_title, lv_color_hex(0x0F172A),
                              LV_PART_MAIN);
  lv_obj_set_pos(lbl_dpad_title, 5, 3);

  // D-Pad Buttons with zero extended click area (Strict Hitbox Isolation)
  btn_fwd = create_dpad_button(card_dpad, 36, 14, 32, 30, &arrow_forward_icon,
                               NULL, lv_color_hex(0x2563EB), "FORWARD");
  btn_left = create_dpad_button(card_dpad, 2, 48, 32, 30, &arrow_left_icon,
                                NULL, lv_color_hex(0x2563EB), "LEFT");
  btn_stop = create_dpad_button(card_dpad, 36, 48, 32, 30, &stop_icon, NULL,
                                lv_color_hex(0xEF4444), "STOP");
  lv_obj_set_style_bg_color(btn_stop, lv_color_hex(0xB91C1C), LV_STATE_PRESSED);
  btn_right = create_dpad_button(card_dpad, 70, 48, 32, 30, &arrow_right_icon,
                                 NULL, lv_color_hex(0x2563EB), "RIGHT");
  btn_bwd = create_dpad_button(card_dpad, 36, 82, 32, 30, &arrow_backward_icon,
                               NULL, lv_color_hex(0x2563EB), "BACKWARD");

  // -------------------------------------------------------------
  // COLUMN 3: SENSOR STATUS & MOTOR STATUS (Right: X=212, W=96, H=124)
  // -------------------------------------------------------------
  // Top Half: SENSOR STATUS (Height=60, Width=96)
  lv_obj_t *card_sensor = create_card(glass_panel, 212, 26, 96, 60);
  create_card_title(card_sensor, "SENSOR STATUS");

  // Status rows with values
  lv_obj_t *lbl_s1 = lv_label_create(card_sensor);
  lv_label_set_text(lbl_s1, "Sonic");
  lv_obj_set_style_text_font(lbl_s1, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_s1, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_s1, 2, 13);
  lv_obj_t *val_s1 = lv_label_create(card_sensor);
  lv_label_set_text(val_s1, "120cm");
  lv_obj_set_style_text_font(val_s1, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(val_s1, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(val_s1, LV_ALIGN_TOP_RIGHT, -2, 13);

  lv_obj_t *lbl_s2 = lv_label_create(card_sensor);
  lv_label_set_text(lbl_s2, "IR");
  lv_obj_set_style_text_font(lbl_s2, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_s2, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_s2, 2, 24);
  lv_obj_t *val_s2 = lv_label_create(card_sensor);
  lv_label_set_text(val_s2, "CLEAR");
  lv_obj_set_style_text_font(val_s2, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(val_s2, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(val_s2, LV_ALIGN_TOP_RIGHT, -2, 24);

  lv_obj_t *lbl_s3 = lv_label_create(card_sensor);
  lv_label_set_text(lbl_s3, "IMU");
  lv_obj_set_style_text_font(lbl_s3, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_s3, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_s3, 2, 35);
  lv_obj_t *val_s3 = lv_label_create(card_sensor);
  lv_label_set_text(val_s3, "0.02g");
  lv_obj_set_style_text_font(val_s3, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(val_s3, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(val_s3, LV_ALIGN_TOP_RIGHT, -2, 35);

  lv_obj_t *lbl_s4 = lv_label_create(card_sensor);
  lv_label_set_text(lbl_s4, "LDR");
  lv_obj_set_style_text_font(lbl_s4, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_s4, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_s4, 2, 46);
  lv_obj_t *val_s4 = lv_label_create(card_sensor);
  lv_label_set_text(val_s4, "DARK");
  lv_obj_set_style_text_font(val_s4, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(val_s4, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(val_s4, LV_ALIGN_TOP_RIGHT, -2, 46);

  // Bottom Half: MOTOR STATUS (Height=60, Width=96)
  lv_obj_t *card_motor = create_card(glass_panel, 212, 90, 96, 60);
  create_card_title(card_motor, "MOTOR STATUS");

  // Left Row
  lv_obj_t *lbl_lm = lv_label_create(card_motor);
  lv_label_set_text(lbl_lm, "Left");
  lv_obj_set_style_text_font(lbl_lm, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_lm, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_lm, 2, 13);

  lv_obj_t *lbl_lm_pct = lv_label_create(card_motor);
  lv_label_set_text(lbl_lm_pct, "82%");
  lv_obj_set_style_text_font(lbl_lm_pct, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_lm_pct, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(lbl_lm_pct, LV_ALIGN_TOP_RIGHT, -12, 13);

  lv_obj_t *dot_lm = lv_obj_create(card_motor);
  lv_obj_set_size(dot_lm, 5, 5);
  lv_obj_set_pos(dot_lm, 82, 16);
  lv_obj_set_style_radius(dot_lm, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(dot_lm, lv_color_hex(0x22C55E), LV_PART_MAIN);
  lv_obj_set_style_border_width(dot_lm, 0, LV_PART_MAIN);

  lv_obj_t *bar_lm = lv_bar_create(card_motor);
  lv_obj_set_pos(bar_lm, 2, 25);
  lv_obj_set_size(bar_lm, 86, 4);
  lv_bar_set_value(bar_lm, 82, LV_ANIM_OFF);
  lv_obj_set_style_bg_color(bar_lm, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
  lv_obj_set_style_bg_color(bar_lm, lv_color_hex(0x2563EB), LV_PART_INDICATOR);

  // Right Row
  lv_obj_t *lbl_rm = lv_label_create(card_motor);
  lv_label_set_text(lbl_rm, "Right");
  lv_obj_set_style_text_font(lbl_rm, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_rm, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_rm, 2, 33);

  lv_obj_t *lbl_rm_pct = lv_label_create(card_motor);
  lv_label_set_text(lbl_rm_pct, "79%");
  lv_obj_set_style_text_font(lbl_rm_pct, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_rm_pct, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_align(lbl_rm_pct, LV_ALIGN_TOP_RIGHT, -12, 33);

  lv_obj_t *dot_rm = lv_obj_create(card_motor);
  lv_obj_set_size(dot_rm, 5, 5);
  lv_obj_set_pos(dot_rm, 82, 36);
  lv_obj_set_style_radius(dot_rm, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(dot_rm, lv_color_hex(0x22C55E), LV_PART_MAIN);
  lv_obj_set_style_border_width(dot_rm, 0, LV_PART_MAIN);

  lv_obj_t *bar_rm = lv_bar_create(card_motor);
  lv_obj_set_pos(bar_rm, 2, 45);
  lv_obj_set_size(bar_rm, 86, 4);
  lv_bar_set_value(bar_rm, 79, LV_ANIM_OFF);
  lv_obj_set_style_bg_color(bar_rm, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
  lv_obj_set_style_bg_color(bar_rm, lv_color_hex(0x2563EB), LV_PART_INDICATOR);

  // 5. CONTROL MODE & SPEAKER VOLUME ROW (Y = 153..196)
  // -------------------------------------------------------------
  // LEFT: CONTROL MODE (X=4, W=146, H=43) - ICONS ONLY (18px x 18px)
  // -------------------------------------------------------------
  lv_obj_t *card_mode = create_card(glass_panel, 4, 153, 146, 43);
  create_card_title(card_mode, "CONTROL MODE");

  // Continuous Segmented Selector [ GESTURE | VOICE | JOYSTICK ]
  lv_obj_t *seg_mode = lv_obj_create(card_mode);
  lv_obj_set_pos(seg_mode, 2, 12);
  lv_obj_set_size(seg_mode, 136, 26);
  lv_obj_set_style_bg_color(seg_mode, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
  lv_obj_set_style_radius(seg_mode, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(seg_mode, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(seg_mode, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
  lv_obj_set_style_pad_all(seg_mode, 0, LV_PART_MAIN);
  lv_obj_clear_flag(seg_mode, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(seg_mode, LV_OBJ_FLAG_CLICKABLE);

  for (int i = 0; i < 3; i++) {
    mode_btns[i] = lv_btn_create(seg_mode);
    lv_obj_set_pos(mode_btns[i], i * 45 + (i == 2 ? 1 : 0), 0);
    lv_obj_set_size(mode_btns[i], 45, 24);
    lv_obj_set_style_radius(mode_btns[i], 3, LV_PART_MAIN);
    lv_obj_set_style_pad_all(mode_btns[i], 0, LV_PART_MAIN);
    lv_obj_set_ext_click_area(mode_btns[i], 0);
    lv_obj_clear_flag(mode_btns[i], LV_OBJ_FLAG_CLICKABLE);

    // Icon ONLY (centered, scaled to 18px x 18px via LVGL zoom factor 230, NO
    // text labels)
    mode_icons[i] = lv_img_create(mode_btns[i]);
    lv_img_set_zoom(mode_icons[i], 230);
    lv_obj_set_size(mode_icons[i], LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_center(mode_icons[i]);
    lv_obj_clear_flag(mode_icons[i], LV_OBJ_FLAG_CLICKABLE);
  }
  update_control_mode_ui(rover_state.control_mode);

  // -------------------------------------------------------------
  // RIGHT: SPEAKER VOLUME (X=154, W=154, H=43)
  // Strict isolation: Zero extended click area across all volume elements
  // -------------------------------------------------------------
  lv_obj_t *card_vol = create_card(glass_panel, 154, 153, 154, 43);
  create_card_title(card_vol, "SPEAKER VOLUME");

  // Low Speaker Icon Tile (Left Button -> Decreases volume: HIGH -> MEDIUM ->
  // LOW -> MUTE)
  lv_obj_t *tile_spk_low = lv_btn_create(card_vol);
  lv_obj_set_pos(tile_spk_low, 2, 14);
  lv_obj_set_size(tile_spk_low, 24, 22);
  lv_obj_set_style_bg_color(tile_spk_low, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
  lv_obj_set_style_radius(tile_spk_low, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(tile_spk_low, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(tile_spk_low, lv_color_hex(0xE2E8F0),
                                LV_PART_MAIN);
  lv_obj_set_style_pad_all(tile_spk_low, 0, LV_PART_MAIN);

  // Strict hitbox isolation: zero extended click area to prevent overlap with
  // ROBOTIC ARM
  lv_obj_set_ext_click_area(tile_spk_low, 0);
  lv_obj_clear_flag(tile_spk_low, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *img_spk_low = lv_img_create(tile_spk_low);
  lv_img_set_src(img_spk_low, &speaker_low_icon);
  lv_img_set_zoom(img_spk_low, 256);
  lv_obj_set_size(img_spk_low, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
  lv_obj_center(img_spk_low);
  lv_obj_clear_flag(img_spk_low, LV_OBJ_FLAG_CLICKABLE);

  // Three Separated Horizontal Volume Bar Sections in Middle (W=88, H=12)
  for (int i = 0; i < 3; i++) {
    vol_bars[i] = lv_btn_create(card_vol);
    lv_obj_set_pos(vol_bars[i], 30 + i * 30, 19);
    lv_obj_set_size(vol_bars[i], 26, 12);
    lv_obj_set_style_radius(vol_bars[i], 3, LV_PART_MAIN);
    lv_obj_set_style_pad_all(vol_bars[i], 0, LV_PART_MAIN);
    lv_obj_set_ext_click_area(vol_bars[i], 0);
    lv_obj_clear_flag(vol_bars[i], LV_OBJ_FLAG_CLICKABLE);
  }
  update_volume_ui(rover_state.speaker_level);

  // High Speaker Icon Tile (Right Button -> Increases volume: MUTE -> LOW ->
  // MEDIUM -> HIGH)
  lv_obj_t *tile_spk_high = lv_btn_create(card_vol);
  lv_obj_set_pos(tile_spk_high, 122, 14);
  lv_obj_set_size(tile_spk_high, 24, 22);
  lv_obj_set_style_bg_color(tile_spk_high, lv_color_hex(0xF1F5F9),
                            LV_PART_MAIN);
  lv_obj_set_style_radius(tile_spk_high, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(tile_spk_high, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(tile_spk_high, lv_color_hex(0xE2E8F0),
                                LV_PART_MAIN);
  lv_obj_set_style_pad_all(tile_spk_high, 0, LV_PART_MAIN);

  // Strict hitbox isolation: zero extended click area to prevent overlap
  lv_obj_set_ext_click_area(tile_spk_high, 0);
  lv_obj_clear_flag(tile_spk_high, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *img_spk_high = lv_img_create(tile_spk_high);
  lv_img_set_src(img_spk_high, &speaker_high_icon);
  lv_img_set_zoom(img_spk_high, 256);
  lv_obj_set_size(img_spk_high, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
  lv_obj_center(img_spk_high);
  lv_obj_clear_flag(img_spk_high, LV_OBJ_FLAG_CLICKABLE);

  // 6. BOTTOM ACTION BUTTONS (Y = 199..225)
  // -------------------------------------------------------------
  // [ CAMERA ] [ ROBOTIC ARM ] [ OPEN ASSISTANCE ]
  // -------------------------------------------------------------
  struct ActionBtn {
    const char *label;
    const lv_img_dsc_t *icon;
    int x;
  } action_btns[3] = {{"CAMERA", &camera_icon, 4},
                      {"ARM", &arm_icon, 108},
                      {"ASSISTANT", &assistant_icon, 212}};

  for (int i = 0; i < 3; i++) {
    lv_obj_t *abtn = lv_btn_create(glass_panel);
    action_btn_objs[i] = abtn;
    lv_obj_set_pos(abtn, action_btns[i].x, 199);
    lv_obj_set_size(abtn, 96, 26);
    lv_obj_set_style_bg_color(abtn, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_color(abtn, lv_color_hex(0xE2E8F0), LV_STATE_PRESSED);
    lv_obj_set_style_bg_opa(abtn, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(abtn, 6, LV_PART_MAIN);
    lv_obj_set_style_border_width(abtn, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(abtn, lv_color_hex(0xE2E8F0), LV_PART_MAIN);

    // Subtle LVGL Box Shadow
    lv_obj_set_style_shadow_width(abtn, 3, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(abtn, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(abtn, LV_OPA_20, LV_PART_MAIN);

    lv_obj_set_style_pad_all(abtn, 0, LV_PART_MAIN);

    // Strict hitbox isolation: zero extended click area to prevent overlap with
    // SPEAKER LOW
    lv_obj_set_ext_click_area(abtn, 0);
    lv_obj_clear_flag(abtn, LV_OBJ_FLAG_CLICKABLE);

    if (action_btns[i].icon && action_btns[i].icon->data) {
      lv_obj_t *aimg = lv_img_create(abtn);
      lv_img_set_src(aimg, action_btns[i].icon);
      lv_obj_align(aimg, LV_ALIGN_LEFT_MID, 4, 0);
      lv_obj_clear_flag(aimg, LV_OBJ_FLAG_CLICKABLE);

      lv_obj_t *albl = lv_label_create(abtn);
      lv_label_set_text(albl, action_btns[i].label);
      lv_obj_set_style_text_font(albl, &lv_font_montserrat_10, LV_PART_MAIN);
      lv_obj_set_style_text_color(albl, lv_color_hex(0x0F172A), LV_PART_MAIN);
      lv_obj_align_to(albl, aimg, LV_ALIGN_OUT_RIGHT_MID, 4, 0);
      lv_obj_clear_flag(albl, LV_OBJ_FLAG_CLICKABLE);
    } else {
      lv_obj_t *albl = lv_label_create(abtn);
      lv_label_set_text(albl, action_btns[i].label);
      lv_obj_set_style_text_font(albl, &lv_font_montserrat_10, LV_PART_MAIN);
      lv_obj_set_style_text_color(albl, lv_color_hex(0x0F172A), LV_PART_MAIN);
      lv_obj_center(albl);
      lv_obj_clear_flag(albl, LV_OBJ_FLAG_CLICKABLE);
    }
  }

  return scr;
}
