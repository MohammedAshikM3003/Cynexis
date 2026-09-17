#ifndef UI_ROVER_H
#define UI_ROVER_H

#include <lvgl.h>

lv_obj_t* ui_rover_create();

// Live Rover State Getters for Arm App Integration
bool ui_rover_get_headlight();
float ui_rover_get_speed();
uint8_t ui_rover_get_fuse();
uint8_t ui_rover_get_speaker_level();

#endif // UI_ROVER_H
