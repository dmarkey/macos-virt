import os
import tarfile

import yaml
from rich.progress import Progress
from rich.console import Console
import shutil

from macos_virt.profiles import BaseProfile, PLATFORM, DISK_FILENAME

PATH = os.path.dirname(os.path.abspath(__file__))


class Alpine315(BaseProfile):
    name = "alpine-3.15"
    description = "Alpine 3.15"

    cloudinit_file = "alpine-cloudinit.yaml"

    @classmethod
    def process_downloaded_files(cls, cache_directory):
        disk_full_path = os.path.join(cache_directory, DISK_FILENAME)
        disk_directory = os.path.dirname(disk_full_path)
        with Progress() as progress:
            progress.add_task(
                "Extracting Root Image for Alpine", total=100, start=False
            )
            gzipped_disk = os.path.join(disk_directory, "disk.img.gz")
            with gzip.open(gzipped_disk, 'r') as f_in, open(disk_full_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                os.unlink(gzipped_disk)


    @classmethod
    def get_boot_files_from_filesystem(cls, mountpoint):
        return "vmlinuz-virt", "initramfs-virt"

    @classmethod
    def get_kernel_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/"
            f"releases/focal/release/"
            f"unpacked/"
            f"ubuntu-20.04-server-cloudimg-{PLATFORM}-vmlinuz-generic"
        )

    @classmethod
    def get_initrd_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/"
            f"releases/focal/release/"
            f"unpacked/"
            f"ubuntu-20.04-server-cloudimg-{PLATFORM}-initrd-generic"
        )

    @classmethod
    def get_disk_image_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/"
            f"releases/focal/release-20220302/"
            f"ubuntu-20.04-server-cloudimg-{PLATFORM}.tar.gz"
        )

    @classmethod
    def render_cloudinit_data(cls, username, ssh_key):
        template = yaml.safe_load(open(os.path.join(PATH, cls.cloudinit_file), "rb"))
        template["users"][1]["gecos"] = username
        template["users"][1]["name"] = username
        template["users"][1]["ssh-authorized-keys"][0] = ssh_key
        if "write_files" in template:
            write_files = template["write_files"]
        else:
            write_files = []

        write_files.append(
            {
                "content": open(
                    os.path.join(PATH, "../service/install_boot.sh")
                ).read(),
                "path": "/usr/sbin/install_boot.sh",
            }
        )
        write_files.append(
            {
                "content": open(os.path.join(PATH, "../service/service.py")).read(),
                "path": "/usr/sbin/macos-virt-service.py",
            }
        )
        template["write_files"] = write_files
        return template
