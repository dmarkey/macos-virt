import getpass
import gzip
import os
import glob
import pathlib
import random
import shutil
import subprocess
import tempfile
import time
from io import BytesIO
from subprocess import check_output
import pycdlib
import serial
import fs
import typer
import xdg as xdg
import json
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich import print

import yaml
from rich.progress import track

from macos_virt.profiles.registry import registry
from macos_virt.constants import (DISK_FILENAME, BOOT_DISK_FILENAME,
                                  CLOUDINIT_ISO_NAME)

MODULE_PATH = os.path.dirname(__file__)

BASE_PATH = os.path.join(xdg.xdg_config_home(), "macos-virt/vms")

pathlib.Path(BASE_PATH).mkdir(parents=True, exist_ok=True)
MB = 1024 * 1024

KEY_PATH = os.path.join(xdg.xdg_config_home(),
                        "macos-virt/macos-virt-identity")
KEY_PATH_PUBLIC = os.path.join(xdg.xdg_config_home(),
                               "macos-virt/macos-virt-identity.pub")

RUNNER_PATH = os.path.join(MODULE_PATH, "macos_virt_runner/macos_virt_runner")
RUNNER_PATH_ENTITLEMENTS = os.path.join(MODULE_PATH, "macos_virt_runner/"
                                                     "macos_virt_runner.entitlements")


class BaseError(typer.Exit):
    code = 1


class DuplicateVMException(BaseError):
    pass


class VMDoesntExist(BaseError):
    pass


class VMHasNoAssignedAddress(BaseError):
    pass


class VMRunning(BaseError):
    pass


class VMNotRunning(BaseError):
    pass


class InternalErrorException(BaseError):
    pass


class VMStarted(typer.Exit):
    code = 0


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

    def is_provisioned(self):
        return self.configuration.get("status") == "running"

    def get_ip_address(self):
        ip_address = self.configuration.get("ip_address", None)
        if not ip_address:
            raise VMHasNoAssignedAddress("VM has no assigned IP address")
        return ip_address

    def file_locations(self):
        return (
            os.path.join(self.vm_directory, DISK_FILENAME),
            os.path.join(self.vm_directory, BOOT_DISK_FILENAME),
            os.path.join(self.vm_directory, CLOUDINIT_ISO_NAME)
        )

    def shell(self, *args):
        ip_address = self.get_ip_address()
        os.execl("/usr/bin/ssh", "/usr/bin/ssh",
                 "-oStrictHostKeyChecking=no",
                 "-i", KEY_PATH, ip_address, *args)

    @staticmethod
    def get_ssh_public_key():
        if not os.path.exists(os.path.expanduser(KEY_PATH)):
            pathlib.Path(os.path.expanduser("~/.ssh/")).mkdir(exist_ok=True)
            check_output(["ssh-keygen", "-f", KEY_PATH, "-N", ""])
        return open(KEY_PATH_PUBLIC).read()

    def start(self):
        if self.is_running():
            raise VMRunning(f"VM {self.name} is already running.")
        elif self.configuration['status'] == "uninitialized":
            self.provision()
        elif self.configuration['status'] == "running":
            self.boot_normally()

    @property
    def get_status_port(self):
        return serial.Serial(os.path.join(self.vm_directory, "control"),
                             timeout=300)

    def send_message(self, message):
        ser = self.get_status_port
        dumped = json.dumps(message)
        ser.write((dumped + "\r\n").encode())

    def receive_message(self):
        ser = self.get_status_port

    def stop(self):
        if not self.is_running():
            raise VMNotRunning("VM is not running")
        self.send_message({'message_type': "poweroff"})

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
        try:
            kern = gzip.open(kernel)
            uncompressed = kern.read()
            kern.close()
            with open(kernel, "wb") as f:
                f.write(uncompressed)
        except gzip.BadGzipFile:
            pass
        process = subprocess.Popen(
            [RUNNER_PATH,
             "--pidfile=./pidfile",
             f"--kernel={kernel}",
             "--cmdline=console=hvc0 irqfixup"
             " quiet root=/dev/vda",
             f"--initrd={initrd}",
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
        try:
            serial.Serial(os.path.join(self.vm_directory, "control"),
                          timeout=300)
        except serial.serialutil.SerialException:
            returncode = process.wait()

            raise InternalErrorException(f"VM Failed to start. "
                                         f"Return code {returncode}")
        subprocess.run(
            f'/usr/bin/screen -dm -S console-{self.name} {self.vm_directory}/console',
            shell=True)
        self.watch_initialization()

    def print_status(self, status):
        grid = Table.grid()
        grid.add_column()
        grid.add_column()
        grid.add_row("CPU Count", str(status['cpu_count']))
        grid.add_row("CPU Usage", str(status['cpu_usage']))
        grid.add_row("Memory Usage", str(status['memory_usage']))
        grid.add_row("Root Filesystem Usage", str(status['root_fs_usage']))
        grid.add_row("Network Addresses", str(status['network_addresses']))
        print(grid)

    def save_configuration_to_disk(self):
        with open(os.path.join(self.vm_directory, "vm.json"),
                  "w") as f:
            json.dump(self.configuration, f)

    def update_vm_status(self, status):
        console = Console()
        status_string = status['status']
        if status_string == "initializing":
            text = Text("VM Booted, waiting for initialization")
            text.stylize("bold magenta")
            console.print(text)
        if status_string == "initialization_complete":
            text = Text("Initialization Complete.")
            text.stylize("bold green")
            console.print(text)
        if status_string == "initialization_error":
            text = Text("VM Initialization Error")
            text.stylize("bold red")
            console.print(text)
        self.configuration['status'] = status_string
        self.save_configuration_to_disk()
        if status_string == "running":
            self.print_status(status)
            if "network_addresses" in status:
                for address, netmask in status['network_addresses']:
                    if address.startswith("192.168"):
                        self.configuration['ip_address'] = address
            self.save_configuration_to_disk()
            raise VMStarted("VM Successfully started.")

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

    def boot_normally(self):
        vm_disk, vm_boot_disk, cloudinit_iso = self.file_locations()
        boot_filesystem = fs.open_fs(f"fat://{vm_boot_disk}?read_only=true")
        kernel, initrd = self.profile.get_boot_files_from_filesystem(
            boot_filesystem)
        kernel_file = boot_filesystem.readbytes(kernel)
        initrd_file = boot_filesystem.readbytes(initrd)
        with tempfile.NamedTemporaryFile(delete=True) as kernel:
            kernel.write(kernel_file)
            with tempfile.NamedTemporaryFile(delete=True) as initrd:
                initrd.write(initrd_file)
                self.boot_vm(kernel.name, initrd.name)

    def watch_initialization(self):
        console = Console()
        text = Text("VM Started.")
        text.stylize("bold gray")
        console.print(text)
        port = self.get_status_port

        while True:
            status = json.loads(port.readline().decode())
            self.update_vm_status(status)


class Controller:

    @classmethod
    def get_valid_vms(cls):
        return [os.path.basename(os.path.dirname(x)) for x in
                glob.glob(f"{BASE_PATH}/*/vm.json")]

    @classmethod
    def start(cls, profile, name, cpus, memory, disk_size):
        if name in cls.get_valid_vms():
            vm_directory = get_vm_directory(name)
            vm = VMManager(vm_directory)
            if vm.is_provisioned():
                vm.start()
                return

            raise DuplicateVMException(f"VM {name} already exists")
        else:
            configuration = {
                "memory": memory,
                "cpus": cpus,
                "disk_size": disk_size,
                "profile": profile,
                "ip_address": None,
                "mac_address": "52:54:00:%02x:%02x:%02x" % (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                ),
                "status": "uninitialized"
            }
            with open(os.path.join(get_vm_directory(name), "vm.json"),
                      "w") as f:
                json.dump(configuration, f)
            vm_directory = get_vm_directory(name)
            vm = VMManager(vm_directory)
            vm.start()

    @classmethod
    def delete(cls, name):
        if name not in cls.get_valid_vms():
            raise VMDoesntExist(f"VM {name} doesnt exist")
        vm = VMManager(get_vm_directory(name))
        if vm.is_running():
            raise VMRunning(f"VM {name} is running,"
                            f" please stop before deleting")
        shutil.rmtree(get_vm_directory(name))

    @classmethod
    def stop(cls, name):
        vm = VMManager(get_vm_directory(name))
        vm.stop()

    @classmethod
    def shell(cls, name, *args):
        if name not in cls.get_valid_vms():
            raise VMDoesntExist(f"VM {name} doesnt exist")
        vm = VMManager(get_vm_directory(name))
        if not vm.is_running():
            raise VMNotRunning(f"VM {name} is not running,")
        vm.shell(*args)

    @classmethod
    def setup(cls):
        check_output(["codesign", "-s", "-", "--entitlements",
                      RUNNER_PATH_ENTITLEMENTS, RUNNER_PATH])
