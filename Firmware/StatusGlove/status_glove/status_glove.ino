/**
 * ============================================================
 * CYNEXIS — Status Glove Firmware
 * Version: 1.0
 * File: status_glove.ino
 * ------------------------------------------------------------
 * Hardware:
 *   - ESP32
 *   - SSD1306 OLED display (128x64, I2C, address 0x3C)
 *   - Vibration motor (3V, via NPN transistor)
 *   - Buzzer (passive, optional)
 *   - 18650 battery + TP4056 charger
 *
 * Libraries required:
 *   - Adafruit SSD1306
 *   - Adafruit GFX Library
 *   - esp_now.h  (built-in)
 *   - WiFi.h     (built-in)
 *
 * Pin mapping:
 *   SSD1306 SDA       → GPIO 21
 *   SSD1306 SCL       → GPIO 22
 *   Vibration motor   → GPIO 26 (via NPN transistor base)
 *   Buzzer (optional) → GPIO 27 (via 100Ω resistor)
 *   Battery sense     → GPIO 36
 *   Status LED        → GPIO 2
 * ============================================================
 */

// ============================================================
// INCLUDES
// ============================================================

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_now.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <driver/i2s.h>

#include "../../Protocol/cynexis_protocol.h"
#include "../../Protocol/cynexis_mac.h"

// ============================================================
// OLED CONFIGURATION
// ============================================================

#define OLED_WIDTH   128
#define OLED_HEIGHT   64
#define OLED_RESET    -1   // No reset pin
#define OLED_ADDR    0x3C

Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);

// ============================================================
// PIN DEFINITIONS (LEFT-HAND INTERFACE GLOVE)
// ============================================================

// Feedback & Alerts
#define PIN_VIBRATION    26
#define PIN_BUZZER       27   // Optional — set to -1 if not installed
#define PIN_BATT         36
#define PIN_LED          2

// INMP441 I2S MEMS Microphone Pins
#define PIN_I2S_SCK      14   // BCLK (Bit Clock)
#define PIN_I2S_WS       15   // LRCLK (Word Select)
#define PIN_I2S_SD       13   // DOUT (Serial Data Input to ESP32)
#define I2S_MIC_PORT     I2S_NUM_0

// Note: Future 2.8" Capacitive Touch Display Pins (Reserved):
// SPI TFT: MOSI=23, SCK=18, CS=5, DC=4, RST=32, Backlight=33
// I2C Touch: SDA=21, SCL=22, Touch INT=27

// ============================================================
// NETWORK AUDIO CONFIGURATION
// ============================================================

#ifndef WIFI_SSID
#define WIFI_SSID "YOUR_WIFI_SSID"
#endif

#ifndef WIFI_PASS
#define WIFI_PASS "YOUR_WIFI_PASS"
#endif

#ifndef PC_IP_ADDR
#define PC_IP_ADDR "192.168.1.100"  // Set to CYNEXIS PC IP
#endif

#define UDP_AUDIO_PORT       50005
#define AUDIO_SAMPLE_RATE    16000
#define AUDIO_FRAME_SAMPLES  256    // 256 samples * 2 bytes = 512 bytes payload (16ms)
#define AUDIO_PAYLOAD_BYTES  (AUDIO_FRAME_SAMPLES * 2)

// Packed 8-byte UDP Audio Header
struct __attribute__((packed)) AudioPacketHeader {
    char magic[2];          // 'C', 'Y' (0x43, 0x59)
    uint16_t sequence;      // 0 - 65535 monotonic
    uint16_t sample_rate;   // 16000
    uint16_t payload_len;   // 512
};

// ============================================================
// CONFIGURATION
// ============================================================

#define VIBRATE_SHORT_MS    150   // Short buzz for normal alerts
#define VIBRATE_LONG_MS     500   // Long buzz for critical alerts
#define BATT_VOLTAGE_DIV    2.0f
#define BATT_MAX_V          4.2f
#define BATT_MIN_V          3.0f
#define ADC_REF_V           3.3f
#define ADC_MAX             4095
#define DISPLAY_REFRESH_MS  200   // Refresh OLED at 5Hz

// ============================================================
// GLOBALS
// ============================================================

// Last received status packet from robot
RobotToStatusPacket robot_status;
volatile bool new_status = false;
unsigned long last_rx_ms = 0;

// Display refresh tracking
unsigned long last_display_ms = 0;

// Glove's own battery
uint8_t glove_battery_pct = 100;

// State string lookup
const char* STATE_NAMES[] = {
    "INIT",    // 0
    "IDLE",    // 1
    "MANUAL",  // 2
    "AI MODE", // 3
    "EMERG",   // 4
    "SHUTDOWN" // 5
};

// Error string lookup (short form for OLED)
const char* ERR_NAMES[] = {
    "OK",        // 0x00
    "COMMS",     // 0x01
    "WDT RST",   // 0x02
    "LOW BATT",  // 0x03
    "I2C FAIL",  // 0x04
    "OBSTACLE",  // 0x05
    "SRV STALL", // 0x06
    "MOT OC",    // 0x07
    "ESTOP",     // 0x08
    "INIT FAIL", // 0x09
    "UNKNOWN"    // 0xFF -> index 10
};

// Forward declarations
void init_espnow();
void init_i2s_microphone();
void audio_stream_task(void* param);
void draw_display();
void draw_status_bar();
void draw_telemetry();
void draw_emergency();
void vibrate(int duration_ms);
void beep(int freq, int duration_ms);
float read_battery_voltage();
uint8_t voltage_to_percent(float v);

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void on_data_recv(const esp_now_recv_info_t* recv_info, const uint8_t* data, int len);
void on_data_sent(const wifi_tx_info_t* info, esp_now_send_status_t status);
#else
void on_data_recv(const uint8_t* mac, const uint8_t* data, int len);
void on_data_sent(const uint8_t* mac, esp_now_send_status_t status);
#endif

void blink(int n, int ms);
const char* get_state_name(uint8_t state_id);
const char* get_error_name(uint8_t err);

WiFiUDP audio_udp;

// ============================================================
// SETUP
// ============================================================

void setup() {
    Serial.begin(115200);
    Serial.println("[CYNEXIS] Status Glove booting...");

    pinMode(PIN_LED,       OUTPUT);
    pinMode(PIN_VIBRATION, OUTPUT);

    #if PIN_BUZZER >= 0
    #if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    ledcAttach(PIN_BUZZER, 2000, 8);
    #else
    ledcSetup(0, 2000, 8);
    ledcAttachPin(PIN_BUZZER, 0);
    #endif
    #endif

    blink(3, 200);

    // --------------------------------------------------------
    // OLED
    // --------------------------------------------------------
    Wire.begin(21, 22);
    if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println("[ERROR] SSD1306 not found!");
        while (true) blink(5, 100);
    }

    oled.clearDisplay();
    oled.setTextColor(SSD1306_WHITE);
    oled.setTextSize(1);
    oled.setCursor(10, 20);
    oled.print("CYNEXIS v1.0");
    oled.setCursor(10, 35);
    oled.print("Status Glove");
    oled.display();
    delay(1500);

    // --------------------------------------------------------
    // ADC
    // --------------------------------------------------------
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // --------------------------------------------------------
    // INMP441 I2S MICROPHONE & AUDIO TASK
    // --------------------------------------------------------
    init_i2s_microphone();
    xTaskCreatePinnedToCore(
        audio_stream_task,
        "audio_stream_task",
        4096,
        NULL,
        5,
        NULL,
        0  // Pinned to Core 0 to leave Core 1 for main loop and display
    );

    // --------------------------------------------------------
    // ESP-NOW
    // --------------------------------------------------------
    init_espnow();

    // --------------------------------------------------------
    // Startup feedback
    // --------------------------------------------------------
    vibrate(VIBRATE_SHORT_MS);

    Serial.println("[CYNEXIS] Status Glove ready.");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
    // Read glove's own battery
    glove_battery_pct = voltage_to_percent(read_battery_voltage());

    // Refresh OLED at display rate
    unsigned long now = millis();
    if (now - last_display_ms >= DISPLAY_REFRESH_MS) {
        last_display_ms = now;
        draw_display();
    }

    // Check for link lost (>2 seconds without a robot packet)
    if (millis() - last_rx_ms > 2000 && last_rx_ms > 0) {
        // Draw link-lost warning on next refresh (handled in draw_display)
    }
}

// ============================================================
// DISPLAY RENDERING
// ============================================================

void draw_display() {
    oled.clearDisplay();

    bool link_ok = (millis() - last_rx_ms < 2000) && (last_rx_ms > 0);

    if (!link_ok) {
        // ---- LINK LOST SCREEN ----
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.print("CYNEXIS");

        oled.setCursor(0, 20);
        oled.setTextSize(2);
        oled.print("NO LINK");

        oled.setTextSize(1);
        oled.setCursor(0, 50);
        oled.print("Glove: ");
        oled.print(glove_battery_pct);
        oled.print("%");

        oled.display();
        return;
    }

    if (robot_status.state == (uint8_t)STATE_EMERGENCY) {
        draw_emergency();
        oled.display();
        return;
    }

    draw_telemetry();
    oled.display();
}

void draw_telemetry() {
    // ---- LINE 1: CYNEXIS | MODE ----
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.print("CYNEXIS");
    oled.setCursor(70, 0);
    oled.print(get_state_name(robot_status.state));

    // Separator
    oled.drawFastHLine(0, 9, 128, SSD1306_WHITE);

    // ---- LINE 2: Robot battery + RSSI ----
    oled.setCursor(0, 12);
    oled.print("R:");
    oled.print(robot_status.robot_battery_pct);
    oled.print("% G:");
    oled.print(glove_battery_pct);
    oled.print("%  ");
    oled.print(robot_status.rssi);
    oled.print("dB");

    // ---- LINE 3: Subsystem status icons ----
    oled.setCursor(0, 22);
    oled.print("CAM:");
    oled.print(robot_status.flags.camera_ok   ? "OK " : "-- ");
    oled.print("ARM:");
    oled.print(robot_status.flags.arm_ok      ? "OK " : "!!");

    oled.setCursor(0, 32);
    oled.print("MOT:");
    oled.print(robot_status.flags.motors_ok   ? "OK " : "-- ");
    oled.print("LNK:");
    oled.print(robot_status.flags.esp_now_ok  ? "OK " : "!!");

    // ---- LINE 4: Obstacle + Error ----
    oled.setCursor(0, 42);
    if (robot_status.flags.obstacle) {
        oled.print("OBSTACLE DETECTED!");
    } else {
        oled.print("ERR:");
        oled.print(get_error_name(robot_status.error_code));
    }

    // ---- BOTTOM: Glove battery bar ----
    oled.setCursor(0, 56);
    oled.print("G:");
    // Battery bar (max 80px wide)
    int bar_w = map(glove_battery_pct, 0, 100, 0, 80);
    oled.fillRect(14, 57, bar_w, 6, SSD1306_WHITE);
    oled.drawRect(14, 57, 80, 6, SSD1306_WHITE);
    oled.setCursor(97, 56);
    oled.print(glove_battery_pct);
    oled.print("%");
}

void draw_emergency() {
    oled.setTextSize(2);
    oled.setCursor(10, 5);
    oled.print("EMERGENCY");

    oled.setTextSize(1);
    oled.setCursor(0, 30);
    oled.print("Err: ");
    oled.print(get_error_name(robot_status.error_code));

    oled.setCursor(0, 45);
    oled.print("Reset robot to clear");
}

// ============================================================
// ALERTS
// ============================================================

void vibrate(int duration_ms) {
    digitalWrite(PIN_VIBRATION, HIGH);
    delay(duration_ms);
    digitalWrite(PIN_VIBRATION, LOW);
}

void beep(int freq_hz, int duration_ms) {
    #if PIN_BUZZER >= 0
    #if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    ledcWriteTone(PIN_BUZZER, freq_hz);
    delay(duration_ms);
    ledcWriteTone(PIN_BUZZER, 0);
    #else
    ledcWriteTone(0, freq_hz);
    delay(duration_ms);
    ledcWriteTone(0, 0);
    #endif
    #endif
}

// ============================================================
// ESP-NOW
// ============================================================

void init_espnow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[FATAL] ESP-NOW init failed.");
        while (true) blink(3, 100);
    }

    esp_now_register_recv_cb(on_data_recv);
    esp_now_register_send_cb(on_data_sent);

    Serial.println("[ESP-NOW] Status Glove listening.");
}

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void on_data_recv(const esp_now_recv_info_t* recv_info, const uint8_t* data, int len) {
#else
void on_data_recv(const uint8_t* mac, const uint8_t* data, int len) {
#endif
    if (len != sizeof(RobotToStatusPacket)) return;

    const RobotToStatusPacket* pkt = (const RobotToStatusPacket*)data;

    if (!rts_validate(pkt)) {
        Serial.println("[ESP-NOW] Invalid packet.");
        return;
    }

    memcpy(&robot_status, pkt, sizeof(RobotToStatusPacket));
    new_status = true;
    last_rx_ms = millis();

    // Haptic alerts
    if (pkt->state == (uint8_t)STATE_EMERGENCY) {
        vibrate(VIBRATE_LONG_MS);
        beep(500, 300);
    } else if (pkt->robot_battery_pct < BATTERY_CRITICAL_PCT) {
        vibrate(VIBRATE_SHORT_MS);
        beep(1000, 100);
    } else if (pkt->flags.obstacle) {
        vibrate(VIBRATE_SHORT_MS);
    }
}

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void on_data_sent(const wifi_tx_info_t* info, esp_now_send_status_t status) {
    // Status glove only receives — no sends expected
}
#else
void on_data_sent(const uint8_t* mac, esp_now_send_status_t status) {
    // Status glove only receives — no sends expected
}
#endif

// ============================================================
// BATTERY
// ============================================================

float read_battery_voltage() {
    int raw = 0;
    for (int i = 0; i < 8; i++) raw += analogRead(PIN_BATT);
    raw /= 8;
    float adc_v = (raw / (float)ADC_MAX) * ADC_REF_V;
    return adc_v * BATT_VOLTAGE_DIV;
}

uint8_t voltage_to_percent(float v) {
    float pct = (v - BATT_MIN_V) / (BATT_MAX_V - BATT_MIN_V) * 100.0f;
    return (uint8_t)constrain((int)pct, 0, 100);
}

// ============================================================
// STRING LOOKUP HELPERS
// ============================================================

const char* get_state_name(uint8_t id) {
    if (id <= 5) return STATE_NAMES[id];
    return "???";
}

const char* get_error_name(uint8_t err) {
    if (err <= 9) return ERR_NAMES[err];
    return ERR_NAMES[10];  // "UNKNOWN"
}

// ============================================================
// UTILITY
// ============================================================

void blink(int n, int ms) {
    for (int i = 0; i < n; i++) {
        digitalWrite(PIN_LED, HIGH); delay(ms / 2);
        digitalWrite(PIN_LED, LOW);  delay(ms / 2);
    }
}

// ============================================================
// INMP441 I2S & UDP AUDIO STREAMING
// ============================================================

void init_i2s_microphone() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = (i2s_comm_format_t)(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = AUDIO_FRAME_SAMPLES,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = PIN_I2S_SCK,
        .ws_io_num = PIN_I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = PIN_I2S_SD
    };

    esp_err_t err = i2s_driver_install(I2S_MIC_PORT, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[ERROR] Failed to install I2S driver: %d\n", err);
        return;
    }

    err = i2s_set_pin(I2S_MIC_PORT, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("[ERROR] Failed to set I2S pins: %d\n", err);
        return;
    }

    Serial.println("[OK] INMP441 I2S microphone initialized.");
}

void audio_stream_task(void* param) {
    uint16_t seq = 0;
    int32_t i2s_raw_buf[AUDIO_FRAME_SAMPLES];
    int16_t pcm_16_buf[AUDIO_FRAME_SAMPLES];
    uint8_t packet_buffer[sizeof(AudioPacketHeader) + AUDIO_PAYLOAD_BYTES];

    AudioPacketHeader* header = (AudioPacketHeader*)packet_buffer;
    header->magic[0] = 'C';
    header->magic[1] = 'Y';
    header->sample_rate = AUDIO_SAMPLE_RATE;
    header->payload_len = AUDIO_PAYLOAD_BYTES;

    while (true) {
        size_t bytes_read = 0;
        esp_err_t res = i2s_read(
            I2S_MIC_PORT,
            (void*)i2s_raw_buf,
            sizeof(i2s_raw_buf),
            &bytes_read,
            portMAX_DELAY
        );

        if (res == ESP_OK && bytes_read > 0) {
            int samples_read = bytes_read / sizeof(int32_t);
            for (int i = 0; i < samples_read; i++) {
                // INMP441 delivers 24-bit audio in 32-bit slot, shift down 14 bits to scale to signed 16-bit PCM
                pcm_16_buf[i] = (int16_t)(i2s_raw_buf[i] >> 14);
            }

            if (WiFi.status() == WL_CONNECTED) {
                header->sequence = seq++;
                memcpy(packet_buffer + sizeof(AudioPacketHeader), pcm_16_buf, samples_read * sizeof(int16_t));

                audio_udp.beginPacket(PC_IP_ADDR, UDP_AUDIO_PORT);
                audio_udp.write(packet_buffer, sizeof(AudioPacketHeader) + (samples_read * sizeof(int16_t)));
                audio_udp.endPacket();
            }
        }
        taskYIELD();
    }
}

// ============================================================
// END OF status_glove.ino
// ============================================================
