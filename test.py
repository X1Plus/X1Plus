#!/usr/bin/python
"""
Released under the MIT License
Copyright 2015 MrTijn/Tijndagamer
"""
import sys
# Import the MPU6050 class from the MPU6050.py file
from mpu import MPU6050
from time import sleep
import pyftdi.i2c
i2c = pyftdi.i2c.I2cController()
i2c.configure('ftdi://ftdi:232h:0:1/1', frequency=1152500)
sensor = i2c.get_port(0x68)


from time import sleep

# Create a new instance of the MPU6050 class
# sensor = MPU6050(0x68)

while True:
    accel_data = sensor.get_accel_data()
    gyro_data = sensor.get_gyro_data()
    temp = sensor.get_temp()

    print("Accelerometer data")
    print("x: " + str(accel_data['x']))
    print("y: " + str(accel_data['y']))
    print("z: " + str(accel_data['z']))

    print("Gyroscope data")
    print("x: " + str(gyro_data['x']))
    print("y: " + str(gyro_data['y']))
    print("z: " + str(gyro_data['z']))

    print("Temp: " + str(temp) + " C")
    sleep(0.5)