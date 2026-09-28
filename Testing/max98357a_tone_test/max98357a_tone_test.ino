/*
 * CYNEXIS — Minimal ESP32 MAX98357A 440Hz Audio Subsystem Test
 * 
 * Target Hardware:
 *   - ESP32      : Dev Module (WROOM-32)
 *   - I2S BCLK   : GPIO 19
 *   - I2S WS/LRC : GPIO 25
 *   - I2S DIN    : GPIO 33
 *   - MAX98357A  : VIN = 5.00V (XL4016), GND = Common GND
 *   - SD / MODE  : 3.3V (HIGH - Left Channel / Enabled)
 *   - GAIN       : GND (Grounded - 12dB Gain)
 *   - Speaker    : 4 Ohm / 3W Mono Speaker (OUT+ / OUT-)
 * 
 * Test Configuration:
 *   - Minimal isolated test (No Wi-Fi, BT, PCA9685, or motors).
 *   - Sample Rate : 48,000 Hz
 *   - Bits        : 16-bit PCM
 *   - Format      : Standard Philips I2S (I2S_COMM_FORMAT_I2S)
 *   - Sine Wave   : 440 Hz pre-calculated 1200-frame continuous buffer.
 */

#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#define I2S_NUM           I2S_NUM_0
#define PIN_I2S_BCLK      19
#define PIN_I2S_LRC       25
#define PIN_I2S_DIN       33
#define AUDIO_SAMPLE_RATE 48000

// 1200 frames @ 48kHz = exactly 11 full cycles of 440 Hz (0.025s) with 0 phase drift
#define SINE_BUFFER_FRAMES 1200
#define SINE_BUFFER_SAMPLES (SINE_BUFFER_FRAMES * 2)

int16_t g_sineBuffer[SINE_BUFFER_SAMPLES];

const char* getVolumeLevel(float amplitude) {
    if (amplitude < 40.0f) return "LOW";
    if (amplitude < 70.0f) return "MEDIUM";
    if (amplitude < 90.0f) return "HIGH";
    return "VERY HIGH";
}

void generatePrecalculatedSineWave(float volume_pct) {
    float scale = (volume_pct / 100.0f) * 32767.0f; // 10% volume = 3276.7 max amplitude
    const float freq = 440.0f;

    Serial.printf("[INIT] Pre-calculating %d-frame (11 cycles) 440Hz sine buffer (Amplitude=%.0f%%)...\n", 
                  SINE_BUFFER_FRAMES, volume_pct);

    for (int i = 0; i < SINE_BUFFER_FRAMES; i++) {
        float t = (float)i / (float)AUDIO_SAMPLE_RATE;
        int16_t sample = (int16_t)(sinf(2.0f * M_PI * freq * t) * scale);
        
        g_sineBuffer[i * 2]     = sample; // Left channel
        g_sineBuffer[i * 2 + 1] = sample; // Right channel
    }
    Serial.println("[INIT] Pre-calculation complete. Buffer phase continuous.");
}

bool initI2S() {
    Serial.println("\n[I2S] Initializing...");

    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT, // Standard 2-channel I2S stereo
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = PIN_I2S_BCLK,
        .ws_io_num = PIN_I2S_LRC,
        .data_out_num = PIN_I2S_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    esp_err_t err = i2s_driver_install(I2S_NUM, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_driver_install failed: 0x%X\n", err);
        return false;
    }

    err = i2s_set_pin(I2S_NUM, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_set_pin failed: 0x%X\n", err);
        return false;
    }

    err = i2s_set_clk(I2S_NUM, AUDIO_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_set_clk failed: 0x%X\n", err);
        return false;
    }

    i2s_zero_dma_buffer(I2S_NUM);
    Serial.println("[I2S] SUCCESS");
    return true;
}

void play440HzTestTone(int duration_ms) {
    Serial.printf("[TEST] Playing 440Hz tone (%d ms)...\n", duration_ms);

    size_t bytes_written = 0;
    uint32_t start_time = millis();

    while (millis() - start_time < (uint32_t)duration_ms) {
        i2s_write(I2S_NUM, g_sineBuffer, sizeof(g_sineBuffer), &bytes_written, portMAX_DELAY);
    }

    // Force zero DMA buffer immediately to ensure silence during pause
    i2s_zero_dma_buffer(I2S_NUM);
    Serial.println("[TEST] Tone stopped.");
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) { delay(10); }

    Serial.println("\n==========================================");
    Serial.println(" CYNEXIS — MAX98357A VOLUME COMPARISON");
    Serial.println("==========================================");
    Serial.println("LOW    : 30%");
    Serial.println("MEDIUM : 60%");
    Serial.println("HIGH   : 80%");
    Serial.println("==========================================");

    if (!initI2S()) {
        Serial.println("[FATAL] I2S Initialization Failed!");
        while (1) { delay(1000); }
    }
}

void loop() {
    struct TestLevel {
        const char* name;
        float amplitude;
    } levels[] = {
        {"LOW", 30.0f},
        {"MEDIUM", 60.0f},
        {"HIGH", 80.0f}
    };

    for (int i = 0; i < 3; i++) {
        Serial.printf("\n[VOLUME TEST] %s — %.0f%%\n", levels[i].name, levels[i].amplitude);
        generatePrecalculatedSineWave(levels[i].amplitude);
        play440HzTestTone(2000);
        Serial.println("[PAUSE] Silence for 1000 ms...");
        delay(1000);
    }

    Serial.println("\n[VOLUME TEST] Cycle complete.");
    Serial.println("[PAUSE] 3000 ms...");
    delay(3000);
}
