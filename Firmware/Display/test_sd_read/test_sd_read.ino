/*
 * CYNEXIS TF / microSD Card Read-Only Diagnostics Sketch
 * Board: ESP32 Dev Module
 * Display: 2.4" 240x320 SPI TFT (ILI9341 + XPT2046 Touch + SD Slot)
 *
 * ABSOLUTE SAFETY GUARANTEE:
 * - Read-only operation ONLY (FILE_READ mode).
 * - NO file creation, NO writing, NO deleting, NO formatting, NO renaming.
 */

#include <Arduino.h>
#include <SPI.h>
#include <FS.h>
#include <SD.h>

// --- CYNEXIS HARDWARE PIN DEFINITIONS ---
#define TFT_CS     5   // TFT Display Chip Select
#define TOUCH_CS  33   // Touch Controller Chip Select
#define TFT_DC     2   // TFT Data/Command
#define TFT_RST    4   // TFT Reset

#define SD_CS     15   // Dedicated microSD Chip Select
#define SD_MOSI   23   // Shared SPI Bus MOSI
#define SD_MISO   19   // Shared SPI Bus MISO
#define SD_SCK    18   // Shared SPI Bus Clock

// Helper function: Recursively list directories and files safely
void listDirectory(File dir, int numTabs = 0) {
    while (true) {
        File entry = dir.openNextFile();
        if (!entry) {
            break; // No more files in this directory
        }

        for (uint8_t i = 0; i < numTabs; i++) {
            Serial.print("  ");
        }

        if (entry.isDirectory()) {
            Serial.print("/");
            Serial.println(entry.name());
            listDirectory(entry, numTabs + 1);
        } else {
            Serial.print("  ");
            Serial.print(entry.name());
            Serial.print(" \t(");
            Serial.print(entry.size());
            Serial.println(" bytes)");
        }
        entry.close();
    }
}

// Helper function: Safely preview first few lines of ONE small text file
void previewSmallTextFile(File dir) {
    static bool filePreviewed = false;
    if (filePreviewed) return;

    while (true) {
        File entry = dir.openNextFile();
        if (!entry) break;

        if (!entry.isDirectory() && !filePreviewed) {
            String filename = String(entry.name());
            // Check if file is small (< 4KB) and has readable text extension
            if (entry.size() > 0 && entry.size() < 4096 && 
               (filename.endsWith(".txt") || filename.endsWith(".TXT") || 
                filename.endsWith(".log") || filename.endsWith(".LOG") || 
                filename.endsWith(".cfg") || filename.endsWith(".csv"))) {
                
                Serial.println("\n----------------------------------------");
                Serial.printf("Previewing small text file: /%s (%d bytes)\n", filename.c_str(), entry.size());
                Serial.println("----------------------------------------");
                
                int lineCount = 0;
                while (entry.available() && lineCount < 10) {
                    String line = entry.readStringUntil('\n');
                    Serial.println(line);
                    lineCount++;
                }
                if (entry.available()) {
                    Serial.println("... [truncated]");
                }
                Serial.println("----------------------------------------\n");
                filePreviewed = true;
            }
        }
        entry.close();
        if (filePreviewed) break;
    }
}

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000); // Wait for Serial connection

    Serial.println("\n===== CYNEXIS TF CARD TEST =====");

    // STEP 1: Explicitly isolate SPI devices (Deselect TFT and Touch)
    pinMode(TFT_CS, OUTPUT);
    digitalWrite(TFT_CS, HIGH);

    pinMode(TOUCH_CS, OUTPUT);
    digitalWrite(TOUCH_CS, HIGH);

    pinMode(SD_CS, OUTPUT);
    digitalWrite(SD_CS, HIGH);

    // STEP 2: Initialize SPI Bus on ESP32 Pins
    SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

    // STEP 3: Mount SD Card (SPI frequency set to 4MHz for rock-solid signal integrity)
    if (!SD.begin(SD_CS, SPI, 4000000)) {
        Serial.println("SD initialization: FAILED");
        Serial.println("Possible causes:");
        Serial.println("  1. Card not inserted properly.");
        Serial.println("  2. Wiring issue on SD_CS (GPIO 15), MOSI(23), MISO(19), or SCK(18).");
        Serial.println("  3. Unsupported filesystem (e.g. exFAT instead of FAT32).");
        Serial.println("  4. Card capacity > 32GB without FAT32 formatting.");
        Serial.println("===== TEST FAILED =====");
        return;
    }

    Serial.println("SD initialization: OK");

    // STEP 4: Determine Card Type
    uint8_t cardType = SD.cardType();
    Serial.print("Card type: ");
    if (cardType == CARD_MMC) {
        Serial.println("MMC");
    } else if (cardType == CARD_SD) {
        Serial.println("SDSC (Standard Capacity)");
    } else if (cardType == CARD_SDHC) {
        Serial.println("SDHC / SDXC");
    } else {
        Serial.println("UNKNOWN");
    }

    // STEP 5: Calculate and Print Card Size
    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    uint64_t totalBytes = SD.totalBytes() / (1024 * 1024);
    uint64_t usedBytes = SD.usedBytes() / (1024 * 1024);

    Serial.printf("Card size: %llu MB\n", cardSize);
    Serial.printf("Total capacity: %llu MB\n", totalBytes);
    Serial.printf("Used space: %llu MB\n", usedBytes);
    Serial.println();

    // STEP 6: Safely list all directories and files recursively
    Serial.println("Filesystem Root Directory Listing:");
    File root = SD.open("/");
    if (root) {
        listDirectory(root);
        root.close();
    } else {
        Serial.println("Failed to open root directory /");
    }

    // STEP 7: Optional safe read preview of a small text file
    File rootForPreview = SD.open("/");
    if (rootForPreview) {
        previewSmallTextFile(rootForPreview);
        rootForPreview.close();
    }

    Serial.println("===== TEST COMPLETE =====");
}

void loop() {
    // Nothing in loop
    delay(1000);
}
