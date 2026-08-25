#pragma once
#include <Arduino.h>

class FloatSwitch {
public:
    FloatSwitch(uint8_t pin, bool activeLow = true);
    void begin();
    bool isTriggered();

private:
    uint8_t _pin;
    bool _activeLow;
};
