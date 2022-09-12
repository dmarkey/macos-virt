#!/usr/bin/python3 -u
import json
import os
import subprocess

import psutil
import serial
import time
time.sleep(3)
while True:
    try:
        ser = serial.Serial("/dev/hvc1")
    except Exception:
        time.sleep(.5)
    else:
        break


def send_json_message(message, ser):
    dumped = json.dumps(message)
    ser.write((dumped + "\r\n").encode())


def send_status(ser):
    interfaces = psutil.net_if_addrs().keys()
    main_interface = "enp0s1"
    if "eth0" in interfaces:
        main_interface = "eth0"

    output = {
        "cpu_count": psutil.cpu_count(),
        "cpu_usage": psutil.cpu_percent(),
        "root_fs_usage": psutil.disk_usage("/").percent,
        "mounts": open("/proc/mounts").read(),
        "status": "running",
        "uptime": int(time.time() - psutil.boot_time()),
        "processes": len(psutil.pids()),
        "network_addresses": [
            [x.address, x.netmask]
            for x in psutil.net_if_addrs()[main_interface]
            if x.family.name == "AF_INET"
        ],
        "memory_usage": psutil.virtual_memory().percent,
    }
    send_json_message(output, ser)


send_json_message({"status": "initializing"}, ser)

try:
    subprocess.check_output(args=["cloud-init", "status", "--wait"])
    send_json_message({"status": "initialization_complete"}, ser)
except subprocess.CalledProcessError:
    send_json_message({"status": "initialization_error"}, ser)

send_status(ser)
ser.close()

while True:
    try:
        ser = serial.Serial("/dev/hvc1", timeout=10)
        incoming = ser.readline()
        command_parsed = json.loads(incoming)
        message_type = command_parsed.pop("message_type", "None")
        if message_type == "poweroff":
            print("Powering off")
            os.system("poweroff")
        if message_type == "time_update":
            print("Updating the time")
            os.system(f'date +%s -s @{command_parsed["time"]}')
        if message_type == "status":
            print("Sending status")
            send_status(ser)
    except:
        time.sleep(.5)
        pass
