import os

from profiles import BaseProfile, PLATFORM, KERNAL_FILENAME, DISK_FILENAME
import gzip
from rich.progress import Progress
import tarfile
import yaml

PATH = os.path.dirname(os.path.abspath(__file__))


class Ubuntu2004(BaseProfile):
    name = "ubuntu-20.04"

    @classmethod
    def process_downloaded_files(cls, cache_directory):
        disk_full_path = os.path.join(cache_directory, DISK_FILENAME)
        try:
            kernel_full_path = os.path.join(cache_directory, KERNAL_FILENAME)
            kern = gzip.open(kernel_full_path)
            uncompressed = kern.read()
            kern.close()
            with open(kernel_full_path, "wb") as f:
                f.write(uncompressed)
        except gzip.BadGzipFile:
            pass
        with Progress() as progress:
            progress.add_task("Extracting Root Image for Ubuntu", total=100,
                              start=False)
            tf = tarfile.open(disk_full_path)
            tf.extractall()
            tf.close()
            os.rename(f"focal-server-cloudimg-{PLATFORM}.img", disk_full_path)

    @classmethod
    def get_kernel_url(cls):
        return f"https://cloud-images.ubuntu.com/releases/focal/release/" \
               f"unpacked/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}-vmlinuz-generic"

    @classmethod
    def get_initrd_url(cls):
        return f"https://cloud-images.ubuntu.com/releases/focal/release/" \
               f"unpacked/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}-initrd-generic"

    @classmethod
    def get_disk_image_url(cls):
        return f"https://cloud-images.ubuntu.com/releases/focal/release/" \
               f"ubuntu-20.04-server-cloudimg-{PLATFORM}.tar.gz"

    @classmethod
    def render_cloudinit_data(cls, username, ssh_key):
        template = yaml.safe_load(open(
            os.path.join(PATH, "ubuntu-cloudinit.yaml"), "rb"))
        template['users'][1]['gecos'] = username
        template['users'][1]['name'] = username
        template['users'][1]['ssh-authorized-keys'][0] = ssh_key
        return template

