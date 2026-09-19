#include "ui_arm.h"
#include "ui.h"
#include "ui_rover.h"
#include <Arduino.h>
#include <cstdio>

// LVGL Asset Headers for Arm Screen
#include "assets/arm_icon.h"
#include "assets/assistant_icon.h"
#include "assets/camera_icon.h"
#include "assets/gesture_black_icon.h"
#include "assets/gesture_white_icon.h"
#include "assets/joystick_black_icon.h"
#include "assets/joystick_white_icon.h"
#include "assets/rover_icon.h"
#include "assets/voice_black_icon.h"
#include "assets/voice_white_icon.h"

// Hardware State Hook Architecture for Robotic Arm
struct ArmState {
  bool wifi_connected;
  uint8_t selected_servo;  // 0..6
  int16_t servo_angles[7]; // ARM_A1, ARM_A2, ARM_B, GRIPPER, ROOT, WRIST_A, WRIST_B
  uint8_t control_mode;    // 0: GESTURE, 1: VOICE, 2: JOYSTICK
};

static ArmState arm_state = {
  .wifi_connected = true,
  .selected_servo = 0,       // ARM_A1
  .servo_angles = {90, 45, 120, 30, 90, 60, 150},
  .control_mode = 0          // GESTURE
};

const char * servo_names[7] = {
  "ARM_A1", "ARM_A2", "ARM_B", "GRIPPER", "ROOT", "WRIST_A", "WRIST_B"
};

// UI Object Pointers for Dynamic Updates
static lv_obj_t * btn_back = NULL;
static lv_obj_t * mode_btns[3] = {NULL, NULL, NULL};
static lv_obj_t * mode_icons[3] = {NULL, NULL, NULL};
static lv_obj_t * action_btn_objs[3] = {NULL, NULL, NULL};
static lv_obj_t * servo_btns[7] = {NULL, NULL, NULL, NULL, NULL, NULL, NULL};
static lv_obj_t * servo_btn_labels[7] = {NULL, NULL, NULL, NULL, NULL, NULL, NULL};
static lv_obj_t * lbl_ctrl_title = NULL;
static lv_obj_t * lbl_ctrl_angle = NULL;
static lv_obj_t * lbl_servo_angles[7] = {NULL, NULL, NULL, NULL, NULL, NULL, NULL};
static lv_obj_t * btn_minus = NULL;
static lv_obj_t * btn_plus = NULL;
static lv_obj_t * btn_rest = NULL;
static lv_obj_t * btn_stop = NULL;

// Forward Declarations
static void update_control_mode_ui(uint8_t mode);
static void select_servo(uint8_t index);
static void update_servo_status_ui();

// Arm Unified Touch Router using Verified Physical Coordinate Regions
static uint32_t last_touch_cmd_ms = 0;

static void process_arm_touch_point(int16_t x, int16_t y) {
  uint32_t now = millis();
  if (now - last_touch_cmd_ms < 100) { // 100ms touch debounce guard
    return;
  }

  const char * action_name = NULL;

  // 1. NAVIGATION HEADER (< APPS)
  if (x >= 4 && x <= 62 && y >= 2 && y <= 30) {
    action_name = "< APPS";
    if (btn_back) lv_obj_add_state(btn_back, LV_STATE_PRESSED);
    Serial.println("[ARM UI] Navigating to APP DRAWER");
    ui_switch_to(SCREEN_APPS);
  }
  // 2. SERVO SELECTION BUTTONS (Expanded Card 2: X=94..218, Y=38..106)
  else if (x >= 104 && x <= 182 && y >= 38 && y <= 55) {
    action_name = "SELECT ARM_A1";
    if (servo_btns[0]) lv_obj_add_state(servo_btns[0], LV_STATE_PRESSED);
    select_servo(0);
  } else if (x >= 183 && x <= 250 && y >= 38 && y <= 55) {
    action_name = "SELECT ARM_A2";
    if (servo_btns[1]) lv_obj_add_state(servo_btns[1], LV_STATE_PRESSED);
    select_servo(1);
  } else if (x >= 104 && x <= 158 && y >= 56 && y <= 72) {
    action_name = "SELECT ARM_B";
    if (servo_btns[2]) lv_obj_add_state(servo_btns[2], LV_STATE_PRESSED);
    select_servo(2);
  } else if (x >= 159 && x <= 259 && y >= 56 && y <= 72) {
    action_name = "SELECT GRIPPER";
    if (servo_btns[3]) lv_obj_add_state(servo_btns[3], LV_STATE_PRESSED);
    select_servo(3);
  } else if (x >= 104 && x <= 181 && y >= 73 && y <= 89) {
    action_name = "SELECT ROOT";
    if (servo_btns[4]) lv_obj_add_state(servo_btns[4], LV_STATE_PRESSED);
    select_servo(4);
  } else if (x >= 182 && x <= 259 && y >= 73 && y <= 89) {
    action_name = "SELECT WRIST_A";
    if (servo_btns[5]) lv_obj_add_state(servo_btns[5], LV_STATE_PRESSED);
    select_servo(5);
  } else if (x >= 94 && x <= 155 && y >= 90 && y <= 108) {
    action_name = "SELECT WRIST_B";
    if (servo_btns[6]) lv_obj_add_state(servo_btns[6], LV_STATE_PRESSED);
    select_servo(6);
  }
  // 3. SERVO ANGLE CONTROL BUTTONS (- / +) (Expanded Targets: MINUS X=102..134, PLUS X=186..218)
  else if (x >= 102 && x <= 134 && y >= 120 && y <= 148) {
    action_name = "MINUS ANGLE";
    if (btn_minus) lv_obj_add_state(btn_minus, LV_STATE_PRESSED);
    int16_t cur = arm_state.servo_angles[arm_state.selected_servo];
    if (cur > 0) {
      cur -= 5;
      if (cur < 0) cur = 0;
      arm_state.servo_angles[arm_state.selected_servo] = cur;
      if (lbl_ctrl_angle) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%d°", cur);
        lv_label_set_text(lbl_ctrl_angle, buf);
      }
      update_servo_status_ui();
      Serial.printf("[ARM] Decremented %s angle to %d°\n", servo_names[arm_state.selected_servo], cur);
    }
  } else if (x >= 186 && x <= 218 && y >= 120 && y <= 148) {
    action_name = "PLUS ANGLE";
    if (btn_plus) lv_obj_add_state(btn_plus, LV_STATE_PRESSED);
    int16_t cur = arm_state.servo_angles[arm_state.selected_servo];
    if (cur < 180) {
      cur += 5;
      if (cur > 180) cur = 180;
      arm_state.servo_angles[arm_state.selected_servo] = cur;
      if (lbl_ctrl_angle) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%d°", cur);
        lv_label_set_text(lbl_ctrl_angle, buf);
      }
      update_servo_status_ui();
      Serial.printf("[ARM] Incremented %s angle to %d°\n", servo_names[arm_state.selected_servo], cur);
    }
  }
  // 4. CONTROL MODE BUTTONS (Y=153..196, X=4..146)
  else if (x >= 4 && x <= 48 && y >= 153 && y <= 196) {
    action_name = "MODE GESTURE";
    if (mode_btns[0]) lv_obj_add_state(mode_btns[0], LV_STATE_PRESSED);
    update_control_mode_ui(0);
  } else if (x >= 49 && x <= 95 && y >= 153 && y <= 196) {
    action_name = "MODE VOICE";
    if (mode_btns[1]) lv_obj_add_state(mode_btns[1], LV_STATE_PRESSED);
    update_control_mode_ui(1);
  } else if (x >= 96 && x <= 146 && y >= 153 && y <= 196) {
    action_name = "MODE JOYSTICK";
    if (mode_btns[2]) lv_obj_add_state(mode_btns[2], LV_STATE_PRESSED);
    update_control_mode_ui(2);
  }
  // 5. ARM ACTION BUTTONS (REST ARM / STOP)
  else if (x >= 154 && x <= 226 && y >= 153 && y <= 196) {
    action_name = "REST ARM";
    if (btn_rest) lv_obj_add_state(btn_rest, LV_STATE_PRESSED);
    Serial.println("[ARM CMD] REST ARM");
  } else if (x >= 228 && x <= 308 && y >= 153 && y <= 196) {
    action_name = "STOP";
    if (btn_stop) lv_obj_add_state(btn_stop, LV_STATE_PRESSED);
    Serial.println("[ARM CMD] STOP");
  }
  // 6. BOTTOM NAVIGATION BUTTONS (CAMERA | ROVER | ASSISTANT)
  else if (x >= 0 && x <= 104 && y >= 199 && y <= 239) {
    action_name = "CAMERA";
    if (action_btn_objs[0]) lv_obj_add_state(action_btn_objs[0], LV_STATE_PRESSED);
    Serial.println("[ARM UI] Navigating to CAMERA APP");
    ui_switch_to(SCREEN_CAMERA);
  } else if (x >= 105 && x <= 208 && y >= 199 && y <= 239) {
    action_name = "ROVER";
    if (action_btn_objs[1]) lv_obj_add_state(action_btn_objs[1], LV_STATE_PRESSED);
    Serial.println("[ARM UI] Navigating to ROVER APP");
    ui_switch_to(SCREEN_ROVER);
  } else if (x >= 209 && x <= 319 && y >= 199 && y <= 239) {
    action_name = "ASSISTANT";
    if (action_btn_objs[2]) lv_obj_add_state(action_btn_objs[2], LV_STATE_PRESSED);
    Serial.println("[ARM UI] Navigating to ASSISTANT APP");
    ui_switch_to(SCREEN_ASSISTANT);
  }

  if (action_name) {
    last_touch_cmd_ms = now;
    Serial.printf("[ARM TOUCH] x=%d y=%d -> %s\n", x, y, action_name);
  }
}

static void arm_screen_touch_cb(lv_event_t *e) {
  lv_event_code_t code = lv_event_get_code(e);
  if (code == LV_EVENT_PRESSED) {
    lv_indev_t *indev = lv_indev_get_act();
    if (indev) {
      lv_point_t point;
      lv_indev_get_point(indev, &point);
      process_arm_touch_point(point.x, point.y);
    }
  } else if (code == LV_EVENT_RELEASED) {
    if (btn_back) lv_obj_clear_state(btn_back, LV_STATE_PRESSED);
    for (int i = 0; i < 3; i++) {
      if (mode_btns[i]) lv_obj_clear_state(mode_btns[i], LV_STATE_PRESSED);
      if (action_btn_objs[i]) lv_obj_clear_state(action_btn_objs[i], LV_STATE_PRESSED);
    }
    for (int i = 0; i < 7; i++) {
      if (servo_btns[i]) lv_obj_clear_state(servo_btns[i], LV_STATE_PRESSED);
    }
    if (btn_minus) lv_obj_clear_state(btn_minus, LV_STATE_PRESSED);
    if (btn_plus) lv_obj_clear_state(btn_plus, LV_STATE_PRESSED);
    if (btn_rest) lv_obj_clear_state(btn_rest, LV_STATE_PRESSED);
    if (btn_stop) lv_obj_clear_state(btn_stop, LV_STATE_PRESSED);
  }
}

static void select_servo(uint8_t index) {
  if (index >= 7) return;
  arm_state.selected_servo = index;

  for (int k = 0; k < 7; k++) {
    if (servo_btns[k] == NULL) continue;
    if (k == index) {
      lv_obj_set_style_bg_color(servo_btns[k], lv_color_hex(0x2563EB), LV_PART_MAIN);
      if (servo_btn_labels[k]) {
        lv_obj_set_style_text_color(servo_btn_labels[k], lv_color_white(), LV_PART_MAIN);
      }
    } else {
      lv_obj_set_style_bg_color(servo_btns[k], lv_color_hex(0xF1F5F9), LV_PART_MAIN);
      if (servo_btn_labels[k]) {
        lv_obj_set_style_text_color(servo_btn_labels[k], lv_color_hex(0x0F172A), LV_PART_MAIN);
      }
    }
  }

  if (lbl_ctrl_title) {
    char buf[32];
    snprintf(buf, sizeof(buf), "%s CONTROL", servo_names[index]);
    lv_label_set_text(lbl_ctrl_title, buf);
  }

  if (lbl_ctrl_angle) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%d°", arm_state.servo_angles[index]);
    lv_label_set_text(lbl_ctrl_angle, buf);
  }

  update_servo_status_ui();
  Serial.printf("[ARM] Selected Servo: %s (%d°)\n", servo_names[index], arm_state.servo_angles[index]);
}

static void update_servo_status_ui() {
  for (int i = 0; i < 7; i++) {
    if (lbl_servo_angles[i]) {
      char buf[16];
      snprintf(buf, sizeof(buf), "%d°", arm_state.servo_angles[i]);
      lv_label_set_text(lbl_servo_angles[i], buf);
    }
  }
}

static void update_control_mode_ui(uint8_t mode) {
  if (mode >= 3) return;
  arm_state.control_mode = mode;
  const lv_img_dsc_t *white_icons[3] = {&gesture_white_icon, &voice_white_icon, &joystick_white_icon};
  const lv_img_dsc_t *black_icons[3] = {&gesture_black_icon, &voice_black_icon, &joystick_black_icon};
  const char *mode_names[3] = {"GESTURE", "VOICE", "JOYSTICK"};

  for (int i = 0; i < 3; i++) {
    if (mode_btns[i] == NULL || mode_icons[i] == NULL) continue;
    if (i == mode) {
      lv_obj_set_style_bg_color(mode_btns[i], lv_color_hex(0x2563EB), LV_PART_MAIN);
      lv_img_set_src(mode_icons[i], white_icons[i]);
    } else {
      lv_obj_set_style_bg_color(mode_btns[i], lv_color_hex(0xF1F5F9), LV_PART_MAIN);
      lv_img_set_src(mode_icons[i], black_icons[i]);
    }
    lv_img_set_zoom(mode_icons[i], 230);
  }
  Serial.printf("[ARM] Control Mode: %s\n", mode_names[mode]);
}

// Helper: Card Container Creator
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
  lv_obj_clear_flag(card, LV_OBJ_FLAG_CLICKABLE);
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

// Helper: Rover Status Dot Indicator Row (No text, Dot ONLY)
static void create_status_dot_indicator_row(lv_obj_t *parent, int y, const char *name, uint8_t color_state) {
  lv_obj_t *lbl_name = lv_label_create(parent);
  lv_label_set_text(lbl_name, name);
  lv_obj_set_style_text_font(lbl_name, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_name, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_name, 2, y);

  lv_obj_t *dot = lv_obj_create(parent);
  lv_obj_set_size(dot, 6, 6);
  lv_obj_set_pos(dot, 68, y + 3);
  lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);

  lv_color_t dot_color;
  if (color_state == 0) {
    dot_color = lv_color_hex(0x22C55E); // Green (ON / Normal / HIGH)
  } else if (color_state == 1) {
    dot_color = lv_color_hex(0xEAB308); // Yellow (Warning / MEDIUM)
  } else if (color_state == 2) {
    dot_color = lv_color_hex(0xEF4444); // Red (Alert / Fault / LOW / MUTE)
  } else {
    dot_color = lv_color_hex(0x94A3B8); // Gray (OFF / Inactive)
  }

  lv_obj_set_style_bg_color(dot, dot_color, LV_PART_MAIN);
  lv_obj_set_style_border_width(dot, 0, LV_PART_MAIN);
  lv_obj_clear_flag(dot, LV_OBJ_FLAG_CLICKABLE);
}

// Helper: Rover Status Text Row (For Speed Display)
static void create_status_text_row(lv_obj_t *parent, int y, const char *name, const char *val_str) {
  lv_obj_t *lbl_name = lv_label_create(parent);
  lv_label_set_text(lbl_name, name);
  lv_obj_set_style_text_font(lbl_name, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_name, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_name, 2, y);

  lv_obj_t *lbl_val = lv_label_create(parent);
  lv_label_set_text(lbl_val, val_str);
  lv_obj_set_style_text_font(lbl_val, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_val, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_pos(lbl_val, 40, y);
}

lv_obj_t *ui_arm_create() {
  // 1. Base Screen Container (320x240 - Pure White Background, ABSOLUTELY NO SCROLLING)
  lv_obj_t *scr = lv_obj_create(NULL);
  lv_obj_set_style_bg_color(scr, lv_color_white(), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_pad_all(scr, 0, LV_PART_MAIN);
  lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

  // Register Unified Screen Touch Event Handler
  lv_obj_add_event_cb(scr, arm_screen_touch_cb, LV_EVENT_ALL, NULL);

  // 2. Main Glass Panel Container (312x232 at X=4, Y=4 - Pure White Surface)
  lv_obj_t *glass_panel = lv_obj_create(scr);
  lv_obj_set_size(glass_panel, 312, 232);
  lv_obj_set_pos(glass_panel, 4, 4);
  lv_obj_set_style_bg_color(glass_panel, lv_color_white(), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(glass_panel, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_radius(glass_panel, 12, LV_PART_MAIN);
  lv_obj_set_style_border_width(glass_panel, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(glass_panel, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
  lv_obj_set_style_shadow_width(glass_panel, 6, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(glass_panel, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(glass_panel, (lv_opa_t)20, LV_PART_MAIN);
  lv_obj_set_style_pad_all(glass_panel, 0, LV_PART_MAIN);
  lv_obj_clear_flag(glass_panel, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(glass_panel, LV_OBJ_FLAG_CLICKABLE);

  // 3. Compact Header Navigation Bar (Y=2..24)
  // 3a. Back to App Drawer Button (< APPS)
  btn_back = lv_btn_create(glass_panel);
  lv_obj_set_pos(btn_back, 4, 2);
  lv_obj_set_size(btn_back, 54, 22);
  lv_obj_set_style_bg_color(btn_back, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn_back, lv_color_hex(0xE2E8F0), LV_STATE_PRESSED);
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

  // 3b. Screen Title (ROBOTIC ARM)
  lv_obj_t *lbl_title = lv_label_create(glass_panel);
  lv_label_set_text(lbl_title, "ROBOTIC ARM");
  lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_pos(lbl_title, 72, 5);

  // 3c. Wi-Fi Status Indicator
  lv_obj_t *wifi_dot = lv_obj_create(glass_panel);
  lv_obj_set_size(wifi_dot, 6, 6);
  lv_obj_set_pos(wifi_dot, 205, 9);
  lv_obj_set_style_radius(wifi_dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(wifi_dot, lv_color_hex(0x22C55E), LV_PART_MAIN);
  lv_obj_set_style_border_width(wifi_dot, 0, LV_PART_MAIN);
  lv_obj_clear_flag(wifi_dot, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_wifi = lv_label_create(glass_panel);
  lv_label_set_text(lbl_wifi, "CONNECTED");
  lv_obj_set_style_text_font(lbl_wifi, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_wifi, lv_color_hex(0x475569), LV_PART_MAIN);
  lv_obj_set_pos(lbl_wifi, 215, 5);

  // 4. MAIN CONTENT GRID (Y = 26..150)
  // COLUMN 1: ROVER STATUS (Left: X=4, W=86, H=124)
  lv_obj_t *card_status = create_card(glass_panel, 4, 26, 86, 124);
  create_card_title(card_status, "ROVER STATUS");

  // 1. Headlight (Dot ONLY: Green=ON, Gray=OFF, Red=Fault)
  bool hl_on = ui_rover_get_headlight();
  create_status_dot_indicator_row(card_status, 18, "HEADLIGHT", hl_on ? 0 : 3);

  // 2. Speed (Text: 0.0 m/s)
  char speed_buf[16];
  snprintf(speed_buf, sizeof(speed_buf), "%.1f m/s", ui_rover_get_speed());
  create_status_text_row(card_status, 42, "SPEED", speed_buf);

  // 3. Fuse (Dot ONLY: Green=Normal/ON, Gray=OFF, Red=Alert)
  uint8_t fuse_st = ui_rover_get_fuse();
  uint8_t fuse_color = (fuse_st == 0) ? 0 : ((fuse_st == 1) ? 3 : 2);
  create_status_dot_indicator_row(card_status, 66, "FUSE", fuse_color);

  // 4. Speaker (Dot ONLY: Red=LOW/MUTE, Yellow=MEDIUM, Green=HIGH)
  uint8_t spk_lvl = ui_rover_get_speaker_level();
  uint8_t spk_color;
  if (spk_lvl == 3) spk_color = 0;      // HIGH -> Green
  else if (spk_lvl == 2) spk_color = 1; // MEDIUM -> Yellow
  else spk_color = 2;                   // LOW / MUTE -> Red
  create_status_dot_indicator_row(card_status, 90, "SPEAKER", spk_color);

  // COLUMN 2: SELECT SERVO & CONTROL (Center Expanded: X=94, W=124, H=124)
  lv_obj_t *card_servo = create_card(glass_panel, 94, 26, 124, 124);
  create_card_title(card_servo, "SELECT SERVO");

  // 7 Servo Selector Buttons (Expanded width: 57px each)
  struct ServoBtnPos {
    int x;
    int y;
    int w;
    int h;
  } s_pos[7] = {
    {3, 14, 57, 15},  // ARM_A1
    {64, 14, 57, 15}, // ARM_A2
    {3, 31, 57, 15},  // ARM_B
    {64, 31, 57, 15}, // GRIPPER
    {3, 48, 57, 15},  // ROOT
    {64, 48, 57, 15}, // WRIST_A
    {3, 65, 57, 15}   // WRIST_B
  };

  for (int i = 0; i < 7; i++) {
    servo_btns[i] = lv_btn_create(card_servo);
    lv_obj_set_pos(servo_btns[i], s_pos[i].x, s_pos[i].y);
    lv_obj_set_size(servo_btns[i], s_pos[i].w, s_pos[i].h);
    lv_obj_set_style_radius(servo_btns[i], 3, LV_PART_MAIN);
    lv_obj_set_style_border_width(servo_btns[i], 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(servo_btns[i], lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_bg_color(servo_btns[i], lv_color_hex(0x1D4ED8), LV_STATE_PRESSED);
    lv_obj_set_style_pad_all(servo_btns[i], 0, LV_PART_MAIN);
    lv_obj_set_ext_click_area(servo_btns[i], 0);
    lv_obj_clear_flag(servo_btns[i], LV_OBJ_FLAG_CLICKABLE);

    servo_btn_labels[i] = lv_label_create(servo_btns[i]);
    lv_label_set_text(servo_btn_labels[i], servo_names[i]);
    lv_obj_set_style_text_font(servo_btn_labels[i], &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_center(servo_btn_labels[i]);
  }

  // Divider / Control Sub-Header Area
  lbl_ctrl_title = lv_label_create(card_servo);
  lv_obj_set_pos(lbl_ctrl_title, 2, 83);
  lv_obj_set_style_text_font(lbl_ctrl_title, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_ctrl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);

  // Minus Button (-) - Expanded Touch Target (32x22)
  btn_minus = lv_btn_create(card_servo);
  lv_obj_set_pos(btn_minus, 4, 96);
  lv_obj_set_size(btn_minus, 32, 22);
  lv_obj_set_style_bg_color(btn_minus, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn_minus, lv_color_hex(0xCBD5E1), LV_STATE_PRESSED);
  lv_obj_set_style_radius(btn_minus, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(btn_minus, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(btn_minus, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_minus, 0, LV_PART_MAIN);
  lv_obj_clear_flag(btn_minus, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_m = lv_label_create(btn_minus);
  lv_label_set_text(lbl_m, "-");
  lv_obj_set_style_text_font(lbl_m, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_m, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_center(lbl_m);

  // Angle Display
  lbl_ctrl_angle = lv_label_create(card_servo);
  lv_obj_set_pos(lbl_ctrl_angle, 40, 98);
  lv_obj_set_size(lbl_ctrl_angle, 44, 18);
  lv_obj_set_style_text_font(lbl_ctrl_angle, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_ctrl_angle, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_set_style_text_align(lbl_ctrl_angle, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);

  // Plus Button (+) - Expanded Touch Target (32x22)
  btn_plus = lv_btn_create(card_servo);
  lv_obj_set_pos(btn_plus, 88, 96);
  lv_obj_set_size(btn_plus, 32, 22);
  lv_obj_set_style_bg_color(btn_plus, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn_plus, lv_color_hex(0xCBD5E1), LV_STATE_PRESSED);
  lv_obj_set_style_radius(btn_plus, 4, LV_PART_MAIN);
  lv_obj_set_style_border_width(btn_plus, 1, LV_PART_MAIN);
  lv_obj_set_style_border_color(btn_plus, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_plus, 0, LV_PART_MAIN);
  lv_obj_clear_flag(btn_plus, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_p = lv_label_create(btn_plus);
  lv_label_set_text(lbl_p, "+");
  lv_obj_set_style_text_font(lbl_p, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_p, lv_color_hex(0x0F172A), LV_PART_MAIN);
  lv_obj_center(lbl_p);

  // COLUMN 3: SERVO STATUS (Right: X=222, W=86, H=124)
  lv_obj_t *card_servo_stat = create_card(glass_panel, 222, 26, 86, 124);
  create_card_title(card_servo_stat, "SERVO STATUS");

  for (int i = 0; i < 7; i++) {
    int y_pos = 14 + (i * 15);
    lv_obj_t *lbl_name = lv_label_create(card_servo_stat);
    lv_label_set_text(lbl_name, servo_names[i]);
    lv_obj_set_style_text_font(lbl_name, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_name, lv_color_hex(0x475569), LV_PART_MAIN);
    lv_obj_set_pos(lbl_name, 2, y_pos);

    lbl_servo_angles[i] = lv_label_create(card_servo_stat);
    lv_obj_set_style_text_font(lbl_servo_angles[i], &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_servo_angles[i], lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_pos(lbl_servo_angles[i], 48, y_pos);

    lv_obj_t *dot = lv_obj_create(card_servo_stat);
    lv_obj_set_size(dot, 5, 5);
    lv_obj_set_pos(dot, 74, y_pos + 3);
    lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(dot, lv_color_hex(0x22C55E), LV_PART_MAIN); // Green OK
    lv_obj_set_style_border_width(dot, 0, LV_PART_MAIN);
    lv_obj_clear_flag(dot, LV_OBJ_FLAG_CLICKABLE);
  }

  // 5. CONTROL MODE & ACTION ROW (Y = 153..196)
  // LEFT: CONTROL MODE (X=4, W=146, H=43)
  Serial.println("[ARM DEBUG 3] Before Control Mode Card");
  lv_obj_t *card_mode = create_card(glass_panel, 4, 153, 146, 43);
  create_card_title(card_mode, "CONTROL MODE");

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

    mode_icons[i] = lv_img_create(mode_btns[i]);
  }
  Serial.println("[ARM DEBUG 4] After Control Mode Card");

  // RIGHT: ACTIONS (X=154, W=154, H=43) - [ REST ARM ] [ STOP ]
  Serial.println("[ARM DEBUG 5] Before Arm Actions");
  lv_obj_t *card_act = create_card(glass_panel, 154, 153, 154, 43);
  create_card_title(card_act, "ARM ACTIONS");

  btn_rest = lv_btn_create(card_act);
  lv_obj_set_pos(btn_rest, 4, 13);
  lv_obj_set_size(btn_rest, 70, 24);
  lv_obj_set_style_bg_color(btn_rest, lv_color_hex(0x2563EB), LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn_rest, lv_color_hex(0x1D4ED8), LV_STATE_PRESSED);
  lv_obj_set_style_radius(btn_rest, 5, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_rest, 0, LV_PART_MAIN);
  lv_obj_set_ext_click_area(btn_rest, 0);
  lv_obj_clear_flag(btn_rest, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_rest = lv_label_create(btn_rest);
  lv_label_set_text(lbl_rest, "REST ARM");
  lv_obj_set_style_text_font(lbl_rest, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_rest, lv_color_white(), LV_PART_MAIN);
  lv_obj_center(lbl_rest);

  btn_stop = lv_btn_create(card_act);
  lv_obj_set_pos(btn_stop, 78, 13);
  lv_obj_set_size(btn_stop, 70, 24);
  lv_obj_set_style_bg_color(btn_stop, lv_color_hex(0xEF4444), LV_PART_MAIN);
  lv_obj_set_style_bg_color(btn_stop, lv_color_hex(0xB91C1C), LV_STATE_PRESSED);
  lv_obj_set_style_radius(btn_stop, 5, LV_PART_MAIN);
  lv_obj_set_style_pad_all(btn_stop, 0, LV_PART_MAIN);
  lv_obj_set_ext_click_area(btn_stop, 0);
  lv_obj_clear_flag(btn_stop, LV_OBJ_FLAG_CLICKABLE);

  lv_obj_t *lbl_stop = lv_label_create(btn_stop);
  lv_label_set_text(lbl_stop, "STOP");
  lv_obj_set_style_text_font(lbl_stop, &lv_font_montserrat_10, LV_PART_MAIN);
  lv_obj_set_style_text_color(lbl_stop, lv_color_white(), LV_PART_MAIN);
  lv_obj_center(lbl_stop);
  Serial.println("[ARM DEBUG 6] After Arm Actions");

  // 6. BOTTOM ACTION BUTTONS (Y = 199..225)
  Serial.println("[ARM DEBUG 7] Before Bottom Nav");
  struct ActionBtn {
    const char *label;
    const lv_img_dsc_t *icon;
    int x;
  } action_btns[3] = {{"CAMERA",    &camera_icon,    4},
                      {"ROVER",     &rover_icon,     108},
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
    }
  }

  // 7. INITIALIZE DYNAMIC UI STATES AFTER ALL OBJECTS EXIST
  Serial.println("[ARM DEBUG] Applying initial UI states...");
  select_servo(arm_state.selected_servo);
  update_control_mode_ui(arm_state.control_mode);

  for (int i = 0; i < 3; i++) {
    if (mode_icons[i]) {
      lv_obj_set_size(mode_icons[i], LV_SIZE_CONTENT, LV_SIZE_CONTENT);
      lv_obj_center(mode_icons[i]);
      lv_obj_clear_flag(mode_icons[i], LV_OBJ_FLAG_CLICKABLE);
    }
  }

  Serial.println("[ARM DEBUG 8] ui_arm_create COMPLETE");
  return scr;
}
