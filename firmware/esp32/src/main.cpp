#include <Arduino.h>
#include <ArduinoJson.h>
#include "ultrasonic.h"
#include "float_switch.h"

// Configuration constants
static const char* SENSOR_ID = "S001";
static const char* BOOT_ID = "boot-001";
static const uint8_t TRIG_PIN = 5;
static const uint8_t ECHO_PIN = 18;
static const uint8_t FLOAT_PIN = 19;
static const size_t BURST_SAMPLE_COUNT = 5;
static const unsigned long TELEMETRY_INTERVAL_MS = 10000;

UltrasonicSensor ultrasonic(TRIG_PIN, ECHO_PIN);
FloatSwitch floatSwitch(FLOAT_PIN, true);

uint32_t sequenceNumber = 0;
unsigned long lastTelemetryTime = 0;

void setup() {
    Serial.begin(115200);
    ultrasonic.begin();
    floatSwitch.begin();
    Serial.println("ESP32 Flood Sensor Node Initialized.");
}

void loop() {
    unsigned long now = millis();
    if (now - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
        lastTelemetryTime = now;
        sequenceNumber++;

        float burstSamples[BURST_SAMPLE_COUNT];
        ultrasonic.sampleBurst(burstSamples, BURST_SAMPLE_COUNT);
        bool floatState = floatSwitch.isTriggered();

        StaticJsonDocument<256> doc;
        doc["sensor_id"] = SENSOR_ID;
        doc["boot_id"] = BOOT_ID;
        doc["sequence"] = sequenceNumber;
        doc["measured_at_seconds"] = (int)(now / 1000);
        doc["received_at_seconds"] = (int)(now / 1000);

        JsonArray samplesArray = doc.createNestedArray("distance_samples_cm");
        for (size_t i = 0; i < BURST_SAMPLE_COUNT; ++i) {
            if (burstSamples[i] > 0) {
                samplesArray.add(burstSamples[i]);
            } else {
                samplesArray.add((char*)nullptr);
            }
        }
        doc["float_triggered"] = floatState;

        serializeJson(doc, Serial);
        Serial.println();
    }
}
