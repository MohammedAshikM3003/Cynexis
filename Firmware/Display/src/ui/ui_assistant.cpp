#include "ui_assistant.h"
#include "ui.h"
#include <Arduino.h>
#include <cstdio>

// LVGL Asset Headers for Assistant Screen
#include "assets/arm_icon.h"
#include "assets/assistant_icon.h"
#include "assets/camera_icon.h"
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

// UI Object Pointers for Dynamic State and Pressed Effects
static lv_obj_t *btn_voice_stop = NULL;
static lv_obj_t *img_voice_stop = NULL;
static lv_obj_t *btn_keyboard = NULL;
static lv_obj_t *btn_clear_chat = NULL;
static lv_obj_t *btn_speaker = NULL;
static lv_obj_t *nav_btns[3] = {NULL, NULL, NULL}; // CAMERA, ROVER, ARM
static lv_obj_t *btn_apps_back = NULL;

static uint32_t last_touch_cmd_ms = 0;

static void update_voice_button_ui() {
    if (!btn_voice_stop || !img_voice_stop) return;

    if (assistant_state.voice_listening) {
        // Listening state: show STOP icon
        lv_img_set_src(img_voice_stop, &stop_icon);
        lv_obj_set_style_bg_color(btn_voice_stop, lv_color_hex(0x2563EB), LV_PART_MAIN);
    } else {
        // Idle state: show VOICE icon
        lv_img_set_src(img_voice_stop, &voice_white_icon);
        lv_obj_set_style_bg_color(btn_voice_stop, lv_color_hex(0x2563EB), LV_PART_MAIN);
    }
}

static void process_assistant_touch_point(int16_t x, int16_t y) {
    uint32_t now = millis();
    if (now - last_touch_cmd_ms < 100) { // 100ms touch debounce guard
        return;
    }

    const char *action_name = NULL;

    // 1. BACK TO APPS (< APPS)
    if (x >= 4 && x <= 62 && y >= 2 && y <= 30) {
        action_name = "APPS";
        if (btn_apps_back) lv_obj_add_state(btn_apps_back, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to APP DRAWER");
        ui_switch_to(SCREEN_APPS);
    }
    // 2. CLEAR CHAT (TRASH BUTTON)
    else if (x >= 265 && x <= 316 && y >= 24 && y <= 56) {
        action_name = "CLEAR CHAT";
        if (btn_clear_chat) lv_obj_add_state(btn_clear_chat, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Clear chat tapped");
    }
    // 3. SPEAKER BUTTON
    else if (x >= 240 && x <= 290 && y >= 120 && y <= 150) {
        action_name = "SPEAKER";
        if (btn_speaker) lv_obj_add_state(btn_speaker, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Speaker tapped");
    }
    // 4. MICROPHONE / STOP TOGGLE BUTTON
    else if (x >= 4 && x <= 232 && y >= 150 && y <= 196) {
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
    // 5. KEYBOARD BUTTON
    else if (x >= 234 && x <= 316 && y >= 150 && y <= 196) {
        action_name = "KEYBOARD";
        if (btn_keyboard) lv_obj_add_state(btn_keyboard, LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Keyboard tapped");
    }
    // 6. BOTTOM NAVIGATION - CAMERA
    else if (x >= 0 && x <= 103 && y >= 199 && y <= 239) {
        action_name = "CAMERA";
        if (nav_btns[0]) lv_obj_add_state(nav_btns[0], LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to CAMERA");
        ui_switch_to(SCREEN_CAMERA);
    }
    // 7. BOTTOM NAVIGATION - ROVER
    else if (x >= 105 && x <= 208 && y >= 199 && y <= 239) {
        action_name = "ROVER";
        if (nav_btns[1]) lv_obj_add_state(nav_btns[1], LV_STATE_PRESSED);
        Serial.println("[ASSISTANT UI] Navigating to ROVER");
        ui_switch_to(SCREEN_ROVER);
    }
    // 8. BOTTOM NAVIGATION - ARM
    else if (x >= 209 && x <= 319 && y >= 199 && y <= 239) {
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
    if (code == LV_EVENT_PRESSED) {
        lv_indev_t *indev = lv_indev_get_act();
        if (indev) {
            lv_point_t point;
            lv_indev_get_point(indev, &point);
            process_assistant_touch_point(point.x, point.y);
        }
    } else if (code == LV_EVENT_RELEASED) {
        if (btn_apps_back) lv_obj_clear_state(btn_apps_back, LV_STATE_PRESSED);
        if (btn_clear_chat) lv_obj_clear_state(btn_clear_chat, LV_STATE_PRESSED);
        if (btn_speaker) lv_obj_clear_state(btn_speaker, LV_STATE_PRESSED);
        if (btn_voice_stop) lv_obj_clear_state(btn_voice_stop, LV_STATE_PRESSED);
        if (btn_keyboard) lv_obj_clear_state(btn_keyboard, LV_STATE_PRESSED);
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
    // Back Button (< APPS)
    btn_apps_back = lv_obj_create(glass);
    lv_obj_set_pos(btn_apps_back, 4, 2);
    lv_obj_set_size(btn_apps_back, 58, 22);
    lv_obj_set_style_bg_color(btn_apps_back, lv_color_hex(0xEFF6FF), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_apps_back, 6, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_apps_back, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_apps_back, lv_color_hex(0xBFDBFE), LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_apps_back, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_apps_back, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_apps_back, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *lbl_back = lv_label_create(btn_apps_back);
    lv_label_set_text(lbl_back, "< APPS");
    lv_obj_set_style_text_color(lbl_back, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_back, &lv_font_montserrat_10, LV_PART_MAIN);
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
    lv_obj_add_flag(conv_card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_scrollbar_mode(conv_card, LV_SCROLLBAR_MODE_ON);
    lv_obj_set_style_width(conv_card, 4, LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_color(conv_card, lv_color_hex(0x2563EB), LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_opa(conv_card, LV_OPA_COVER, LV_PART_SCROLLBAR);
    lv_obj_set_style_radius(conv_card, 2, LV_PART_SCROLLBAR);

    // Top-Right Clear Chat / Trash Button
    btn_clear_chat = lv_obj_create(conv_card);
    lv_obj_set_pos(btn_clear_chat, 270, 2);
    lv_obj_set_size(btn_clear_chat, 24, 22);
    lv_obj_set_style_bg_color(btn_clear_chat, lv_color_hex(0xF1F5F9), LV_PART_MAIN);
    lv_obj_set_style_radius(btn_clear_chat, 6, LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_clear_chat, 1, LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_clear_chat, lv_color_hex(0xE2E8F0), LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_clear_chat, 0, LV_PART_MAIN);
    lv_obj_clear_flag(btn_clear_chat, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(btn_clear_chat, LV_OBJ_FLAG_CLICKABLE);

    lv_obj_t *img_trash = lv_img_create(btn_clear_chat);
    lv_img_set_src(img_trash, &trash_icon);
    lv_img_set_zoom(img_trash, 200);
    lv_obj_center(img_trash);

    // Robot Icon
    lv_obj_t *img_bot = lv_img_create(conv_card);
    lv_img_set_src(img_bot, &assistant_icon);
    lv_img_set_zoom(img_bot, 220);
    lv_obj_set_pos(img_bot, 132, 2);

    // Prompt Header Text
    lv_obj_t *lbl_prompt_title = lv_label_create(conv_card);
    lv_label_set_text(lbl_prompt_title, "How can I help?");
    lv_obj_set_style_text_color(lbl_prompt_title, lv_color_hex(0x0F172A), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_prompt_title, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_prompt_title, 94, 34);

    lv_obj_t *lbl_prompt_sub = lv_label_create(conv_card);
    lv_label_set_text(lbl_prompt_sub, "Tap the microphone to speak or keyboard to type.");
    lv_obj_set_style_text_color(lbl_prompt_sub, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_prompt_sub, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_prompt_sub, 14, 48);

    // Chat Message 1: User Message Bubble
    lv_obj_t *msg_user = lv_obj_create(conv_card);
    lv_obj_set_pos(msg_user, 4, 64);
    lv_obj_set_size(msg_user, 282, 38);
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
    lv_obj_set_pos(lbl_u_body, 4, 16);

    lv_obj_t *lbl_u_time = lv_label_create(msg_user);
    lv_label_set_text(lbl_u_time, "14:25");
    lv_obj_set_style_text_color(lbl_u_time, lv_color_hex(0x64748B), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_u_time, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_pos(lbl_u_time, 244, 16);

    // Chat Message 2: Assistant Message Bubble
    lv_obj_t *msg_ast = lv_obj_create(conv_card);
    lv_obj_set_pos(msg_ast, 4, 106);
    lv_obj_set_size(msg_ast, 282, 38);
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
    lv_obj_set_pos(lbl_a_body, 4, 16);

    // Speaker Button inside Assistant response
    btn_speaker = lv_obj_create(msg_ast);
    lv_obj_set_pos(btn_speaker, 222, 12);
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
    lv_obj_set_pos(lbl_a_time, 244, 16);

    // 5. Input Controls Area (Microphone / STOP + Keyboard)
    // Microphone / STOP Button (Wide Blue Button)
    btn_voice_stop = lv_obj_create(glass);
    lv_obj_set_pos(btn_voice_stop, 4, 153);
    lv_obj_set_size(btn_voice_stop, 228, 41);
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

    // Keyboard Button (Light Gray Button to the Right)
    btn_keyboard = lv_obj_create(glass);
    lv_obj_set_pos(btn_keyboard, 236, 153);
    lv_obj_set_size(btn_keyboard, 72, 41);
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
    lv_img_set_zoom(img_kb, 220);
    lv_obj_center(img_kb);

    // 6. Bottom Navigation (CAMERA | ROVER | ARM) matching Rover App exact geometry
    const char *nav_labels[3] = {"CAMERA", "ROVER", "ARM"};
    const lv_img_dsc_t *nav_icons[3] = {&camera_icon, &rover_icon, &arm_icon};
    int nav_x[3] = {4, 108, 212};

    for (int i = 0; i < 3; i++) {
        nav_btns[i] = lv_obj_create(glass);
        lv_obj_set_pos(nav_btns[i], nav_x[i], 199);
        lv_obj_set_size(nav_btns[i], 96, 26);
        lv_obj_set_style_bg_color(nav_btns[i], lv_color_hex(0xF1F5F9), LV_PART_MAIN);
        lv_obj_set_style_radius(nav_btns[i], 6, LV_PART_MAIN);
        lv_obj_set_style_border_width(nav_btns[i], 1, LV_PART_MAIN);
        lv_obj_set_style_border_color(nav_btns[i], lv_color_hex(0xE2E8F0), LV_PART_MAIN);
        lv_obj_set_style_pad_all(nav_btns[i], 0, LV_PART_MAIN);
        lv_obj_clear_flag(nav_btns[i], LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_clear_flag(nav_btns[i], LV_OBJ_FLAG_CLICKABLE);

        lv_obj_t *ic = lv_img_create(nav_btns[i]);
        lv_img_set_src(ic, nav_icons[i]);
        lv_img_set_zoom(ic, 180);
        lv_obj_set_pos(ic, 8, 4);

        lv_obj_t *lbl = lv_label_create(nav_btns[i]);
        lv_label_set_text(lbl, nav_labels[i]);
        lv_obj_set_style_text_color(lbl, lv_color_hex(0x0F172A), LV_PART_MAIN);
        lv_obj_set_style_text_font(lbl, &lv_font_montserrat_10, LV_PART_MAIN);
        lv_obj_set_pos(lbl, 32, 6);
    }

    return scr;
}
