import json
import subprocess
import os
import time
import re
import sys
import math
import argparse
	
#### Speed adjustment macro for X1Plus
#### Usage:
#### 1) Set speed to value between 30 and 180:
#### python3 speed_ramp.py --speed 100
#### 2) incrementally adjust speed between target values 
#### python3 speed_ramp.py --speed 100 --rampto 180
#### Parameters calculated with trendlines fit to Bambu's 
#### speed adjustment parameters
##########################################################

def speed_adjust(speed_percentage):
	if speed_percentage is None:
		return
	if speed_percentage < 30 or speed_percentage > 180:
		speed_percentage = 100
	speed_fraction = speed_interp['speed_fraction'](speed_percentage)
	acceleration_magnitude = speed_interp['acceleration_magnitude'](speed_fraction)
	feedrate = speed_interp['feed_rate'](speed_percentage)
	gcode = acc_magnitude(acceleration_magnitude)
	gcode += feed_rate(feedrate)
	gcode += timeline(speed_fraction)
	return gcode
    
speed_interp = {
    'speed_fraction': lambda speed_percentage: math.floor(10000 / speed_percentage) / 100, # speed fraction (inverse of speed %) = R 
    'acceleration_magnitude': lambda speed_fraction: math.exp((speed_fraction - 1.0191) / -0.814), # exponential trend: acceleration magnitude vs. speed fraction
    'feed_rate': lambda speed_percentage: (0.00006426) * speed_percentage ** 2 + (-0.002484) * speed_percentage + 0.654 # polynomial, feed rate vs speed %
    #'level': lambda acceleration_magnitude: (1.549 * acceleration_magnitude ** 2 - 0.7032 * acceleration_magnitude + 4.0834) #polynomial
}
def acc_magnitude(K):
	return f"M204.2 K{K:.2f}\n"
	
def feed_rate(K):
	return f"M220 K{K:.2f}\n"
	
def timeline(R):
	return f"M73.2 R{R}\n"
	
def send_gcode(gcode_line, sequence_id):
	json_payload = json.dumps({
		"print": {
			"command": "gcode_line",
			"sequence_id": sequence_id,
			"param": gcode_line
		}
	})
	mqtt_pub(json_payload)

def mqtt_pub(message):
    command = f"source /usr/bin/mqtt_access.sh; mqtt_pub '{message}'"
    try:
        subprocess.run(command, shell=True, check=True, executable='/bin/bash',
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")

def speed_ramp(start, end, step, duration):
	current = start
	if end < start and step > 0:
		step = -step
	
	print(f"Ramping from {start} to {end}, step {current} of {step}.\n")
	while (current <= end and step > 0) or (current >= end and step < 0):
		gcodes = speed_adjust(current)
		print(f"Ramping {current} to {end}\n{gcodes}")
		send_gcode(gcodes, 0)
		time.sleep(duration)
		current += step
		
			
def main(args):
	if args.rampto:
		step = int(input("Enter a step size (>= 2)\n"))
		dt = int(input("Enter a time interval (sec) to wait between steps\n"))
		speed_ramp(args.speed, args.rampto, step, dt)
	else:
		send_gcode(speed_adjust(args.speed), 0)

	
if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Control the speed of a machine using G-code.")
	parser.add_argument('-s', '--speed', type=int, help="Enter a speed between 30 to 180%")
	parser.add_argument('-r', '--rampto', type=int, help="Enter a target ramp speed between 30 to 180%")
	
	args = parser.parse_args()
	main(args)
	