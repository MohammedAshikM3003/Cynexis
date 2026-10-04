#include "ui_assistant.h"
#include "ui.h"
#include <Arduino.h>
#include <cstdio>

// LVGL Asset Headers for Assistant Screen
#include "assets/arm_icon.h"
#include "assets/assistant_icon.h"
#include "assets/camera_icon.h"
#include "assets/keyboard_close_icon.h"
#include "assets/keyboard_icon.h"
#include "assets/rover_icon.h"
#include "assets/speaker_icon.h"
#include "assets/stop_icon.h"
#include "assets/trash_icon.h"
#include "assets/voice_white_icon.h"

// State structure for Assistant UI
struct AssistantState {
    bool voice_listening;
};

static AssistantState assistant_state = {
    .voice_listening = false
};

// UI Object Pointers for Dynamic State, Waveform, Keyboard, and Pressed Effects
static lv_obj_t *btn_bin = NULL;
static lv_obj_t *btn_voice_stop = NULL;
static lv_obj_t *img_voice_stop = NULL;
static lv_obj_t *btn_keyboard = NULL;
static lv_obj_t *btn_speaker = NULL;
static lv_obj_t *nav_btns[3] = {NULL, NULL, NULL}; // CAMERA, ROVER, ARM
static lv_obj_t *btn_apps_back = NULL;
static lv_obj_t *box_waveform = NULL;
static lv_obj_t *wave_bars[5] = {NULL, NULL, NULL, NULL, NULL};
static lv_timer_t *wave_timer = NULL;

// Keyboard overlay objects
static lv_obj_t *kb_overlay = NULL;
static lv_obj_t *ta_input = NULL;
static lv_obj_t *lv_kb = NULL;
static lv_obj_t *btn_kb_close = NULL;

static uint32_t last_touch_cmd_ms = 0;

static void wave_anim_cb(lv_timer_t *t) {
    if (!assistant_state.voice_listening) return;

    static const uint8_t heights[5][4] = {
        {3, 7, 11, 5},
        {6, 10, 4, 9},
        {10, 4, 12, 6},
        {4, 9, 5, 11},
        {7, 5, 9, 3}
    };
    static uint8_t step = 0;
    step = (step + 1) % 4;

    for (int i = 0; i < 5; i++) {
        if (wave_bars[i]) {
            int h = heights[i][step];
            lv_obj_set_size(wave_bars[i], 4, h);
            lv_obj_set_pos(wave_bars[i], 5 + i * 9, 7 - h / 2);
            lv_obj_set_style_bg_color(wave_bars[i], lv_color_hex(0xEF4444), LV_PART_MAIN);
        }
    }
}

static void update_voice_button_ui() {
    if (!btn_voice_stop || !img_voice_stop) return;

    if (assistant_state.voice_listening) {
        // Listening state: show STOP icon & RED background
        lv_img_set_src(img_voice_stop, &stop_icon);
        lv_obj_set_style_bg_color(btn_voice_stop, lv_color_hex(0xEF4444), LV_PART_MAIN);
        lv_obj_set_style_border_color(btn_voice_stop, lv_color_hex(0xDC2626), LV_PART_MAIN);

        // Activate Waveform Animation
        if (!wave_timer) {
            wave_timer = lv_timer_create(wave_anim_cb, 100, NULL);
        } else {
            lv_timer_resume(wave_timer);
        }
    } else {
        // Idle state: show VOICE icon & BLUE background
        lv_img_set_src(img_voice_stop, &voice_white_icon);
        lv_obj_set_style_bg_color(btn_voice_stop, lv_color_hex(0x2563EB), LV_PART_MAIN);
        lv_obj_set_style_border_color(btn_voice_stop, lv_color_hex(0x1D4ED8), LV_PART_MAIN);

        // Reset Waveform Bars to Flat Idle State
        if (wave_timer) {
            lv_timer_pause(wave_timer);
        }
        for (int i = 0; i < 5; i++) {
            if (wave_bars[i]) {
                lv_obj_set_size(wave_bars[i], 4, 3);
                lv_obj_set_pos(wave_bars[i], 5 + i * 9, 5);
                lv_obj_set_style_bg_color(wave_bars[i], lv_color_hex(0xCBD5E1), LV_PART_MAIN);
            }
        }
    }
    lv_obj_invalidate(btn_voice_stop);
}

static void show_keyboard_ui(bool show) {
    if (!kb_overlay) return;
    if (show) {
        lv_obj_clear_flag(kb_overlay, LV_OBJ_FLAG_HIDDEN);
        if (ta_input) {
            lv_textarea_set_text(ta_input, "");
        }
        Serial.println("[ASSISTANT UI] Keyboard opened");
    } else {
        lv_obj_add_flag(kb_overlay, LV_OBJ_FLAG_HIDDEN);
        Serial.println("[ASSISTANT UI] Keyboard closed");
    }
}

static void process_assistant_touch_point(int16_t x, int16_t y) {
    uint32_t now = millis();
    if (now - last_touch_cmd_ms < 100) { // 100ms touch debounce guard
        return;
    }

    const char *action_name = NULL;

    // Check if Keyboard Overlay is visible and handle close button touch & touch priority
    if (kb_overlay && !lv_obj_has_flag(kb_overlay, LV_OBJ_FLAG_HIDDEN)) {
        if (x >= 260 && x <= 319 && y >= 54 && y <= 93) {
            action_name = "Keyboard CLOSE";
            if (btn_kb_close) lv_obj_add_state(btn_kb_close, LV_STATE_PRESSED);
            show_keyboard_ui(false);
            last_touch_cmd_ms = now;
            Serial.printf("[ASSISTANT TOUCH] x=%d y=%d -> %s\n", x, y, action_name);
            return;
        }
        // Prevent touches from reaching underlying navigation buttons while keyboard is open
        if (y >= 54) {
            return;
        }
    }

    // 1. BACK TO APPS (< APPS)
    if (x >= 4 && x <= 62 && y >= 2 && y <= 30) {
        action_name = "APPS";
        if (btn_apps_back) lv_obj_add_state(btn_apps_back, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to APP DRAWER");
        ui_switch_to(SCREEN_APPS);
    }
    // 2. SPEAKER BUTTON INSIDE CHAT
    else if (x >= 210 && x <= 260 && y >= 110 && y <= 150) {
        action_name = "SPEAKER";
        if (btn_speaker) lv_obj_add_state(btn_speaker, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Speaker tapped");
    }
    // 3. LEFT BUTTON (BIN / CLEAR CHAT)
    else if (x >= 4 && x <= 100 && y >= 165 && y <= 198) {
        action_name = "BIN / CLEAR CHAT";
        if (btn_bin) lv_obj_add_state(btn_bin, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Clear chat tapped");
    }
    // 4. CENTER BUTTON (MICROPHONE / STOP TOGGLE)
    else if (x >= 104 && x <= 204 && y >= 150 && y <= 196) {
        action_name = "MICROPHONE/STOP";
        if (btn_voice_stop) lv_obj_add_state(btn_voice_stop, LV_STATE_PRESSED);
        assistant_state.voice_listening = !assistant_state.voice_listening;
        update_voice_button_ui();
        if (assistant_state.voice_listening) {
            Serial.println("[ASSISTANT UI] Voice listening START");
        } else {
            Serial.println("[ASSISTANT UI] Voice listening STOP");
        }
    }
    // 5. RIGHT BUTTON (KEYBOARD)
    else if (x >= 208 && x <= 316 && y >= 150 && y <= 196) {
        action_name = "KEYBOARD";
        if (btn_keyboard) lv_obj_add_state(btn_keyboard, LV_STATE_PRESSED);
        show_keyboard_ui(true);
    }
    // 6. BOTTOM NAVIGATION - CAMERA (Matches Rover CAMERA hitbox exactly)
    else if (x >= 0 && x <= 105 && y >= 214 && y <= 239) {
        action_name = "CAMERA";
        if (nav_btns[0]) lv_obj_add_state(nav_btns[0], LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to CAMERA");
        ui_switch_to(SCREEN_CAMERA);
    }
    // 7. BOTTOM NAVIGATION - ROVER (Matches Rover Center hitbox exactly)
    else if (x >= 120 && x <= 245 && y >= 214 && y <= 239) {
        action_name = "ROVER";
        if (nav_btns[1]) lv_obj_add_state(nav_btns[1], LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to ROVER");
        ui_switch_to(SCREEN_ROVER);
    }
    // 8. BOTTOM NAVIGATION - ARM (Matches Rover ASSISTANT/Right hitbox exactly)
    else if (x >= 255 && x <= 319 && y >= 214 && y <= 239) {
        action_name = "ARM";
        if (nav_btns[2]) lv_obj_add_state(nav_btns[2], LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to ARM");
        ui_switch_to(SCREEN_ARM);
    }

    if (action_name) {
        last_touch_cmd_ms = now;
        Serial.printf("[ASSISTANT TOUCH] x=%d y=%d -> %s\n", x, y, action_name);
    }
}

static void assistant_screen_touch_cb(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_PRESSED || code == LV_EVENT_PRESSING) {
        lv_indev_t *indev = lv_indev_get_act();
        if (indev) {
            lv_point_t point;
            lv_indev_get_point(indev, &point);

            // Local Y-transformation ONLY when keyboard overlay is visible and touch is in keyboard area
            if (kb_overlay && !lv_obj_has_flag(kb_overlay, LV_OBJ_FLAG_HIDDEN)) {
                // Ignore keyboard close button (x:260..319, y:54..93)
                if (!(point.x >= 260 && point.x <= 319 && point.y >= 54 && point.y <= 93)) {
                    if (point.y >= 125 && point.y <= 235) {
                        int16_t mapped_y = 94 + (int16_t)(((int32_t)(point.y - 130) * 130) / 98);
                        if (mapped_y < 94) mapped_y = 94;
                        if (mapped_y > 228) mapped_y = 228;
                        indev->proc.types.pointer.act_point.y = mapped_y;
                    }
                }
            }

            if (code == LV_EVENT_PRESSED) {
                process_assistant_touch_point(point.x, point.y);
            }
        }
    } else if (code == LV_EVENT_RELEASED) {
        if (btn_apps_back) lv_obj_clear_state(btn_apps_back, LV_STATE_PRESSED);
        if (btn_speaker) lv_obj_clear_state(btn_speaker, LV_STATE_PRESSED);
        if (btn_bin) lv_obj_clear_state(btn_bin, LV_STATE_PRESSED);
        if (btn_voice_stop) lv_obj_clear_state(btn_voice_stop, LV_STATE_PRESSED);
        if (btn_keyboard) lv_obj_clear_state(btn_keyboard, LV_STATE_PRESSED);
        if (btn_kb_close) lv_obj_clear_state(btn_kb_close, LV_STATE_PRESSED);
        for (int i = 0; i < 3; i++) {
            if (nav_btns[i]) lv_obj_clear_state(nav_btns[i], LV_STATE_PRESSED);
        }
    }
}

// Helper: Card Container Creator matching Rover style
static lv_obj_t *create_card(lv_obj_t *parent, int x, int y, int w, int h) {
    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_set_pos(card, x, y);
    lv_obj_set_size(card, w, h);
    lv_obj_set_style_bg_color(card, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(card, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(card, lv_color_hex(0xE2E8F0), LV_PART_MAIN);

    // Subtle Box Shadow
    lv_obj_set_style_shadow_width(card, 4, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(card, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(card, (lv_opa_t)20, LV_PART_MAIN);

    lv_obj_set_style_pad_all(card, 3, LV_PART_MAIN);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_CLICKABLE);
    return card;
}

lv_obj_t *ui_assistant_create() {
    // 1. Root Screen Setup
    lv_obj_t *scr = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    // Attach screen-level touch router callback
    lv_obj_add_event_cb(scr, assistant_screen_touch_cb, LV_EVENT_ALL, NULL);

    // 2. Main Glass Panel (312x232 at 4,4) matching Rover
    lv_obj_t *glass = lv_obj_create(scr);
    lv_obj_set_pos(glass, 4, 4);
    lv_obj_set_size(glass, 312, 232);
    lv_obj_set_style_bg_color(glass, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(glass, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(glass, 12, LV_PART_MAIN);
    lv_obj_set_style_border_width(glass, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(glass, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(glass, 6, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(glass, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(glass, (lv_opa_t)25, LV_PART_MAIN);
    lv_obj_set_style_pad_all(glass, 0, LV_PART_MAIN);
    lv_obj_clear_flag(glass, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(glass, LV_OBJ_FLAG_CLICKABLE);

    // 3. Header Setup
    // Back Button (< APPS) matching Rover App exact geometry & styling
    btn_apps_back = lv_btn_create(glass);
    lv_obj_set_pos(btn_apps_back, 4, 2);
    lv_obj_set_size(btn_apps_back, 54, 22);
    lv_obj_set_style_bg_color(btn_apps_back, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(btn_apps_back, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(btn_apps_back, 5, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_apps_back, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_apps_back, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn_apps_back, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(btn_apps_back, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn_apps_back, LV_OPA_20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_apps_back, 0, LV_PART_MAIN);
    lv_obj_set_ext_click_area(btn_apps_back, 0);
    lv_obj_clear_flag(btn_apps_back, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *lbl_back = lv_label_create(btn_apps_back);
    lv_label_set_text(lbl_back, "< APPS");
    lv_obj_set_style_text_font(lbl_back, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_back, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_center(lbl_back);

    // Header Title (ASSISTANT)
    lv_obj_t *lbl_title = lv_label_create(glass);
    lv_label_set_text(lbl_title, "ASSISTANT");
    lv_obj_set_style_text_color(lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_title, 115, 6);

    // Wi-Fi Status Indicator
    lv_obj_t *dot_wifi = lv_obj_create(glass);
    lv_obj_set_pos(dot_wifi, 222, 10);
    lv_obj_set_size(dot_wifi, 6, 6);
    lv_obj_set_style_bg_color(dot_wifi, lv_color_hex(0x22C55E), LV_PART_MAIN);
    lv_obj_set_style_radius(dot_wifi, 3, LV_PART_MAIN);
    lv_obj_set_style_border_width(dot_wifi, 0, LV_PART_MAIN);
    lv_obj_clear_flag(dot_wifi, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl_wifi = lv_label_create(glass);
    lv_label_set_text(lbl_wifi, "CONNECTED");
    lv_obj_set_style_text_color(lbl_wifi, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_wifi, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_wifi, 232, 6);

    // 4. Conversation Card Container
    lv_obj_t *conv_card = create_card(glass, 4, 26, 304, 124);
    lv_obj_set_style_pad_all(conv_card, 4, LV_PART_MAIN);
    lv_obj_add_flag(conv_card, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_flag(conv_card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(conv_card, LV_OBJ_FLAG_SCROLL_MOMENTUM);
    lv_obj_add_flag(conv_card, LV_OBJ_FLAG_SCROLL_ELASTIC);
    lv_obj_clear_flag(conv_card, LV_OBJ_FLAG_SCROLL_CHAIN);
    lv_obj_set_scroll_dir(conv_card, LV_DIR_VER); // Vertical scrolling ONLY
    lv_obj_set_scrollbar_mode(conv_card, LV_SCROLLBAR_MODE_AUTO);
    lv_obj_set_style_width(conv_card, 4, LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_color(conv_card, lv_color_hex(0x2563EB), LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_opa(conv_card, LV_OPA_COVER, LV_PART_SCROLLBAR);
    lv_obj_set_style_radius(conv_card, 2, LV_PART_SCROLLBAR);

    // Robot Icon on the LEFT
    lv_obj_t *img_bot = lv_img_create(conv_card);
    lv_img_set_src(img_bot, &assistant_icon);
    lv_img_set_zoom(img_bot, 220);
    lv_obj_set_pos(img_bot, 4, 4);

    // Prompt Header Text on the RIGHT of logo
    lv_obj_t *lbl_prompt_title = lv_label_create(conv_card);
    lv_label_set_text(lbl_prompt_title, "How can I help ?");
    lv_obj_set_style_text_color(lbl_prompt_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_prompt_title, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_prompt_title, 38, 2);

    // Live Voice Waveform Box immediately to the RIGHT of "How can I help ?"
    box_waveform = lv_obj_create(conv_card);
    lv_obj_set_pos(box_waveform, 162, 2);
    lv_obj_set_size(box_waveform, 54, 14);
    lv_obj_set_style_bg_color(box_waveform, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_radius(box_waveform, 4, LV_PART_MAIN);
    lv_obj_set_style_border_width(box_waveform, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(box_waveform, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_pad_all(box_waveform, 0, LV_PART_MAIN);
    lv_obj_clear_flag(box_waveform, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(box_waveform, LV_OBJ_FLAG_CLICKABLE);

    for (int i = 0; i < 5; i++) {
        wave_bars[i] = lv_obj_create(box_waveform);
        lv_obj_set_pos(wave_bars[i], 5 + i * 9, 5);
        lv_obj_set_size(wave_bars[i], 4, 4);
        lv_obj_set_style_bg_color(wave_bars[i], lv_color_hex(0xCBD5E1), LV_PART_MAIN);
        lv_obj_set_style_radius(wave_bars[i], 2, LV_PART_MAIN);
        lv_obj_set_style_border_width(wave_bars[i], 0, LV_PART_MAIN);
        lv_obj_clear_flag(wave_bars[i], LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(wave_bars[i], LV_OBJ_FLAG_CLICKABLE);
    }

    lv_obj_t *lbl_prompt_sub1 = lv_label_create(conv_card);
    lv_label_set_text(lbl_prompt_sub1, "Tap the microphone to speak /");
    lv_obj_set_style_text_color(lbl_prompt_sub1, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_prompt_sub1, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_prompt_sub1, 38, 18);

    lv_obj_t *lbl_prompt_sub2 = lv_label_create(conv_card);
    lv_label_set_text(lbl_prompt_sub2, "keyboard to type");
    lv_obj_set_style_text_color(lbl_prompt_sub2, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_prompt_sub2, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_prompt_sub2, 38, 30);

    // Chat Message 1: User Message Bubble
    lv_obj_t *msg_user = lv_obj_create(conv_card);
    lv_obj_set_pos(msg_user, 4, 48);
    lv_obj_set_size(msg_user, 272, 38);
    lv_obj_set_style_bg_color(msg_user, lv_color_hex(0xEFF6FF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(msg_user, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(msg_user, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(msg_user, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(msg_user, lv_color_hex(0xBFDBFE), LV_PART_MAIN);
    lv_obj_set_style_pad_all(msg_user, 3, LV_PART_MAIN);
    lv_obj_clear_flag(msg_user, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(msg_user, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *lbl_u_title = lv_label_create(msg_user);
    lv_label_set_text(lbl_u_title, "You:");
    lv_obj_set_style_text_color(lbl_u_title, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u_title, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_u_title, 4, 2);

    lv_obj_t *lbl_u_body = lv_label_create(msg_user);
    lv_label_set_text(lbl_u_body, "Move the rover forward");
    lv_obj_set_style_text_color(lbl_u_body, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u_body, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_label_set_long_mode(lbl_u_body, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(lbl_u_body, 200);
    lv_obj_set_pos(lbl_u_body, 4, 16);

    lv_obj_t *lbl_u_time = lv_label_create(msg_user);
    lv_label_set_text(lbl_u_time, "14:25");
    lv_obj_set_style_text_color(lbl_u_time, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u_time, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_u_time, 234, 16);

    // Chat Message 2: Assistant Message Bubble
    lv_obj_t *msg_ast = lv_obj_create(conv_card);
    lv_obj_set_pos(msg_ast, 4, 90);
    lv_obj_set_size(msg_ast, 272, 38);
    lv_obj_set_style_bg_color(msg_ast, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(msg_ast, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(msg_ast, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(msg_ast, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(msg_ast, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_pad_all(msg_ast, 3, LV_PART_MAIN);
    lv_obj_clear_flag(msg_ast, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(msg_ast, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *lbl_a_title = lv_label_create(msg_ast);
    lv_label_set_text(lbl_a_title, "Assistant:");
    lv_obj_set_style_text_color(lbl_a_title, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_a_title, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_a_title, 4, 2);

    lv_obj_t *lbl_a_body = lv_label_create(msg_ast);
    lv_label_set_text(lbl_a_body, "Rover moving forward.");
    lv_obj_set_style_text_color(lbl_a_body, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_a_body, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_label_set_long_mode(lbl_a_body, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(lbl_a_body, 190);
    lv_obj_set_pos(lbl_a_body, 4, 16);

    // Speaker Button inside Assistant response
    btn_speaker = lv_obj_create(msg_ast);
    lv_obj_set_pos(btn_speaker, 210, 12);
    lv_obj_set_size(btn_speaker, 20, 20);
    lv_obj_set_style_bg_color(btn_speaker, lv_color_hex(0xEFF6FF), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_speaker, 4, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_speaker, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_speaker, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_speaker, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_speaker, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *img_spk = lv_img_create(btn_speaker);
    lv_img_set_src(img_spk, &speaker_icon);
    lv_img_set_zoom(img_spk, 200);
    lv_obj_center(img_spk);

    lv_obj_t *lbl_a_time = lv_label_create(msg_ast);
    lv_label_set_text(lbl_a_time, "14:25");
    lv_obj_set_style_text_color(lbl_a_time, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_a_time, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_a_time, 234, 16);

    // Chat Message 3: Extra message bubble to activate vertical scrolling
    lv_obj_t *msg_user2 = lv_obj_create(conv_card);
    lv_obj_set_pos(msg_user2, 4, 132);
    lv_obj_set_size(msg_user2, 272, 38);
    lv_obj_set_style_bg_color(msg_user2, lv_color_hex(0xEFF6FF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(msg_user2, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(msg_user2, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(msg_user2, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(msg_user2, lv_color_hex(0xBFDBFE), LV_PART_MAIN);
    lv_obj_set_style_pad_all(msg_user2, 3, LV_PART_MAIN);
    lv_obj_clear_flag(msg_user2, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(msg_user2, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *lbl_u2_title = lv_label_create(msg_user2);
    lv_label_set_text(lbl_u2_title, "You:");
    lv_obj_set_style_text_color(lbl_u2_title, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u2_title, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_u2_title, 4, 2);

    lv_obj_t *lbl_u2_body = lv_label_create(msg_user2);
    lv_label_set_text(lbl_u2_body, "Turn headlights ON");
    lv_obj_set_style_text_color(lbl_u2_body, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u2_body, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_label_set_long_mode(lbl_u2_body, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(lbl_u2_body, 200);
    lv_obj_set_pos(lbl_u2_body, 4, 16);

    lv_obj_t *lbl_u2_time = lv_label_create(msg_user2);
    lv_label_set_text(lbl_u2_time, "14:26");
    lv_obj_set_style_text_color(lbl_u2_time, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u2_time, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_u2_time, 234, 16);

    // 5. Bottom Assistant Control Row (3 Equal-Width Buttons: BIN | MICROPHONE | KEYBOARD)
    // Button 1: Left BIN / Trash Button (X=4, W=96, H=41)
    btn_bin = lv_obj_create(glass);
    lv_obj_set_pos(btn_bin, 4, 153);
    lv_obj_set_size(btn_bin, 96, 41);
    lv_obj_set_style_bg_color(btn_bin, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_bin, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_bin, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_bin, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn_bin, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(btn_bin, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn_bin, (lv_opa_t)20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_bin, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_bin, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_bin, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *img_trash = lv_img_create(btn_bin);
    lv_img_set_src(img_trash, &trash_icon);
    lv_obj_center(img_trash);

    // Button 2: Center Microphone / STOP Button (X=108, W=96, H=41)
    btn_voice_stop = lv_obj_create(glass);
    lv_obj_set_pos(btn_voice_stop, 108, 153);
    lv_obj_set_size(btn_voice_stop, 96, 41);
    lv_obj_set_style_bg_color(btn_voice_stop, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_voice_stop, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_voice_stop, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_voice_stop, lv_color_hex(0x1D4ED8), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn_voice_stop, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(btn_voice_stop, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn_voice_stop, (lv_opa_t)20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_voice_stop, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_voice_stop, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_voice_stop, LV_OBJ_FLAG_CLICKABLE);

    img_voice_stop = lv_img_create(btn_voice_stop);
    lv_img_set_src(img_voice_stop, &voice_white_icon);
    lv_img_set_zoom(img_voice_stop, 220);
    lv_obj_center(img_voice_stop);

    // Button 3: Right Keyboard Button (X=212, W=96, H=41)
    btn_keyboard = lv_obj_create(glass);
    lv_obj_set_pos(btn_keyboard, 212, 153);
    lv_obj_set_size(btn_keyboard, 96, 41);
    lv_obj_set_style_bg_color(btn_keyboard, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_keyboard, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_keyboard, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_keyboard, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(btn_keyboard, 2, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(btn_keyboard, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(btn_keyboard, (lv_opa_t)20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_keyboard, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_keyboard, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_keyboard, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *img_kb = lv_img_create(btn_keyboard);
    lv_img_set_src(img_kb, &keyboard_icon);
    lv_obj_center(img_kb);

    // 6. Bottom Navigation (CAMERA | ROVER | ARM) matching Rover App exact geometry & styling
    struct ActionBtn {
        const char *label;
        const lv_img_dsc_t *icon;
        int x;
    } action_btns[3] = {{"CAMERA", &camera_icon, 4},
                        {"ROVER", &rover_icon, 108},
                        {"ARM", &arm_icon, 212}};

    for (int i = 0; i < 3; i++) {
        lv_obj_t *abtn = lv_btn_create(glass);
        nav_btns[i] = abtn;
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

        // Strict hitbox isolation: zero extended click area
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

    // 7. Full-size On-Screen Keyboard Overlay with Clean Collapse Handle
    kb_overlay = lv_obj_create(glass);
    lv_obj_set_pos(kb_overlay, 0, 56);
    lv_obj_set_size(kb_overlay, 312, 172);
    lv_obj_set_style_bg_color(kb_overlay, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(kb_overlay, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(kb_overlay, 8, LV_PART_MAIN);
    lv_obj_set_style_border_width(kb_overlay, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(kb_overlay, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_pad_all(kb_overlay, 2, LV_PART_MAIN);
    lv_obj_clear_flag(kb_overlay, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(kb_overlay, LV_OBJ_FLAG_HIDDEN); // Initially hidden

    // Textarea Input Field
    ta_input = lv_textarea_create(kb_overlay);
    lv_obj_set_pos(ta_input, 4, 2);
    lv_obj_set_size(ta_input, 260, 30);
    lv_textarea_set_one_line(ta_input, true);
    lv_textarea_set_placeholder_text(ta_input, "Type command...");
    lv_obj_set_style_text_font(ta_input, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_bg_color(ta_input, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_border_color(ta_input, lv_color_hex(0xBFDBFE), LV_PART_MAIN);
    lv_obj_set_style_radius(ta_input, 6, LV_PART_MAIN);

    // Clean Rounded Close / Collapse Handle Button at top-right
    btn_kb_close = lv_btn_create(kb_overlay);
    lv_obj_set_pos(btn_kb_close, 270, 2);
    lv_obj_set_size(btn_kb_close, 36, 30);
    lv_obj_set_style_bg_color(btn_kb_close, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_bg_color(btn_kb_close, lv_color_hex(0x1D4ED8), LV_STATE_PRESSED);
    lv_obj_set_style_radius(btn_kb_close, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_kb_close, 0, LV_PART_MAIN);
    lv_obj_set_ext_click_area(btn_kb_close, 0);
    lv_obj_clear_flag(btn_kb_close, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *img_kb_close = lv_img_create(btn_kb_close);
    lv_img_set_src(img_kb_close, &keyboard_close_icon);
    lv_obj_center(img_kb_close);
    lv_obj_clear_flag(img_kb_close, LV_OBJ_FLAG_CLICKABLE);

    // LVGL Keyboard Widget optimized for 320x240
    lv_kb = lv_keyboard_create(kb_overlay);
    lv_obj_set_pos(lv_kb, 2, 34);
    lv_obj_set_size(lv_kb, 304, 134);
    lv_obj_set_style_pad_all(lv_kb, 3, LV_PART_MAIN);
    lv_obj_set_style_pad_row(lv_kb, 2, LV_PART_ITEMS);
    lv_obj_set_style_pad_column(lv_kb, 2, LV_PART_ITEMS);
    lv_obj_set_style_text_font(lv_kb, &lv_font_montserrat_12, LV_PART_ITEMS);
    lv_obj_set_style_radius(lv_kb, 4, LV_PART_ITEMS);
    lv_keyboard_set_textarea(lv_kb, ta_input);

    return scr;
}
