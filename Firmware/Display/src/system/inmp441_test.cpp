#include "inmp441_test.h"
#include <driver/i2s.h>
#include <cmath>

#define I2S_WS   17
#define I2S_SCK  16
#define I2S_SD   27
#define I2S_PORT I2S_NUM_0

#define SAMPLE_RATE 16000
#define BUFFER_SAMPLES 512

void inmp441_test_setup() {
    Serial.println("[INMP441 TEST] Starting Diagnostic Setup");
    Serial.println("[INMP441 TEST] WS=17");
    Serial.println("[INMP441 TEST] SCK=16");
    Serial.println("[INMP441 TEST] SD=27");
    Serial.println("[INMP441 TEST] L/R=GND / LEFT");
    Serial.println("[INMP441 TEST] Sample rate=16000 Hz");

    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT, // Use stereo format to prevent ESP32 DMA channel alignment slip
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = BUFFER_SAMPLES,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_SCK,
        .ws_io_num = I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_SD
    };

    esp_err_t err_install = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    Serial.printf("[INMP441 DEBUG] driver_install = %d (%s)\n", err_install, esp_err_to_name(err_install));

    esp_err_t err_pin = i2s_set_pin(I2S_PORT, &pin_config);
    Serial.printf("[INMP441 DEBUG] set_pin = %d (%s)\n", err_pin, esp_err_to_name(err_pin));

    esp_err_t err_start = i2s_start(I2S_PORT);
    Serial.printf("[INMP441 DEBUG] start = %d (%s)\n", err_start, esp_err_to_name(err_start));

    if (err_install == ESP_OK && err_pin == ESP_OK && err_start == ESP_OK) {
        Serial.println("[INMP441 TEST] I2S Driver Initialized & Started Successfully");
    } else {
        Serial.println("[INMP441 TEST] ERROR: I2S Initialization Failed!");
    }
}

void inmp441_test_loop() {
    static uint32_t last_log_time = 0;
    static int32_t samples_buffer[BUFFER_SAMPLES];
    size_t bytes_read = 0;

    esp_err_t err = i2s_read(I2S_PORT, samples_buffer, sizeof(samples_buffer), &bytes_read, pdMS_TO_TICKS(100));

    uint32_t now = millis();
    bool should_log = (now - last_log_time >= 200);

    if (err != ESP_OK) {
        if (should_log) {
            Serial.printf("[INMP441 DEBUG] read=ERR err=%d (%s) bytes=%d\n", err, esp_err_to_name(err), (int)bytes_read);
            last_log_time = now;
        }
        return;
    }

    if (bytes_read == 0) {
        if (should_log) {
            Serial.println("[INMP441 DEBUG] read=OK bytes=0 (ERROR: no samples received)");
            last_log_time = now;
        }
        return;
    }

    int total_samples = bytes_read / sizeof(int32_t);
    int left_nonzero = 0;
    int right_nonzero = 0;
    int total_nonzero = 0;

    int64_t sum_abs_left = 0;
    int32_t peak_left = 0;
    int left_sample_count = 0;

    int64_t sum_abs_right = 0;
    int32_t peak_right = 0;
    int right_sample_count = 0;

    for (int i = 0; i < total_samples; i++) {
        int32_t raw = samples_buffer[i];
        if (raw != 0) {
            total_nonzero++;
        }

        // Standard I2S Stereo format: even indices are Left channel (WS LOW), odd indices are Right channel (WS HIGH)
        bool is_left = (i % 2 == 0);
        int32_t sample = raw >> 8; // INMP441 24-bit audio in top 24 bits of 32-bit word
        int32_t abs_sample = std::abs(sample);

        if (is_left) {
            if (raw != 0) left_nonzero++;
            left_sample_count++;
            sum_abs_left += abs_sample;
            if (abs_sample > peak_left) {
                peak_left = abs_sample;
            }
        } else {
            if (raw != 0) right_nonzero++;
            right_sample_count++;
            sum_abs_right += abs_sample;
            if (abs_sample > peak_right) {
                peak_right = abs_sample;
            }
        }
    }

    if (should_log) {
        last_log_time = now;
        if (total_nonzero == 0) {
            Serial.printf("[INMP441 DEBUG] read=OK bytes=%d samples=%d ALL SAMPLES ZERO\n", (int)bytes_read, total_samples);
        } else {
            int32_t mean_left = left_sample_count > 0 ? (sum_abs_left / left_sample_count) : 0;
            int32_t mean_right = right_sample_count > 0 ? (sum_abs_right / right_sample_count) : 0;

            Serial.printf("[INMP441 DEBUG] read=OK bytes=%d nonzero=%d (L_nz=%d, R_nz=%d) L_level=%ld L_peak=%ld R_level=%ld R_peak=%ld\n",
                          (int)bytes_read, total_nonzero, left_nonzero, right_nonzero,
                          (long)mean_left, (long)peak_left, (long)mean_right, (long)peak_right);
            
            // Standard simplified line for user test matching requirement
            Serial.printf("[INMP441] level=%ld peak=%ld\n", (long)mean_left, (long)peak_left);
        }
    }
}
