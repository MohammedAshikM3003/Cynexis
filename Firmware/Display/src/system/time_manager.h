#ifndef TIME_MANAGER_H
#define TIME_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include "../wifi_config.h"

struct TimeData {
    char hour_str[8];    // e.g. "21"
    char min_str[8];     // e.g. "15"
    char day_str[8];     // e.g. "Mon"
    char date_str[16];   // e.g. "06 Sep"
    char time_str[16];   // e.g. "21:15"
    bool is_synced;
};

void time_manager_init();
bool time_manager_update(TimeData &out_data);

#endif // TIME_MANAGER_H
