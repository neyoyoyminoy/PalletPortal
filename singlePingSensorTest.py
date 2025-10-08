import Jetson.GPIO as GPIO
import time

PIN = 15
GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIN, GPIO.IN)

start_time = 0
GPIO.remove_event_detect(PIN)

def measure_pulse():

    GPIO.wait_for_edge(PIN, GPIO.RISING)
    start = time.monotonic_ns()

    GPIO.wait_for_edge(PIN, GPIO.FALLING)
    end = time.monotonic_ns()



    pulse_width_us = (end - start) / 1000.0
    return pulse_width_us


try:

    print("measuring mb1040 PWM signal")
    while True:
        width_us = measure_pulse()
        distance_in = width_us / 147.0
        distance_cm = distance_in * 2.54
        print(f"Pulse: {width_us:.1f} | Distance: {distance_in:.2f} in ({distance_cm:.2f} cm)")

except KeyboardInterrupt:
    print("Exiting")

finally:
    GPIO.cleanup()
