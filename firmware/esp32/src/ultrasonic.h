#pragma once
#include <Arduino.h>

class UltrasonicSensor {
public:
    UltrasonicSensor(uint8_t trigPin, uint8_t echoPin);
    void begin();
    float readDistanceCm();
    void sampleBurst(float* buffer, size_t count);

private:
    uint8_t _trigPin;
    uint8_t _echoPin;
};
