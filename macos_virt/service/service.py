import json
import os
import subprocess

import psutil
import serial
import time

ser = serial.Serial("/dev/hvc1")


def send_json_message(message):
    dumped = json.dumps(message)
    ser.write((dumped + "\r\n").encode())


def send_status():
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
            for x in psutil.net_if_addrs()["enp0s1"]
            if x.family.name == "AF_INET"
        ],
        "memory_usage": psutil.virtual_memory().percent,
    }
    send_json_message(output)


send_json_message({"status": "initializing"})

try:
    subprocess.check_output(args=["cloud-init", "status", "--wait"])
    send_json_message({"status": "initialization_complete"})
except subprocess.CalledProcessError:
    send_json_message({"status": "initialization_error"})

send_status()

while True:
    incoming = ser.readline()
    command_parsed = json.loads(incoming)
    if command_parsed["message_type"] == "poweroff":
        print("Powering off")
        os.system("poweroff")
    if command_parsed["message_type"] == "time_update":
        print("Updating the time")
        os.system(f'date +%s -s @{command_parsed["time"]}')
    if command_parsed["message_type"] == "status":
        print("Sending status")
        send_status()
