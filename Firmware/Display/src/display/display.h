#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>
#include <TFT_eSPI.h>
#include <lvgl.h>

#define SCREEN_WIDTH  320
#define SCREEN_HEIGHT 240

extern TFT_eSPI tft;

void display_init();

#endif // DISPLAY_H
