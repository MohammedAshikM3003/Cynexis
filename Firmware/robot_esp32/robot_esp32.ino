/*
 * ============================================================
 * CYNEXIS — Robot ESP32 Firmware (ESP32 Node #3)
 * Version: 2.2 — Dedicated MAX98357A 440Hz Audio Test Mode
 * File: robot_esp32.ino
 * ------------------------------------------------------------
 * Hardware Architecture & Pin Assignments (STRICTLY PRESERVED):
 *   - Motors: BTS7960 Dual H-Bridge Motor Driver (4x 12V DC Motors)
 *       Left Motor  : L_RPWM (GPIO 26), L_LPWM (GPIO 27), L_EN (GPIO 14)
 *       Right Motor : R_RPWM (GPIO 12), R_LPWM (GPIO 13), R_EN (GPIO 15)
 *   - Servos / Arm: PCA9685 16-Channel PWM Driver via I2C
 *       SDA (GPIO 21), SCL (GPIO 22)
 *   - Sensors: HC-SR04 Ultrasonic (TRIG GPIO 5, ECHO GPIO 18)
 *   - Safety: E-Stop Button (GPIO 4, NC to GND, INPUT_PULLUP)
 *             Battery Voltage Sense (GPIO 36, ADC1_CH0)
 *             Status LED (GPIO 2, Onboard)
 *   - Audio Subsystem: MAX98357A I2S 3W Class-D Mono Amplifier + 4Ω 3W Speaker
 *       BCLK   : GPIO 19 (Bit Clock)
 *       LRC/WS : GPIO 25 (Word Select / Left-Right Clock)
 *       DIN    : GPIO 33 (Data In)
 *       VIN    : 5V Supply (from ESP32 5V / LM2596)
 *       GND    : Common GND
 *       SD     : 3.3V (Amplifier Enabled)
 *       GAIN   : Floating (Default 9dB)
 *       OUT+   : Speaker RED (+)
 *       OUT-   : Speaker BLACK (-) [BTL Differential — NEVER connect to GND]
 * ============================================================
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_now.h>
#include <Wire.h>
#include <driver/i2s.h>
#include "cynexis_protocol.h"
#include "cynexis_mac.h"

// Wi-Fi Hotspot Credentials (matching project wifi_config.h)
#ifndef WIFI_SSID
#define WIFI_SSID           "WhiteShadow"
#endif

#ifndef WIFI_PASS
#define WIFI_PASS           "No Password"
#endif

// ============================================================
// WI-FI STATIC IP CONFIGURATION (WINDOWS HOTSPOT 192.168.137.X)
// ============================================================
#define USE_STATIC_IP       1
IPAddress staticIP(192, 168, 137, 200);   // Dedicated permanent Rover IP
IPAddress gateway(192, 168, 137, 1);      // Windows Hotspot Host Gateway
IPAddress subnet(255, 255, 255, 0);      // Standard /24 Subnet Mask
IPAddress primaryDNS(192, 168, 137, 1);  // Primary DNS
IPAddress secondaryDNS(8, 8, 8, 8);      // Secondary DNS

// ============================================================
// TEST MODE CONFIGURATION
// Set to 1 to run repeating 440Hz hardware audio test
// Set to 0 for full normal rover operational mode
// ============================================================
#define AUDIO_HARDWARE_TEST   1

// ============================================================
// GPIO PIN DEFINITIONS (STRICTLY PRESERVED & AUDITED)
// ============================================================

// BTS7960 Motor Driver Pins
#define PIN_MOTOR_L_RPWM    26    // Left forward PWM
#define PIN_MOTOR_L_LPWM    27    // Left reverse PWM
#define PIN_MOTOR_L_EN      14    // Left enable
#define PIN_MOTOR_R_RPWM    12    // Right forward PWM
#define PIN_MOTOR_R_LPWM    13    // Right reverse PWM
#define PIN_MOTOR_R_EN      15    // Right enable

// I2C Bus Pins (PCA9685 Servo Driver & INA219 Power Monitor)
#define PIN_I2C_SDA         21
#define PIN_I2C_SCL         22

// HC-SR04 Ultrasonic Sensor Pins
#define PIN_HCSR04_TRIG     5
#define PIN_HCSR04_ECHO     18

// Safety & System Pins
#define PIN_ESTOP           4     // Emergency Stop (INPUT_PULLUP, NC to GND)
#define PIN_BATTERY_SENSE   36    // ADC1_CH0 battery voltage divider
#define PIN_STATUS_LED      2     // Onboard status LED

// MAX98357A I2S Audio Pins (AUDITED & SAFE)
#define PIN_I2S_BCLK        19    // I2S Bit Clock
#define PIN_I2S_LRC         25    // I2S Word Select / Left-Right Clock
#define PIN_I2S_DIN         33    // I2S Data Input

// ============================================================
// HARDWARE & CONSTANTS CONFIGURATION
// ============================================================

// PWM Channels for BTS7960 Motors
#define PWM_CHAN_L_RPWM     0
#define PWM_CHAN_L_LPWM     1
#define PWM_CHAN_R_RPWM     2
#define PWM_CHAN_R_LPWM     3
#define PWM_FREQ_HZ         20000 // 20kHz ultrasonic PWM for quiet motor drive
#define PWM_RES_BITS        8     // 8-bit resolution (0-255)

// I2S Audio Port Configuration
#define I2S_NUM             I2S_NUM_0
#define AUDIO_SAMPLE_RATE   24000 // 24kHz matching Kokoro TTS
#define AUDIO_UDP_PORT      50006
#define AUDIO_BUFFER_SIZE   1024

// UDP Network Audio Server
WiFiUDP audioUdp;

// Global System State
volatile cynexis_state_t currentState = STATE_INITIALIZATION;
volatile uint32_t lastPacketReceivedMs = 0;
volatile bool emergencyStopped = false;

// Motor state memory
uint8_t currentMotorCmd = MOTOR_STOP;
uint8_t currentMotorSpeed = 0;

// Telemetry counters
uint32_t totalPacketsRecv = 0;
uint32_t totalMissedPackets = 0;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================

void initMotors();
bool initI2S();
void initSensors();
void play440HzTestTone(int duration_ms, float volume_pct = 50.0f);
void setMotors(uint8_t cmd, uint8_t speed);
void stopMotorsImmediately();
float readObstacleDistanceCm();
void processAudioStream();

// ============================================================
// ESP-NOW RECEIVE CALLBACK
// ============================================================

#include <esp_arduino_version.h>

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingData, int len) {
#else
void OnDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
#endif
    if (len != sizeof(GloveToRobotPacket)) {
        return;
    }

    const GloveToRobotPacket* pkt = (const GloveToRobotPacket*)incomingData;
    if (!gtr_validate(pkt)) {
        return;
    }

    lastPacketReceivedMs = millis();
    totalPacketsRecv++;

    // Check E-Stop flag in incoming packet or physical button
    bool is_estop_requested = (pkt->emergency == 1) || (pkt->gesture_id == GESTURE_EMERGENCY_STOP) || (digitalRead(PIN_ESTOP) == HIGH);
    if (is_estop_requested) {
        emergencyStopped = true;
        stopMotorsImmediately();
        currentState = STATE_EMERGENCY;
        return;
    }

    if (currentState == STATE_EMERGENCY) {
        stopMotorsImmediately();
        return;
    }

    currentState = STATE_MANUAL;
    currentMotorCmd = pkt->motor_cmd;
    currentMotorSpeed = 180; // Default drive speed (0-255)

    // Obstacle proximity check
    if (currentMotorCmd == MOTOR_FORWARD) {
        float dist = readObstacleDistanceCm();
        if (dist > 0.0f && dist < OBSTACLE_STOP_CM) {
            stopMotorsImmediately();
            return;
        }
    }

    setMotors(currentMotorCmd, currentMotorSpeed);
}

// ============================================================
// HARDWARE INITIALIZATION
// ============================================================

void initMotors() {
    pinMode(PIN_MOTOR_L_EN, OUTPUT);
    pinMode(PIN_MOTOR_R_EN, OUTPUT);
    digitalWrite(PIN_MOTOR_L_EN, HIGH);
    digitalWrite(PIN_MOTOR_R_EN, HIGH);

    #if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach(PIN_MOTOR_L_RPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcAttach(PIN_MOTOR_L_LPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcAttach(PIN_MOTOR_R_RPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcAttach(PIN_MOTOR_R_LPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    #else
    ledcSetup(PWM_CHAN_L_RPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcSetup(PWM_CHAN_L_LPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcSetup(PWM_CHAN_R_RPWM, PWM_FREQ_HZ, PWM_RES_BITS);
    ledcSetup(PWM_CHAN_R_LPWM, PWM_FREQ_HZ, PWM_RES_BITS);

    ledcAttachPin(PIN_MOTOR_L_RPWM, PWM_CHAN_L_RPWM);
    ledcAttachPin(PIN_MOTOR_L_LPWM, PWM_CHAN_L_LPWM);
    ledcAttachPin(PIN_MOTOR_R_RPWM, PWM_CHAN_R_RPWM);
    ledcAttachPin(PIN_MOTOR_R_LPWM, PWM_CHAN_R_LPWM);
    #endif

    stopMotorsImmediately();
    Serial.println("[ROVER] BTS7960 Motor Driver Initialized.");
}

bool initI2S() {
    Serial.println("\n[I2S INIT] Initializing MAX98357A I2S Audio Driver...");

    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = AUDIO_SAMPLE_RATE,             // 24000 Hz
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,  // 16-bit PCM
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,   // Mono Left channel formatting
        .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num = PIN_I2S_BCLK,    // GPIO 19
        .ws_io_num = PIN_I2S_LRC,     // GPIO 25
        .data_out_num = PIN_I2S_DIN,   // GPIO 33
        .data_in_num = I2S_PIN_NO_CHANGE
    };

    esp_err_t err = i2s_driver_install(I2S_NUM, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_driver_install failed with code: 0x%X\n", err);
        return false;
    }

    err = i2s_set_pin(I2S_NUM, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_set_pin failed with code: 0x%X\n", err);
        return false;
    }

    err = i2s_set_clk(I2S_NUM, AUDIO_SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
    if (err != ESP_OK) {
        Serial.printf("[I2S ERROR] i2s_set_clk failed with code: 0x%X\n", err);
        return false;
    }

    i2s_zero_dma_buffer(I2S_NUM);
    Serial.printf("[I2S SUCCESS] MAX98357A Driver Active: BCLK=%d, WS=%d, DIN=%d, Rate=%dHz, Bits=16, Mode=Stereo\n",
                  PIN_I2S_BCLK, PIN_I2S_LRC, PIN_I2S_DIN, AUDIO_SAMPLE_RATE);
    return true;
}

void play440HzTestTone(int duration_ms, float volume_pct) {
    float scale = (volume_pct / 100.0f) * 32767.0f;
    Serial.printf("[AUDIO TEST] Starting 440Hz Sine Wave Tone for %d ms (SampleRate=%dHz, Volume=%.0f%%)...\n",
                  duration_ms, AUDIO_SAMPLE_RATE, volume_pct);

    const float freq = 440.0f; // 440 Hz (Concert Pitch A4)
    const int num_frames = (AUDIO_SAMPLE_RATE * duration_ms) / 1000;
    
    // Stereo 16-bit frame buffer: [Left_int16, Right_int16] = 4 bytes per frame
    int16_t stereo_buffer[256]; 
    size_t bytes_written = 0;
    uint32_t total_bytes_sent = 0;

    int frame_idx = 0;
    while (frame_idx < num_frames) {
        int chunk_frames = min(128, num_frames - frame_idx); // 128 stereo frames = 256 int16 samples
        
        for (int i = 0; i < chunk_frames; i++) {
            float t = (float)(frame_idx + i) / (float)AUDIO_SAMPLE_RATE;
            // 440Hz sine wave scaled by volume_pct (0-100%)
            int16_t pcm_sample = (int16_t)(sinf(2.0f * M_PI * freq * t) * scale);
            
            // Output sample to BOTH Left and Right channels for MAX98357A SD_MODE compatibility
            stereo_buffer[i * 2]     = pcm_sample; // Left channel
            stereo_buffer[i * 2 + 1] = pcm_sample; // Right channel
        }

        esp_err_t res = i2s_write(I2S_NUM, stereo_buffer, chunk_frames * 2 * sizeof(int16_t), &bytes_written, portMAX_DELAY);
        if (res == ESP_OK) {
            total_bytes_sent += bytes_written;
        } else {
            Serial.printf("[AUDIO TEST ERROR] i2s_write failed with error 0x%X\n", res);
        }

        frame_idx += chunk_frames;
    }

    // i2s_zero_dma_buffer(I2S_NUM);  // Commented out to allow full DMA transmission without buffer truncation
    Serial.printf("[AUDIO TEST COMPLETE] Played 440Hz tone. Total Bytes Written to I2S DMA: %u\n", total_bytes_sent);
}

void initSensors() {
    pinMode(PIN_HCSR04_TRIG, OUTPUT);
    pinMode(PIN_HCSR04_ECHO, INPUT);
    digitalWrite(PIN_HCSR04_TRIG, LOW);

    pinMode(PIN_ESTOP, INPUT_PULLUP);
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, HIGH);

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    Serial.println("[ROVER] Sensors & I2C Bus Initialized.");
}

// ============================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================

void stopMotorsImmediately() {
    #if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(PIN_MOTOR_L_RPWM, 0);
    ledcWrite(PIN_MOTOR_L_LPWM, 0);
    ledcWrite(PIN_MOTOR_R_RPWM, 0);
    ledcWrite(PIN_MOTOR_R_LPWM, 0);
    #else
    ledcWrite(PWM_CHAN_L_RPWM, 0);
    ledcWrite(PWM_CHAN_L_LPWM, 0);
    ledcWrite(PWM_CHAN_R_RPWM, 0);
    ledcWrite(PWM_CHAN_R_LPWM, 0);
    #endif
}

void setMotors(uint8_t cmd, uint8_t speed) {
    if (emergencyStopped || digitalRead(PIN_ESTOP) == HIGH) {
        stopMotorsImmediately();
        return;
    }

    uint8_t l_fwd = 0, l_rev = 0, r_fwd = 0, r_rev = 0;

    switch (cmd) {
        case MOTOR_FORWARD:
            l_fwd = speed; r_fwd = speed;
            break;
        case MOTOR_REVERSE:
            l_rev = speed; r_rev = speed;
            break;
        case MOTOR_SPIN_LEFT:
            l_rev = speed; r_fwd = speed;
            break;
        case MOTOR_SPIN_RIGHT:
            l_fwd = speed; r_rev = speed;
            break;
        case MOTOR_STOP:
        default:
            stopMotorsImmediately();
            return;
    }

    #if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite(PIN_MOTOR_L_RPWM, l_fwd);
    ledcWrite(PIN_MOTOR_L_LPWM, l_rev);
    ledcWrite(PIN_MOTOR_R_RPWM, r_fwd);
    ledcWrite(PIN_MOTOR_R_LPWM, r_rev);
    #else
    ledcWrite(PWM_CHAN_L_RPWM, l_fwd);
    ledcWrite(PWM_CHAN_L_LPWM, l_rev);
    ledcWrite(PWM_CHAN_R_RPWM, r_fwd);
    ledcWrite(PWM_CHAN_R_LPWM, r_rev);
    #endif
}

float readObstacleDistanceCm() {
    digitalWrite(PIN_HCSR04_TRIG, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_HCSR04_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_HCSR04_TRIG, LOW);

    long duration = pulseIn(PIN_HCSR04_ECHO, HIGH, 20000); // 20ms timeout
    if (duration == 0) return -1.0f;
    return (duration * 0.0343f) / 2.0f;
}

void processAudioStream() {
    int packetSize = audioUdp.parsePacket();
    if (packetSize <= 0) return;

    uint8_t packetBuffer[AUDIO_BUFFER_SIZE];
    int len = audioUdp.read(packetBuffer, AUDIO_BUFFER_SIZE);
    if (len < 8) return;

    if (packetBuffer[0] == 'C' && packetBuffer[1] == 'Y') {
        int pcm_len = len - 8;
        if (pcm_len > 0 && pcm_len % 2 == 0) {
            int num_mono_samples = pcm_len / 2;
            static int16_t stereoBuffer[AUDIO_BUFFER_SIZE];
            int max_stereo_samples = (sizeof(stereoBuffer) / sizeof(int16_t)) / 2;
            int process_samples = min(num_mono_samples, max_stereo_samples);

            const int16_t* monoPcm = (const int16_t*)(packetBuffer + 8);
            for (int i = 0; i < process_samples; i++) {
                int16_t sample = monoPcm[i];
                stereoBuffer[i * 2]     = sample; // Left channel
                stereoBuffer[i * 2 + 1] = sample; // Right channel
            }

            size_t bytes_written = 0;
            size_t stereo_bytes = process_samples * 2 * sizeof(int16_t);
            i2s_write(I2S_NUM, stereoBuffer, stereo_bytes, &bytes_written, portMAX_DELAY);
        }
    }
}

// ============================================================
// SETUP & MAIN LOOP
// ============================================================

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n==================================================");
    Serial.println(" CYNEXIS — ROVER ESP32 MAX98357A AUDIO TEST MODE ");
    Serial.println("==================================================");

    initSensors();
    initMotors();

    // Initialize MAX98357A I2S Audio
    if (!initI2S()) {
        Serial.println("[ROVER CRITICAL] I2S Hardware Initialization Failed!");
    } else {
        Serial.println("[ROVER SUCCESS] I2S Hardware Initialized Successfully.");
    }

    #if AUDIO_HARDWARE_TEST
    Serial.println("\n--------------------------------------------------");
    Serial.println(" MODE: AUDIO_HARDWARE_TEST ENABLED");
    Serial.println(" [AUDIO TEST] 440 Hz tone started.");
    Serial.println("--------------------------------------------------\n");
    play440HzTestTone(1000);
    #else
    WiFi.mode(WIFI_STA);
    Serial.println("[WIFI] Connecting to Laptop Hotspot...");

    #if USE_STATIC_IP
    if (!WiFi.config(staticIP, gateway, subnet, primaryDNS, secondaryDNS)) {
        Serial.println("[WIFI ERROR] Static IP Configuration Failed!");
    } else {
        Serial.println("[WIFI] Static IP configuration enabled.");
    }
    #endif

    WiFi.begin(WIFI_SSID, WIFI_PASS);

    // Bounded 3-second non-blocking connection attempt
    uint32_t wifiStartMs = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - wifiStartMs < 3000)) {
        delay(100);
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("[WIFI] Connected to Laptop Hotspot Successfully!");
        Serial.print("[WIFI] Rover IP Address : ");
        Serial.println(WiFi.localIP());
        Serial.print("[WIFI] Gateway          : ");
        Serial.println(WiFi.gatewayIP());
        Serial.print("[WIFI] Subnet           : ");
        Serial.println(WiFi.subnetMask());
        Serial.printf("[WIFI] Signal Strength  : %d dBm\n", WiFi.RSSI());
    } else {
        Serial.println("[WIFI] Connection Timeout. Proceeding in offline ESP-NOW/safety mode.");
    }

    if (esp_now_init() == ESP_OK) {
        esp_now_register_recv_cb(OnDataRecv);
        Serial.println("[ROVER] ESP-NOW Receiver Ready.");
    } else {
        Serial.println("[ROVER ERROR] ESP-NOW Init Failed!");
    }

    audioUdp.begin(AUDIO_UDP_PORT);
    Serial.printf("[ROVER] UDP Audio Listener bound to port %d.\n", AUDIO_UDP_PORT);
    #endif

    currentState = STATE_IDLE;
    Serial.println("[ROVER] Initialization Complete. Entering Main Loop.\n");
}

void loop() {
    uint32_t now = millis();

    #if AUDIO_HARDWARE_TEST
    // In AUDIO_HARDWARE_TEST mode, play 440Hz tone continuously
    static bool toneStartedLogged = false;
    if (!toneStartedLogged) {
        Serial.println("[AUDIO TEST] 440 Hz tone started.");
        toneStartedLogged = true;
    }
    digitalWrite(PIN_STATUS_LED, LOW);
    play440HzTestTone(1000);
    digitalWrite(PIN_STATUS_LED, HIGH);
    #else
    // Check hardware E-Stop pin
    if (digitalRead(PIN_ESTOP) == HIGH) {
        if (!emergencyStopped) {
            emergencyStopped = true;
            stopMotorsImmediately();
            currentState = STATE_EMERGENCY;
        }
    }

    // Communication Watchdog: 500ms timeout
    if (currentState == STATE_MANUAL && (now - lastPacketReceivedMs > COMMS_WATCHDOG_MS)) {
        stopMotorsImmediately();
        currentState = STATE_IDLE;
    }

    processAudioStream();
    #endif

    // Heartbeat LED indicator
    static uint32_t lastBlink = 0;
    if (now - lastBlink > 500) {
        lastBlink = now;
        digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
    }

    delay(2);
}
