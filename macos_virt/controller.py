import glob
import gzip
import json
import os
import pathlib
import random
import shutil
import subprocess
import tarfile
import tempfile
from subprocess import check_output
import typer
import xdg as xdg
from rich import print
from rich.console import Console
from rich.progress import track, Progress
from rich.table import Table
from urllib import request
import time
import fs
import configparser
import platform
from .downloader import download

PLATFORM = platform.machine()
MODULE_PATH = os.path.dirname(__file__)

DISK_FILENAME = "root.img"
BOOT_DISK_FILENAME = "boot.img"

CONTROL_DIRECTORY_NAME = "control_directory"
BASE_PATH = os.path.join(xdg.xdg_config_home(), "macos-virt2")
VM_BASE_PATH = os.path.join(BASE_PATH, "vms")
GENERIC_KERNELS_PATH = os.path.join(BASE_PATH, "generic_kernels")

pathlib.Path(GENERIC_KERNELS_PATH).mkdir(parents=True, exist_ok=True)
pathlib.Path(VM_BASE_PATH).mkdir(parents=True, exist_ok=True)
MB = 1024 * 1024

KEY_PATH = os.path.join(xdg.xdg_config_home(), "macos-virt/macos-virt-identity")
KEY_PATH_PUBLIC = os.path.join(
    xdg.xdg_config_home(), "macos-virt/macos-virt-identity.pub"
)

RUNNER_PATH = os.path.join(MODULE_PATH, "macos_virt_runner/macos_virt_runner")
SERVICE_PATH = os.path.join(MODULE_PATH, "service.sh")
RUNNER_PATH_ENTITLEMENTS = os.path.join(
    MODULE_PATH, "macos_virt_runner/" "macos_virt_runner.entitlements"
)

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

class ProfileNotFound(BaseError):
    pass

class VMStarted(typer.Exit):
    code = 0


def get_vm_directory(name):
    path = os.path.join(VM_BASE_PATH, name)
    pathlib.Path(path).mkdir(exist_ok=True)
    return path


class VMManager:
    def __init__(self, name):
        self.name = name
        self.vm_directory = os.path.join(VM_BASE_PATH, name)
        self.vm_configuration_file = os.path.join(self.vm_directory, "vm.json")
        self.exists = False
        if os.path.exists(self.vm_configuration_file):
            self.exists = True
        self.configuration = {}
        self.profile = None

    @property
    def control_directory(self):
        return os.path.join(self.vm_directory, CONTROL_DIRECTORY_NAME)

    def create(self, package, cpus, memory, disk_size, mount_home_directory):
        if self.exists:
            raise VMExists(f"VM {self.name} already exists")
        if "://" not in package:
            try:
                package = Controller.get_profiles()[package]
            except KeyError:
                raise ProfileNotFound(f"{package} not found")
        self.configuration = {
            "memory": memory,
            "cpus": cpus,
            "package": package,
            "disk_size": disk_size,
            "ip_address": None,
            "status": "uninitialized",
            "mount_home_directory": mount_home_directory,
            "mac_address": "52:54:00:%02x:%02x:%02x"
                           % (
                               random.randint(0, 255),
                               random.randint(0, 255),
                               random.randint(0, 255),
                           ),
        }
        pathlib.Path(self.vm_directory).mkdir(parents=True)
        self.save_configuration_to_disk()
        self.provision()

    def read_control_file(self, filename):
        try:
            with open(os.path.join(self.control_directory, filename)) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def print_realtime_status(self):
        heartbeat = self.read_control_file("heartbeat")
        stats = { x.split(": ")[0]: x.split(": ")[1]+"%"
                  for x in heartbeat.split("\n")  if x}
        tab = Table()
        tab.add_column("Name")
        tab.add_column("IP")
        for header in stats.keys():
            tab.add_column(header)
        tab.add_row(self.name, self.get_ip_address(), *list(stats.values()))
        console.print(tab)
        return

    def get_ip_address(self):
        return self.read_control_file("ip").strip().split("\n")[-1]

    def shell(self, args, wait=False):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running.")
        ip_address = self.get_ip_address()
        to_spawn = [
            "/usr/bin/ssh",
            "-oStrictHostKeyChecking=no",
            "-i",
            KEY_PATH,
            f"{USERNAME}@{ip_address}",
        ]
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

        return self.boot_normally()

    def load_configuration_from_disk(self):
        self.configuration = json.load(open(self.vm_configuration_file))

    def stop(self, force=False):
        if not self.is_running():
            raise VMNotRunning(f"🤷 VM {self.name} is not running")
        if force:
            pid = open(os.path.join(self.vm_directory, "pidfile")).read()
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
            finally:
                console.print(f":skull: VM  {self.name} terminated by force")
                return

        with open(os.path.join(self.control_directory, "poweroff"), "w") as f:
            f.close()
        console.print(f":sleeping: Stop request sent to {self.name}")

    def provision(self):
        vm_directory = self.vm_directory
        download([{"from": self.configuration['package'], "to": os.path.join(
            self.vm_directory, "package.tar.gz")}])
        source = request.urlopen(self.configuration['package'])
        dest = os.path.join(vm_directory, "package.tar.gz")
        with Progress() as progress:
            progress.add_task(
                "Extracting Files for VM", total=100, start=False
            )
            tf = tarfile.open(dest)
            tf.extract("root.img", path=vm_directory)
            tf.extract("boot.img", path=vm_directory)
            tf.extract("boot.cfg", path=vm_directory)
            tf.close()
            os.unlink(dest)
        vm_disk = os.path.join(vm_directory, "root.img")
        mb_padding = b"\0" * MB
        size = os.path.getsize(vm_disk)
        chunks = int(((MB * self.configuration["disk_size"]) - size) / MB)
        with open(vm_disk, "ba") as f:
            for _ in track(range(chunks), description="Expanding Root Image..."):
                f.write(mb_padding)

        self.boot_normally()

    def boot_vm(self, kernel, initrd=None, cmdline=None):
        try:
            kern = gzip.open(kernel)
            uncompressed = kern.read()
            kern.close()
            with open(kernel, "wb") as f:
                f.write(uncompressed)
        except gzip.BadGzipFile:
            pass

        shutil.rmtree(self.control_directory, ignore_errors=True)
        os.mkdir(self.control_directory)
        shutil.copy(SERVICE_PATH, os.path.join(self.control_directory, "service.sh"))
        ssh_key = self.get_ssh_public_key()
        with open(os.path.join(self.control_directory, "ssh_key"), "w") as f:
            f.write(ssh_key)
        check_output(
            [
                "codesign",
                "-f",
                "-s",
                "-",
                "--entitlements",
                RUNNER_PATH_ENTITLEMENTS,
                RUNNER_PATH,
            ]
        )
        boot_config = {}
        boot_config["kernel"] = kernel
        boot_config["mac"] = self.configuration['mac_address']
        boot_config["cpus"] = self.configuration['cpus']
        boot_config["memory"] = self.configuration['memory']
        boot_config["share_home"] = False
        if initrd:
            boot_config["initrd"] = initrd
        if cmdline:
            boot_config["cmdline"] = cmdline
        if self.configuration.get("mount_home_directory", False):
            with open(os.path.join(self.control_directory, "mnt_usr_directory"), "w") as f:
                f.write(os.path.expanduser('~'))
            boot_config["share_home"] = True
        else:
            try:
                os.remove(os.path.join(self.control_directory, "mnt_usr_directory"))
            except OSError:
                pass

        with open(os.path.join(self.vm_directory, "boot_config.json"), "w") as f:
            json.dump(boot_config, f)

        subprocess.run(
            f"/usr/bin/screen -S console-{self.name} -dm sh -c '{RUNNER_PATH}'",
            shell=True,
            cwd=self.vm_directory
        )
        for x in range(0, 30):
            if self.get_ip_address():
                text = ":hatched_chick: VM is booted."
                console.print(text)
                return
            time.sleep(0.5)
        text = ":rotating_light: VM had a problem initializing"
        console.print(text)

    def save_configuration_to_disk(self):
        with open(os.path.join(self.vm_directory, "vm.json"), "w") as f:
            json.dump(self.configuration, f)


    def is_running(self):
        try:
            pid = open(os.path.join(self.vm_directory, "pidfile")).read()
            try:
                os.kill(int(pid), 0)
            except OSError:
                return False
            else:
                return True
        except FileNotFoundError:
            return False

    def boot_disk(self):
        return os.path.join(self.vm_directory, BOOT_DISK_FILENAME)

    def get_generic_kernel(self):
        test_kernel_path = os.path.join(GENERIC_KERNELS_PATH, "test-kernel")
        if os.path.exists(test_kernel_path):
            print("Booting with test kernel")
            return test_kernel_path
        resp = request.urlopen("https://api.github.com/"
                               "repos/dmarkey/macos-virt-kernel/releases")
        releases = json.loads(resp.read().decode())
        latest_release = [x for x in releases if x['assets']][0]
        version = releases[0]['tag_name']
        latest_kernel_path = os.path.join(GENERIC_KERNELS_PATH, version)
        if not os.path.exists(latest_kernel_path):
            latest_kernel =  [ x for x in latest_release['assets'] if
                               x['name'] == f"vmlinuz-{PLATFORM}" ][0]['browser_download_url']
            download([{"from": latest_kernel, "to": latest_kernel_path }])
        return latest_kernel_path

    def boot_normally(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(self.vm_directory, "boot.cfg"))
        config = config['macos-virt-boot-config']
        cmdline = config['cmdline']
        if config.get(f"generic_{PLATFORM}_kernel", "false").lower() == "true":
            kernel_path = self.get_generic_kernel()
            console.print(
                f":floppy_disk: Booting with generic arm64 kernel {kernel_path}"
                f" and kernel command line {cmdline}"
            )
            self.boot_vm(kernel_path, cmdline=cmdline)
        else:
            vm_boot_disk = self.boot_disk()
            with fs.open_fs(f"fat://{vm_boot_disk}?read_only=true") as fat32_boot_disk:
                vm_boot_disk = self.boot_disk()
                fat32_boot_disk = fs.open_fs(f"fat://{vm_boot_disk}?read_only=true")
                try:
                    kernel_path = \
                    sorted([x.path for x in fat32_boot_disk.glob(config["kernel_glob"])])[0]
                    initrd_path = \
                    sorted([x.path for x in fat32_boot_disk.glob(config["initrd_glob"])])[0]
                except IndexError:
                    console.print(
                        "Could not load kernel or initrd from the boot disk."
                    )
                    return
                console.print(
                    f":floppy_disk: Booting with Kernel {kernel_path} and"
                    f" Ramdisk {initrd_path} from Boot volume"
                    f" and kernel command line {cmdline}"
                )
                with tempfile.NamedTemporaryFile(delete=True) as kernel:
                    kernel.write(fat32_boot_disk.open(kernel_path, "rb").read())
                    with tempfile.NamedTemporaryFile(delete=True) as initrd:
                        initrd.write(fat32_boot_disk.open(initrd_path, "rb").read())
                        self.boot_vm(kernel.name, initrd=initrd.name,
                                     cmdline=config['cmdline'])

    def delete(self):
        if not self.exists:
            raise VMDoesntExist(f"🤷 VM {self.name} does not exist.")
        if self.is_running():
            raise VMRunning(
                f"VM {self.name} is running, please stop it before deleting."
            )
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
            raise InternalErrorException(
                "Copy arguments missing vm: prefix to indicate direction."
            )
        if recursive:
            args.insert(0, "-r")
        full_args = [
                        "/usr/bin/scp",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-i",
                        KEY_PATH,
                    ] + args
        check_output(full_args)

    def update_vm_settings(self, memory, cpus, mount_home_directory):
        if self.is_running():
            raise VMRunning(
                f"🤷 VM {self.name} is running, "
                f"Please shut it down before updating settings."
            )
        self.load_configuration_from_disk()
        if memory:
            console.print(
                f":rocket: changing memory from "
                f"{self.configuration['memory']} to {memory}"
            )
            self.configuration["memory"] = memory
        if mount_home_directory is not None:
            self.configuration["mount_home_directory"] = mount_home_directory
        if cpus:
            self.configuration["cpus"] = cpus
            console.print(
                f":rocket: changing CPUs from "
                f"{self.configuration['cpus']} to {cpus}"
            )
        if memory or cpus or mount_home_directory is not None:
            self.save_configuration_to_disk()
        else:
            console.print(f"🤷 You didn't ask to change anything.")


class Controller:

    @classmethod
    def get_profiles(cls):
        resp = request.urlopen("https://api.github.com/"
                               "repos/dmarkey/macos-virt-images/releases")
        releases = json.loads(resp.read().decode())
        latest_release = [x for x in releases if x['assets']][0]
        arch = platform.machine()
        linux_arch = "x86_64"
        if arch == "arm64":
            linux_arch = "aarch64"
        profiles = { x['name'][:-8-len(linux_arch)]: x['browser_download_url']
                     for x in latest_release['assets'] if linux_arch in x['name']}
        return profiles

    @classmethod
    def list_all_vms(cls):
        return [
            os.path.basename(os.path.dirname(x))
            for x in glob.glob(f"{VM_BASE_PATH}/*/vm.json")
        ]

    @classmethod
    def list_running_vms(cls):
        vms = cls.list_all_vms()
        return [x for x in vms if VMManager(x).is_running()]

    @classmethod
    def get_all_vm_status(cls):
        vms = cls.list_all_vms()
        table = Table()
        table.add_column("VM Name", width=35)
        table.add_column("IP Address")
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

                table.add_row(
                    vm,
                    ip_address,
                    str(configuration["cpus"]),
                    str(configuration["memory"]),
                    status,
                )

        print(table)
