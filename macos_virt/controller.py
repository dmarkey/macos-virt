import glob
import gzip
import json
import os
import pathlib
import random
import shutil
import subprocess
import tempfile
import time
from io import BytesIO
from subprocess import check_output

import fs
import pycdlib
import serial
import typer
import xdg as xdg
import yaml
from rich import print
from rich.console import Console
from rich.progress import track
from rich.table import Table

from macos_virt.constants import (DISK_FILENAME, BOOT_DISK_FILENAME,
                                  CLOUDINIT_ISO_NAME)
from macos_virt.profiles.registry import registry

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

USERNAME = "macos-virt"

console = Console()


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


class VMExists(BaseError):
    pass


class InternalErrorException(BaseError):
    pass


class ImmutableConfiguration(BaseError):
    pass


class VMStarted(typer.Exit):
    code = 0


def get_vm_directory(name):
    path = os.path.join(BASE_PATH, name)
    pathlib.Path(path).mkdir(exist_ok=True)
    return path


class VMManager:
    def __init__(self, name):
        self.name = name
        self.vm_directory = os.path.join(BASE_PATH, name)
        self.vm_configuration_file = os.path.join(self.vm_directory, "vm.json")
        self.exists = False
        if os.path.exists(self.vm_configuration_file):
            self.exists = True
        self.configuration = {}
        self.profile = None

    def create(self, profile, cpus, memory, disk_size):
        if self.exists:
            raise VMExists(f"VM {self.name} already exists")
        self.configuration = {
            "memory": memory,
            "cpus": cpus,
            "profile": profile,
            "disk_size": disk_size,
            "ip_address": None,
            "status": "uninitialized",
            "mac_address": "52:54:00:%02x:%02x:%02x" % (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            )
        }
        pathlib.Path(self.vm_directory).mkdir(parents=True)
        self.save_configuration_to_disk()
        self.profile = registry.get_profile(self.configuration['profile'])
        self.provision()

    def is_provisioned(self):
        return self.configuration.get("status") == "running"

    def get_ip_address(self):
        self.load_configuration_from_disk()
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

    def shell(self, args, wait=False):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running.")
        ip_address = self.get_ip_address()
        to_spawn = ["/usr/bin/ssh",
                    "-oStrictHostKeyChecking=no", "-i", KEY_PATH, f"{USERNAME}@{ip_address}"]
        if args is not None:
            to_spawn += [args]
        if wait:
            check_output(to_spawn)
            return
        os.execl("/usr/bin/ssh", *to_spawn)

    @staticmethod
    def get_ssh_public_key():
        if not os.path.exists(os.path.expanduser(KEY_PATH)):
            pathlib.Path(os.path.expanduser("~/.ssh/")).mkdir(exist_ok=True)
            check_output(["ssh-keygen", "-f", KEY_PATH, "-N", ""])
        return open(KEY_PATH_PUBLIC).read()

    def start(self):
        if not self.exists:
            raise VMDoesntExist("🤷 VM {self.name} does not exist.")
        self.load_configuration_from_disk()
        if self.is_running():
            raise VMRunning(f"🤷 VM {self.name} is already running.")

        elif self.configuration['status'] == "running":
            return self.boot_normally()

        raise InternalErrorException(f"VM {self.name} is in an unknown state, can't boot.")

    def load_configuration_from_disk(self):
        self.configuration = json.load(open(self.vm_configuration_file))
        self.profile = registry.get_profile(self.configuration['profile'])

    @property
    def get_status_port(self):
        return serial.Serial(os.path.join(self.vm_directory, "control"),
                             timeout=300)

    def send_message(self, message):
        ser = self.get_status_port
        dumped = json.dumps(message)
        ser.write((dumped + "\r\n").encode())

    def stop(self, force=False):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running")
        if force:
            pid = open(
                os.path.join(self.vm_directory, "pidfile")).read()
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
            finally:
                console.print(f":skull: VM  {self.name} terminated by force")
                return

        self.send_message({'message_type': "poweroff"})
        console.print(f":sleeping: Stop request sent to {self.name}")

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
        ssh_key = self.get_ssh_public_key()
        cloudinit_content = self.profile.render_cloudinit_data(
            USERNAME, ssh_key)
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

        check_output(["codesign", "-f", "-s", "-", "--entitlements",
                      RUNNER_PATH_ENTITLEMENTS, RUNNER_PATH])
        arguments = [RUNNER_PATH,
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
                     ]
        process = subprocess.Popen(arguments
                                   , cwd=self.vm_directory)
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
        grid.add_column(width=40)
        grid.add_column(style="bold")
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
        status_string = status['status']
        if status_string == "initializing":
            text = ":hatching_chick: VM has made first contact"
            console.print(text)
        if status_string == "initialization_complete":
            text = ":hatched_chick: Initialization complete"
            console.print(text)
        if status_string == "initialization_error":
            text = ":rotating_light: VM had a problem initializing"
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
        console.print(f":floppy_disk: Booting with Kernel {kernel} and"
                      f" Ramdisk {initrd} from Boot volume")
        kernel_file = boot_filesystem.readbytes(kernel)
        initrd_file = boot_filesystem.readbytes(initrd)
        with tempfile.NamedTemporaryFile(delete=True) as kernel:
            kernel.write(kernel_file)
            with tempfile.NamedTemporaryFile(delete=True) as initrd:
                initrd.write(initrd_file)
                self.boot_vm(kernel.name, initrd.name)

    def watch_initialization(self):
        text = "🥚 VM has been created"

        console.print(text)
        port = self.get_status_port

        while True:
            status = json.loads(port.readline().decode())
            self.update_vm_status(status)

    def delete(self):
        if not self.exists:
            raise VMDoesntExist(f"🤷 VM {self.name} does not exist.")
        if self.is_running():
            raise VMRunning("VM {self.name} is running, please stop it before deleting.")
        shutil.rmtree(self.vm_directory)

    def cp(self, source, destination, recursive=False):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running.")
        args = []
        if source.startswith("vm:"):
            args.append(f"{USERNAME}@{self.get_ip_address()}:{source[3:]}")
            args.append(destination)
        elif destination.startswith("vm:"):
            args.append(source)
            args.append(f"{USERNAME}@{self.get_ip_address()}:{source[3:]}")
        if not args:
            raise InternalErrorException("Copy arguments missing vm: prefix to indicate direction.")
        if recursive:
            args.insert(0, "-r")
        full_args = ["/usr/bin/scp", "-o", "StrictHostKeyChecking=no", "-i", KEY_PATH] + args
        check_output(full_args)

    def mount(self, source, destination):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running.")
        source = os.path.abspath(source)
        if not os.path.isdir(source):
            raise InternalErrorException(f"{source} is not a directory")
        fifo_name = os.path.join(self.vm_directory, f"sshfs-fifo-{os.getpid()}")
        os.mkfifo(fifo_name)
        self.shell(f"sudo mkdir -p {destination} && sudo chown 1000 {destination}", wait=True)

        subprocess.Popen(
            f'nohup sh -c \"< {fifo_name} /usr/libexec/sftp-server | ssh -c aes128-ctr -o Compression=no -o ServerAliveInterval=15 -o ServerAliveCountMax=3 '
            f'-i {KEY_PATH} {USERNAME}@{self.get_ip_address()} '
            f'sshfs -o slave ":{source}" "{destination}" -o uid=1000  > {fifo_name}\" > /dev/null',
            shell=True)

    def update_resources(self, memory, cpus):
        if self.is_running():
            raise VMRunning(f"🤷 VM {self.name} is running, "
                            f"Please shut it down before updating resources.")
        self.load_configuration_from_disk()
        if memory:
            console.print(f":rocket: changing memory from "
                          f"{self.configuration['memory']} to {memory}")
            self.configuration['memory'] = memory
        if cpus:
            self.configuration['cpus'] = cpus
            console.print(f":rocket: changing CPUs from "
                          f"{self.configuration['cpus']} to {cpus}")
        if memory or cpus:
            self.save_configuration_to_disk()

class Controller:

    @classmethod
    def get_all_vm_status(cls):

        vms = [os.path.basename(os.path.dirname(x)) for x in
               glob.glob(f"{BASE_PATH}/*/vm.json")]
        table = Table()
        table.add_column("VM Name", width=35)
        table.add_column("IP Address")
        table.add_column("Distribution")
        table.add_column("CPUs")
        table.add_column("Memory")
        table.add_column("Status")
        for vm in vms:
            vm_obj = VMManager(vm)
            if vm_obj.exists:
                vm_obj.load_configuration_from_disk()
                configuration = vm_obj.configuration
                try:
                    ip_address = vm_obj.get_ip_address()
                except VMHasNoAssignedAddress:
                    ip_address = "None"

                if vm_obj.is_running():
                    status = "Running :person_running:"
                else:
                    status = "Stopped :stop_button:"

                table.add_row(vm, ip_address, configuration['profile'],
                              str(configuration['cpus']), str(configuration['memory']),
                              status)

        print(table)

    @classmethod
    def create(cls, profile, name, cpus, memory, disk_size):
        vm = VMManager(name)
        vm.create(profile, cpus, memory, disk_size)

    @classmethod
    def delete(cls, name):
        vm = VMManager(name)
        vm.delete()

    @classmethod
    def stop(cls, name, force: bool = False):
        vm = VMManager(name)
        vm.stop(force=force)

    @classmethod
    def start(cls, name):
        vm = VMManager(name)
        vm.start()

    @classmethod
    def cp(cls, name, source, destination, recursive=False):
        vm = VMManager(name)
        vm.cp(source, destination, recursive)

    @classmethod
    def mount(cls, name, source, destination):
        vm = VMManager(name)
        vm.mount(source, destination)

    @classmethod
    def shell(cls, name, command):
        vm = VMManager(name)
        vm.shell(command)

    @classmethod
    def update_vm_resources(cls, name, memory, cpus):
        vm = VMManager(name)
        vm.update_resources(memory, cpus)

