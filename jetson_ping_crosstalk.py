"""
Dual MB1040 Ultrasonic Sensor Test – jetson orin nano
this code has been adapted from the crosstalk_filteringv2.
"""

import Jetson.GPIO as GPIO
import time
import statistics

# --- Pin assignments (BOARD numbering) ---
# for jetson we need 
SENSOR1_PIN = 15
SENSOR2_PIN = 32

GPIO.setmode(GPIO.BOARD)
GPIO.setup(SENSOR1_PIN, GPIO.IN)
GPIO.setup(SENSOR2_PIN, GPIO.IN)

# --- Sensor limits ---
HARD_MIN_IN = 6.0    # below this = impossible
SOFT_MIN_IN = 13.0   # below this, smooth to last valid
MAX_IN = 254.0       # max reliable distance

# Keep track of last valid reading for smoothing
last_valid = {SENSOR1_PIN: None, SENSOR2_PIN: None}

def measure_pulse(pin):
    """Measure one PWM pulse width (µs) on the given GPIO pin."""
    GPIO.wait_for_edge(pin, GPIO.RISING)
    start = time.monotonic_ns()
    GPIO.wait_for_edge(pin, GPIO.FALLING)
    end = time.monotonic_ns()
    return (end - start) / 1000.0  # µs

def read_distance(pin, label, samples=5):
    """Read several pulses, average valid results, print distance."""
    global last_valid
    distances = []
    for _ in range(samples):
        width_us = measure_pulse(pin)
        distance_in = width_us / 147.0  # per datasheet
        if HARD_MIN_IN <= distance_in <= MAX_IN:
            distances.append(distance_in)
        time.sleep(0.05)  # small gap between samples

    if distances:
        avg_in = statistics.mean(distances)

        # Apply soft lower limit smoothing
        if avg_in < SOFT_MIN_IN:
            if last_valid[pin] is not None:
                # Smooth: average with last valid
                avg_in = (avg_in + last_valid[pin]) / 2.0
            # else: no last value, use as-is (might be slightly unstable)

        last_valid[pin] = avg_in
        avg_cm = avg_in * 2.54
        print(f"{label} → {avg_in:.2f} in ({avg_cm:.2f} cm)")

    elif last_valid[pin] is not None:
        # Reuse last valid reading
        avg_in = last_valid[pin]
        avg_cm = avg_in * 2.54
        print(f"{label} → Using last valid reading ({avg_in:.2f} in / {avg_cm:.2f} cm)")

    else:
        print(f"{label} → Out of range")

try:
    print("Alternating MB1040 readings every 3 s with soft lower limit smoothing...")
    while True:
        # --- Sensor 1 ---
        read_distance(SENSOR1_PIN, "Sensor 1")
        time.sleep(0.5)   # quiet time before switching

        # --- Wait 3 s before Sensor 2 ---
        time.sleep(3.0)

        # --- Sensor 2 ---
        read_distance(SENSOR2_PIN, "Sensor 2")
        time.sleep(0.5)

        # --- Wait 3 s before switching back ---
        time.sleep(3.0)

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    GPIO.cleanup()
