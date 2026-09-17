#include "ui_boot.h"
#include <Arduino.h>

// State handles for Boot Animation elements
static lv_obj_t * scr_boot = NULL;
static lv_obj_t * target_next_screen = NULL;

static lv_obj_t * bg_panel = NULL;
static lv_obj_t * logo_container = NULL;
static lv_obj_t * logo_icon = NULL;
static lv_obj_t * lbl_title = NULL;
static lv_obj_t * lbl_subtitle = NULL;

static lv_obj_t * init_container = NULL;
static lv_obj_t * lbl_init_status = NULL;
static lv_obj_t * bar_init = NULL;

static lv_obj_t * check_container = NULL;
static lv_obj_t * lbl_checks[5] = {NULL, NULL, NULL, NULL, NULL};

static lv_obj_t * branding_container = NULL;
static lv_obj_t * lbl_ready_badge = NULL;

static lv_timer_t * boot_timer = NULL;
static uint32_t start_time_ms = 0;

// Phase tracking flags
static bool phase_0_5_done = false;
static bool phase_1_2_done = false;
static bool phase_2_0_done = false;
static bool phase_2_7_done = false;
static bool phase_3_2_done = false;
static bool phase_4_5_done = false;
static bool phase_5_3_done = false;
static bool phase_6_0_done = false;

static const char * check_labels[5] = {
    "ESP32", "MOTORS", "ARM", "SENSORS", "CAMERA"
};

// Non-blocking Timer Callback driving the 0.0s - 6.0s Boot Sequence
static void boot_timer_cb(lv_timer_t * timer) {
    uint32_t elapsed = lv_tick_get() - start_time_ms;

    // --- PHASE 1: 0.5s - Light-blue background elements appear ---
    if (elapsed >= 500 && !phase_0_5_done) {
        phase_0_5_done = true;
        // Transition background to soft light-blue / cyan tech palette
        lv_obj_set_style_bg_color(bg_panel, lv_color_hex(0xE0F2FE), LV_PART_MAIN); // Sky Blue 100
        lv_obj_set_style_border_color(bg_panel, lv_color_hex(0x0284C7), LV_PART_MAIN); // Sky Blue 600
        lv_obj_set_style_border_width(bg_panel, 3, LV_PART_MAIN);
    }

    // --- PHASE 2: 1.2s - Robotic Arm / C-Logo builds ---
    if (elapsed >= 1200 && !phase_1_2_done) {
        phase_1_2_done = true;
        lv_obj_clear_flag(logo_container, LV_OBJ_FLAG_HIDDEN);
    }

    // --- PHASE 3: 2.0s - CYNEXIS text appears ---
    if (elapsed >= 2000 && !phase_2_0_done) {
        phase_2_0_done = true;
        lv_obj_clear_flag(lbl_title, LV_OBJ_FLAG_HIDDEN);
    }

    // --- PHASE 4: 2.7s - ROBOTIC ASSISTANCE SYSTEM subtitle appears ---
    if (elapsed >= 2700 && !phase_2_7_done) {
        phase_2_7_done = true;
        lv_obj_clear_flag(lbl_subtitle, LV_OBJ_FLAG_HIDDEN);
    }

    // --- PHASE 5: 3.2s - SYSTEM INITIALIZATION + Progress bar (3.2s to 4.5s) ---
    if (elapsed >= 3200 && elapsed < 4500) {
        if (!phase_3_2_done) {
            phase_3_2_done = true;
            lv_obj_clear_flag(init_container, LV_OBJ_FLAG_HIDDEN);
        }
        // Smoothly animate progress bar 0% -> 100% over 1300ms (3200ms to 4500ms)
        int32_t progress = map(elapsed, 3200, 4500, 0, 100);
        progress = constrain(progress, 0, 100);
        lv_bar_set_value(bar_init, progress, LV_ANIM_OFF);
    }

    // --- PHASE 6: 4.5s - Sequential Diagnostic Checkmarks (4.5s to 5.3s) ---
    if (elapsed >= 4500 && !phase_4_5_done) {
        if (!phase_4_5_done) {
            phase_4_5_done = true;
            lv_obj_add_flag(init_container, LV_OBJ_FLAG_HIDDEN);
            lv_obj_clear_flag(check_container, LV_OBJ_FLAG_HIDDEN);
        }
    }

    if (elapsed >= 4500 && elapsed < 5300) {
        // Step checkmarks sequentially every 160ms
        uint32_t step_time = elapsed - 4500;
        for (int i = 0; i < 5; i++) {
            if (step_time >= (uint32_t)(i * 160)) {
                if (lbl_checks[i]) {
                    char buf[32];
                    snprintf(buf, sizeof(buf), "%s  #22C55E %s#", check_labels[i], LV_SYMBOL_OK);
                    lv_label_set_text(lbl_checks[i], buf);
                }
            }
        }
    }

    // --- PHASE 7: 5.3s - Final CYNEXIS Branding Screen ---
    if (elapsed >= 5300 && !phase_5_3_done) {
        phase_5_3_done = true;
        lv_obj_add_flag(check_container, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(branding_container, LV_OBJ_FLAG_HIDDEN);
    }

    // --- PHASE 8: 6.0s - Seamless Switch to existing CYNEXIS Home UI ---
    if (elapsed >= 6000 && !phase_6_0_done) {
        phase_6_0_done = true;
        Serial.println("[BOOT SCREEN] Animation sequence complete (6.0s)! Transitioning to Home UI...");

        // Stop boot timer
        if (boot_timer) {
            lv_timer_del(boot_timer);
            boot_timer = NULL;
        }

        // Load Home Screen directly and clean up boot screen
        if (target_next_screen) {
            lv_scr_load(target_next_screen);
            if (scr_boot) {
                lv_obj_del_async(scr_boot);
                scr_boot = NULL;
            }
        }
    }
}

void ui_boot_start(lv_obj_t * next_screen) {
    target_next_screen = next_screen;

    // Reset phase flags
    phase_0_5_done = false;
    phase_1_2_done = false;
    phase_2_0_done = false;
    phase_2_7_done = false;
    phase_3_2_done = false;
    phase_4_5_done = false;
    phase_5_3_done = false;
    phase_6_0_done = false;

    // 1. Create Base Boot Screen
    scr_boot = lv_obj_create(NULL);
    lv_obj_clear_flag(scr_boot, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(scr_boot, lv_color_hex(0xFFFFFF), LV_PART_MAIN);

    // 2. Main Background Panel (0.0s White, transitions to light-blue at 0.5s)
    bg_panel = lv_obj_create(scr_boot);
    lv_obj_set_size(bg_panel, 310, 230);
    lv_obj_center(bg_panel);
    lv_obj_set_style_bg_color(bg_panel, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_border_color(bg_panel, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_border_width(bg_panel, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(bg_panel, 12, LV_PART_MAIN);
    lv_obj_clear_flag(bg_panel, LV_OBJ_FLAG_SCROLLABLE);

    // 3. Logo Container & Graphic Icon (Center Top)
    logo_container = lv_obj_create(bg_panel);
    lv_obj_set_size(logo_container, 56, 56);
    lv_obj_align(logo_container, LV_ALIGN_TOP_MID, 0, 10);
    lv_obj_set_style_bg_color(logo_container, lv_color_hex(0x0F172A), LV_PART_MAIN); // Dark Navy Core
    lv_obj_set_style_border_color(logo_container, lv_color_hex(0x0284C7), LV_PART_MAIN); // Cyan border
    lv_obj_set_style_border_width(logo_container, 2, LV_PART_MAIN);
    lv_obj_set_style_radius(logo_container, 28, LV_PART_MAIN); // Circle
    lv_obj_clear_flag(logo_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(logo_container, LV_OBJ_FLAG_HIDDEN);

    logo_icon = lv_label_create(logo_container);
    lv_label_set_text(logo_icon, "C");
    lv_obj_set_style_text_font(logo_icon, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(logo_icon, lv_color_hex(0x38BDF8), LV_PART_MAIN); // Bright Cyan
    lv_obj_center(logo_icon);

    // 4. CYNEXIS Title Text (2.0s)
    lbl_title = lv_label_create(bg_panel);
    lv_label_set_text(lbl_title, "CYNEXIS");
    lv_obj_set_style_text_font(lbl_title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_title, lv_color_hex(0x0F172A), LV_PART_MAIN); // Dark Navy
    lv_obj_align(lbl_title, LV_ALIGN_TOP_MID, 0, 72);
    lv_obj_add_flag(lbl_title, LV_OBJ_FLAG_HIDDEN);

    // 5. Subtitle Text (2.7s)
    lbl_subtitle = lv_label_create(bg_panel);
    lv_label_set_text(lbl_subtitle, "ROBOTIC ASSISTANCE SYSTEM");
    lv_obj_set_style_text_font(lbl_subtitle, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_subtitle, lv_color_hex(0x0284C7), LV_PART_MAIN); // Cyan Accent
    lv_obj_align(lbl_subtitle, LV_ALIGN_TOP_MID, 0, 96);
    lv_obj_add_flag(lbl_subtitle, LV_OBJ_FLAG_HIDDEN);

    // 6. Initialization Container (Progress Bar 3.2s - 4.5s)
    init_container = lv_obj_create(bg_panel);
    lv_obj_set_size(init_container, 260, 60);
    lv_obj_align(init_container, LV_ALIGN_BOTTOM_MID, 0, -10);
    lv_obj_set_style_bg_opa(init_container, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(init_container, 0, LV_PART_MAIN);
    lv_obj_clear_flag(init_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(init_container, LV_OBJ_FLAG_HIDDEN);

    lbl_init_status = lv_label_create(init_container);
    lv_label_set_text(lbl_init_status, "SYSTEM INITIALIZATION...");
    lv_obj_set_style_text_font(lbl_init_status, &lv_font_montserrat_10, LV_PART_MAIN);
    lv_obj_set_style_text_color(lbl_init_status, lv_color_hex(0x475569), LV_PART_MAIN);
    lv_obj_align(lbl_init_status, LV_ALIGN_TOP_MID, 0, 0);

    bar_init = lv_bar_create(init_container);
    lv_obj_set_size(bar_init, 220, 10);
    lv_obj_align(bar_init, LV_ALIGN_BOTTOM_MID, 0, -10);
    lv_obj_set_style_bg_color(bar_init, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_init, lv_color_hex(0x0284C7), LV_PART_INDICATOR);

    // 7. Diagnostic Checklist Container (4.5s - 5.3s)
    check_container = lv_obj_create(bg_panel);
    lv_obj_set_size(check_container, 270, 70);
    lv_obj_align(check_container, LV_ALIGN_BOTTOM_MID, 0, -5);
    lv_obj_set_style_bg_color(check_container, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_border_color(check_container, lv_color_hex(0xBAE6FD), LV_PART_MAIN);
    lv_obj_set_style_border_width(check_container, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(check_container, 8, LV_PART_MAIN);
    lv_obj_clear_flag(check_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(check_container, LV_OBJ_FLAG_HIDDEN);

    // Create 5 diagnostic checklist items in 2 horizontal rows
    for (int i = 0; i < 5; i++) {
        lbl_checks[i] = lv_label_create(check_container);
        lv_label_set_recolor(lbl_checks[i], true); // Enable color formatting (#22C55E ✓#)
        
        char buf[32];
        snprintf(buf, sizeof(buf), "%s  ...", check_labels[i]);
        lv_label_set_text(lbl_checks[i], buf);
        lv_obj_set_style_text_font(lbl_checks[i], &lv_font_montserrat_10, LV_PART_MAIN);

        int col = i % 3;
        int row = i / 3;
        lv_obj_set_pos(lbl_checks[i], 10 + (col * 85), 5 + (row * 24));
    }

    // 8. Final CYNEXIS Branding Screen Container (5.3s - 6.0s)
    branding_container = lv_obj_create(bg_panel);
    lv_obj_set_size(branding_container, 270, 70);
    lv_obj_align(branding_container, LV_ALIGN_BOTTOM_MID, 0, -5);
    lv_obj_set_style_bg_color(branding_container, lv_color_hex(0x0F172A), LV_PART_MAIN); // Dark Navy Card
    lv_obj_set_style_border_color(branding_container, lv_color_hex(0x38BDF8), LV_PART_MAIN);
    lv_obj_set_style_border_width(branding_container, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(branding_container, 8, LV_PART_MAIN);
    lv_obj_clear_flag(branding_container, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(branding_container, LV_OBJ_FLAG_HIDDEN);

    /* 
     * =========================================================================
     * PLACEHOLDER FOR SUPPLIED CYNEXIS WALLPAPER IMAGE (cynexis_wallpaper)
     * When ready to embed the bitmap wallpaper:
     * lv_obj_t * img_wp = lv_img_create(branding_container);
     * lv_img_set_src(img_wp, &cynexis_wallpaper);
     * =========================================================================
     */

    lbl_ready_badge = lv_label_create(branding_container);
    lv_label_set_recolor(lbl_ready_badge, true);
    lv_label_set_text(lbl_ready_badge, "#22C55E " LV_SYMBOL_OK " SYSTEM READY#");
    lv_obj_set_style_text_font(lbl_ready_badge, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_center(lbl_ready_badge);

    // 9. Load Boot Screen & Start Non-Blocking 20ms Animation Timer
    lv_scr_load(scr_boot);
    start_time_ms = lv_tick_get();
    boot_timer = lv_timer_create(boot_timer_cb, 20, NULL);

    Serial.println("[BOOT SCREEN] Non-blocking CYNEXIS boot animation started!");
}
