#ifndef UI_BOOT_H
#define UI_BOOT_H

#include <lvgl.h>

/**
 * @brief Starts the CYNEXIS boot animation sequence.
 * @param next_screen Pointer to the main home screen to load when boot animation completes (at 6.0s).
 */
void ui_boot_start(lv_obj_t * next_screen);

#endif // UI_BOOT_H
