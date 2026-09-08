#ifndef UI_HOME_H
#define UI_HOME_H

#include <lvgl.h>
#include "../system/time_manager.h"
#include "ui_status_card.h"

lv_obj_t* ui_home_create(const SystemStatus &initial_status);
void ui_home_update_clock(const TimeData &time_data);
void ui_home_update_status(const SystemStatus &status);

#endif // UI_HOME_H
