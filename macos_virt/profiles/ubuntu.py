import os

from fs.base import FS

from macos_virt.profiles import BaseProfile, PLATFORM, DISK_FILENAME
from rich.progress import Progress
import tarfile
import yaml

PATH = os.path.dirname(os.path.abspath(__file__))


class Ubuntu2004(BaseProfile):
    name = "ubuntu-20.04"

    extracted_name = f"focal-server-cloudimg-{PLATFORM}.img"

    @classmethod
    def process_downloaded_files(cls, cache_directory):
        disk_full_path = os.path.join(cache_directory, DISK_FILENAME)
        disk_directory = os.path.dirname(disk_full_path)
        with Progress() as progress:
            progress.add_task("Extracting Root Image for Ubuntu", total=100,
                              start=False)
            tf = tarfile.open(disk_full_path)
            tf.extractall(disk_directory)
            tf.close()
            os.rename(os.path.join(disk_directory, cls.extracted_name), disk_full_path)

    @classmethod
    def get_boot_files_from_filesystem(cls, filesystem: FS):
        files = filesystem.listdir("/")

        kernel = sorted([x for x in files if "vmlinuz" in x])[-1]
        initrd = sorted([x for x in files if "initrd" in x])[-1]
        return kernel, initrd

    @classmethod
    def get_kernel_url(cls):
        return f"https://cloud-images.ubuntu.com/" \
               f"releases/focal/release-20220302/" \
               f"unpacked/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}-vmlinuz-generic"

    @classmethod
    def get_initrd_url(cls):
        return f"https://cloud-images.ubuntu.com/" \
               f"releases/focal/release-20220302/" \
               f"unpacked/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}-initrd-generic"

    @classmethod
    def get_disk_image_url(cls):
        return f"https://cloud-images.ubuntu.com/" \
               f"releases/focal/release-20220302/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}.tar.gz"

    @classmethod
    def render_cloudinit_data(cls, username, ssh_key):
        template = yaml.safe_load(open(
            os.path.join(PATH, "ubuntu-cloudinit.yaml"), "rb"))
        template['users'][1]['gecos'] = username
        template['users'][1]['name'] = username
        template['users'][1]['ssh-authorized-keys'][0] = ssh_key
        return template


class Ubuntu2104(Ubuntu2004):
    name = "ubuntu-21.04"
    extracted_name = f"hirsute-server-cloudimg-{PLATFORM}.img"

    @classmethod
    def get_kernel_url(cls):
        return f"https://cloud-images.ubuntu.com/releases/hirsute/release/unpacked/" \
               f"ubuntu-21.04-server-cloudimg-{PLATFORM}-vmlinuz-generic"

    @classmethod
    def get_initrd_url(cls):
        return f"https://cloud-images.ubuntu.com/releases/hirsute/release/unpacked/" \
               f"ubuntu-21.04-server-cloudimg-{PLATFORM}-initrd-generic"

    @classmethod
    def get_disk_image_url(cls):
        return "https://cloud-images.ubuntu.com/releases/hirsute/release/" \
               f"ubuntu-21.04-server-cloudimg-{PLATFORM}.tar.gz"


class Ubuntu2110(Ubuntu2004):
    name = "ubuntu-21.10"
    extracted_name = f"impish-server-cloudimg-{PLATFORM}.img"

    @classmethod
    def get_kernel_url(cls):
        return f"https://cloud-images.ubuntu.com/" \
               f"releases/impish/release/unpacked/" \
               f"ubuntu-21.10-server-cloudimg-{PLATFORM}-vmlinuz-generic"

    @classmethod
    def get_initrd_url(cls):
        return f"https://cloud-images.ubuntu.com/" \
               f"releases/impish/release/unpacked/" \
               f"ubuntu-21.10-server-cloudimg-{PLATFORM}-initrd-generic"

    @classmethod
    def get_disk_image_url(cls):
        return "https://cloud-images.ubuntu.com/releases/impish/release-20220118/" \
               f"ubuntu-21.10-server-cloudimg-{PLATFORM}.tar.gz"