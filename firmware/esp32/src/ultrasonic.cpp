#include "ultrasonic.h"

UltrasonicSensor::UltrasonicSensor(uint8_t trigPin, uint8_t echoPin)
    : _trigPin(trigPin), _echoPin(echoPin) {}

void UltrasonicSensor::begin() {
    pinMode(_trigPin, OUTPUT);
    pinMode(_echoPin, INPUT);
    digitalWrite(_trigPin, LOW);
}

float UltrasonicSensor::readDistanceCm() {
    digitalWrite(_trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(_trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(_trigPin, LOW);

    unsigned long duration = pulseIn(_echoPin, HIGH, 30000); // 30ms timeout (~5m max)
    if (duration == 0) {
        return -1.0f; // Timeout/No echo
    }

    // Speed of sound = 343 m/s = 0.0343 cm/us -> distance = duration * 0.0343 / 2
    return (float)duration * 0.0343f / 2.0f;
}

void UltrasonicSensor::sampleBurst(float* buffer, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        buffer[i] = readDistanceCm();
        delay(20); // 20ms settling time between burst pulses
    }
}
