#include "float_switch.h"

FloatSwitch::FloatSwitch(uint8_t pin, bool activeLow)
    : _pin(pin), _activeLow(activeLow) {}

void FloatSwitch::begin() {
    pinMode(_pin, _activeLow ? INPUT_PULLUP : INPUT_PULLDOWN);
}

bool FloatSwitch::isTriggered() {
    int state = digitalRead(_pin);
    return _activeLow ? (state == LOW) : (state == HIGH);
}
