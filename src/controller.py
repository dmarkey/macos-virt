import getpass
import os
import glob
import pathlib
import random
import shutil
import subprocess
import time
from io import BytesIO
from subprocess import check_output
import pycdlib
import serial

import xdg as xdg
import json

import yaml
from rich.progress import track

from profiles.registry import registry
from constants import (DISK_FILENAME, BOOT_DISK_FILENAME, CLOUDINIT_ISO_NAME,
                       KERNAL_FILENAME, INITRD_FILENAME)

BASE_PATH = os.path.join(xdg.xdg_config_home(), "macos-virt/vms")

pathlib.Path(BASE_PATH).mkdir(parents=True, exist_ok=True)
MB = 1024 * 1024

KEY_PATH = os.path.expanduser("~/.ssh/macos-virt")
KEY_PATH_PUBLIC = os.path.expanduser("~/.ssh/macos-virt")


class DuplicateVMException(Exception):
    pass


class VMDoesntExist(Exception):
    pass


class VMRunning(Exception):
    pass


def get_vm_directory(name):
    path = os.path.join(BASE_PATH, name)
    pathlib.Path(path).mkdir(exist_ok=True)
    return path


class VMManager:
    def __init__(self, vm_directory):
        self.vm_directory = vm_directory
        self.name = os.path.basename(vm_directory)
        self.configuration = json.load(
            open(os.path.join(vm_directory, "vm.json")))
        self.profile = registry.get_profile(self.configuration['profile'])

    def file_locations(self):
        return (
            os.path.join(self.vm_directory, DISK_FILENAME),
            os.path.join(self.vm_directory, BOOT_DISK_FILENAME),
            os.path.join(self.vm_directory, CLOUDINIT_ISO_NAME)
        )

    @staticmethod
    def get_ssh_public_key():
        if not os.path.exists(os.path.expanduser(KEY_PATH)):
            pathlib.Path(os.path.expanduser("~/.ssh/")).mkdir(exist_ok=True)
            check_output(["ssh-keygen", "-f", KEY_PATH, "-N", ""])
        return open(KEY_PATH_PUBLIC).read()

    def start(self):
        if self.is_running():
            raise VMRunning(f"VM {self.name} is already running.")
        if self.configuration['status'] == "uninitialized":
            self.provision()

    def provision(self):
        vm_disk, vm_boot_disk, cloudinit_iso = self.file_locations()
        kernel, initrd, disk, = self.profile.file_locations()
        check_output(["cp", "-c", disk, vm_disk])
        mb_padding = b"\0" * MB
        with open(vm_boot_disk, "wb") as f:
            for _ in track(range(256), description="Creating Boot image..."):
                f.write(mb_padding)
        size = os.path.getsize(vm_disk)
        chunks = int(((MB * self.configuration['disk_size']) - size) / MB)
        with open(vm_disk, "ba") as f:
            for n in track(range(chunks),
                           description="Expanding Root Image..."):
                f.write(mb_padding)
        username = getpass.getuser()
        ssh_key = self.get_ssh_public_key()
        cloudinit_content = self.profile.render_cloudinit_data(
            username, ssh_key)
        iso = pycdlib.PyCdlib()
        iso.new(interchange_level=4,
                joliet=True,
                rock_ridge='1.09',
                vol_ident='cidata')
        userdata = ("#cloud-config\n" + yaml.dump(cloudinit_content))
        iso.add_fp(BytesIO(),
                   0,
                   '/METADATA.;1',
                   rr_name="meta-data",
                   joliet_path='/meta-data',
                   )

        iso.add_fp(BytesIO(userdata.encode()),
                   len(userdata),
                   '/USERDATA.;1',
                   rr_name="user-data",
                   joliet_path='/user-data',
                   )
        iso.write(cloudinit_iso)
        iso.close()
        self.boot_vm(kernel, initrd)

    def boot_vm(self, kernel, initrd):

        subprocess.Popen(["vmcli",
                          "--pidfile=./pidfile",
                          f"--kernel=./{kernel}",
                          "--cmdline=console=hvc0 root=/dev/vda",
                          f"--initrd=./{initrd}",
                          f"--cdrom=./{CLOUDINIT_ISO_NAME}",
                          f"--disk={DISK_FILENAME}",
                          f"--disk={BOOT_DISK_FILENAME}",
                          f"--network={self.configuration['mac_address']}@nat",
                          f"--cpu-count={self.configuration['cpus']}",
                          f"--memory-size={self.configuration['memory']}",
                          "--console-symlink=console",
                          "--control-symlink=control",
                          ], cwd=self.vm_directory)
        time.sleep(5)
        ser = serial.Serial(os.path.join(self.vm_directory, "control"),
                            timeout=300)
        for x in range(3):
            status = json.loads(ser.readline().decode())['status']
            self.update_vm_status(status)

    def update_vm_status(self, status):
        self.configuration['status'] = status
        with open(os.path.join(self.vm_directory, "vm.json"),
                  "w") as f:
            json.dump(self.configuration, f)

    def is_running(self):
        try:
            pid = open(
                os.path.join(self.vm_directory, "pidfile")).read()
            try:
                os.kill(int(pid), 0)
            except OSError:
                return False
            else:
                return True
        except FileNotFoundError:
            return False


class Controller:

    @classmethod
    def get_valid_vms(cls):
        return [os.path.basename(os.path.dirname(x)) for x in
                glob.glob(f"{BASE_PATH}/*/vm.json")]

    @classmethod
    def start(cls, profile, name, cpus, memory, disk_size, cloudinit):
        if name in cls.get_valid_vms():
            raise DuplicateVMException(f"VM {name} already exists")
        configuration = {
            "memory": memory,
            "cpus": cpus,
            "disk_size": disk_size,
            "profile": profile,
            "mac_address": ':'.join('%02x' % random.randint(0, 255)
                                    for x in range(6)),
            "status": "uninitialized"
        }
        vm_directory = get_vm_directory(name)
        with open(os.path.join(get_vm_directory(name), "vm.json"),
                  "w") as f:
            json.dump(configuration, f)
        VMManager(vm_directory).start()

    @classmethod
    def delete(cls, name):
        if name not in cls.get_valid_vms():
            raise VMDoesntExist(f"VM {name} doesnt exist")
        vm = VMManager(get_vm_directory(name))
        if vm.is_running():
            raise VMRunning(f"VM {name} is running,"
                            f" please stop before deleting")
        shutil.rmtree(get_vm_directory(name))
