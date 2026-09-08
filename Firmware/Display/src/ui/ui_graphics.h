#ifndef UI_GRAPHICS_H
#define UI_GRAPHICS_H

#include <lvgl.h>

// Draws a 3-DOF Robotic Arm vector graphic inside a parent LVGL container
void ui_draw_robotic_arm(lv_obj_t * parent);

// Draws a mini 4-wheel Rover vehicle icon inside a parent container
void ui_draw_rover_icon(lv_obj_t * parent, int x, int y);

// Draws a mini Control/Status Glove icon inside a parent container
void ui_draw_glove_icon(lv_obj_t * parent, int x, int y, lv_color_t color);

// Draws a 2x2 grid Apps icon inside a parent container
void ui_draw_apps_icon(lv_obj_t * parent, int x, int y);

#endif // UI_GRAPHICS_H
