#!env python3
import tarfile
import urllib.request
import subprocess
import time
import gzip
import os
import pycdlib
from io import BytesIO
import yaml
import serial
import json
import getpass
from os import path

ser = None


def send_json_message(message):
    dumped = json.dumps(message)
    ser.write((dumped + "\r\n").encode())


CLOUD_INIT_DATA = {
    "package_update": True,
    "package_upgrade": True,
    "packages": ['python3-psutil'],
    'users': ['default',
              {'name': getpass.getuser(),
               'lock_passwd': False,
               'gecos': getpass.getuser(),
               'groups': ['adm',
                          'audio',
                          'cdrom',
                          'dialout',
                          'dip',
                          'floppy',
                          'lxd',
                          'netdev',
                          'plugdev',
                          'sudo',
                          'video'],
               'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
               'shell': '/bin/bash',
               'plain_text_passwd': 'password',
               'ssh-authorized-keys': [
                   open(f"{path.expanduser('~/.ssh/macos-virt.pub')}").read()]}],
    'runcmd': [
        'apt remove -y irqbalance'],
    'network': {'version': 2,
                'renderer': 'networkd',
                'ethernets': {'enp0s1': {'dhcp4': True}}}}

if "write_files" in CLOUD_INIT_DATA:
    write_files = CLOUD_INIT_DATA['write_files']
else:
    write_files = []
write_files.append({
    "content": open("service.py").read(),
    "path": "/root/test.py"
})
write_files.append({
    "content": open("macos-virt.service").read(),
    "path": "/etc/systemd/system/macos-virt-service.service"
})
write_files.append({
    "content": open("install_boot.sh").read(),
    "path": "/root/install_boot.sh"
})
CLOUD_INIT_DATA['write_files'] = write_files

if "runcmd" in CLOUD_INIT_DATA:
    runcmd = []
else:
    runcmd = CLOUD_INIT_DATA["runcmd"]

runcmd.insert(0,
              ["sh", "/root/install_boot.sh"]
              )

runcmd.insert(0,
              ["systemctl", "enable", "macos-virt-service.service", "--now"]
              )

runcmd.insert(0,
              ['systemctl', 'daemon-reload']
              )
CLOUD_INIT_DATA['runcmd'] = runcmd

MB = 1024 * 1024
"""urllib.request.urlretrieve(
    "https://cloud-images.ubuntu.com/releases/focal/release/unpacked/ubuntu-20.04-server-cloudimg-amd64-vmlinuz-generic",
    "kernel")
urllib.request.urlretrieve(
    "https://cloud-images.ubuntu.com/releases/focal/release/unpacked/ubuntu-20.04-server-cloudimg-amd64-initrd-generic",
    "initrd")
urllib.request.urlretrieve(
    "https://cloud-images.ubuntu.com/releases/focal/release/ubuntu-20.04-server-cloudimg-amd64.tar.gz",
    "image.tar.gz")"""
tf = tarfile.open("image.tar.gz")
tf.extractall()
tf.close()

MB_PAD = b"\0" * MB
try:
    kern = gzip.open("kernel")
    uncompressed = kern.read()
    kern.close()
    with open("kernel", "wb") as f:
        f.write(uncompressed)
except gzip.BadGzipFile:
    pass

with open("boot.img", "wb") as f:
    [f.write(MB_PAD) for x in range(256)]

size = os.path.getsize("focal-server-cloudimg-amd64.img")

chunks = int(((MB * 10000) - size) / MB)
with open("focal-server-cloudimg-amd64.img", "ba") as f:
    [f.write(MB_PAD) for x in range(chunks)]

iso = pycdlib.PyCdlib()
iso.new(interchange_level=4,
        joliet=True,
        rock_ridge='1.09',
        vol_ident='cidata')
userdata = ("#cloud-config\n" + yaml.dump(CLOUD_INIT_DATA)).encode()

iso.add_fp(BytesIO(),
           0,
           '/METADATA.;1',
           rr_name="meta-data",
           joliet_path='/meta-data',
           )

iso.add_fp(BytesIO(userdata),
           len(userdata),
           '/USERDATA.;1',
           rr_name="user-data",
           joliet_path='/user-data',
           )
iso.write("test.iso")
iso.close()

subprocess.Popen(["vmcli",
                  "--pidfile=./pidfile",
                  "--kernel=./kernel",
                  "--cmdline=console=hvc0 root=/dev/vda",
                  "--initrd=./initrd",
                  "--cdrom=./test.iso",
                  "--disk=./focal-server-cloudimg-amd64.img",
                  "--disk=./boot.img",
                  "--network=aa:bb:cc:dd:ee:ff@nat",
                  "--cpu-count=2",
                  "--memory-size=1024",
                  "--console-symlink=console",
                  "--control-symlink=control",
                  ])
time.sleep(10)
ser = serial.Serial("./control", timeout=300)
print(ser.readline())
print(ser.readline())
print(ser.readline())
# send_json_message({"message_type": "poweroff"})
