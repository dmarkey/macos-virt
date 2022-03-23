import xdg
import os
import platform
import pathlib

from macos_virt.constants import KERNAL_FILENAME, INITRD_FILENAME, DISK_FILENAME
from .downloader import download

base_path = os.path.join(xdg.xdg_config_home(), "macos-virt/base-files/")

if platform.machine() == "x86_64":
    PLATFORM = "amd64"
else:
    PLATFORM = "arm64"


class BaseProfile:
    name = None

    @classmethod
    def profile_directory(cls):
        return os.path.join(base_path, cls.name)

    @classmethod
    def file_locations(cls):
        cache_directory = cls.profile_directory()
        if not cls.required_files_exist():
            cls.download_required_files()
        return (
            os.path.join(cache_directory, KERNAL_FILENAME),
            os.path.join(cache_directory, INITRD_FILENAME),
            os.path.join(cache_directory, DISK_FILENAME),
        )

    @classmethod
    def required_files_exist(cls):
        cache_directory = cls.profile_directory()
        pathlib.Path(cache_directory).mkdir(exist_ok=True, parents=True)
        for filename in [KERNAL_FILENAME, INITRD_FILENAME, DISK_FILENAME]:
            if not os.path.exists(os.path.join(cache_directory, filename)):
                return False
        return True

    @classmethod
    def process_downloaded_files(cls, cache_directory):
        raise NotImplementedError()

    @classmethod
    def post_provision_customizations(cls, vm):
        pass

    @classmethod
    def download_required_files(cls):
        cache_directory = cls.profile_directory()
        if not cls.required_files_exist():
            kernel_url = cls.get_kernel_url()
            initrd_url = cls.get_initrd_url()
            disk_url = cls.get_disk_image_url()
            tmp_kernel_filename = os.path.join(
                cache_directory, KERNAL_FILENAME + "_tmp"
            )
            tmp_initrd_filename = os.path.join(
                cache_directory, INITRD_FILENAME + "_tmp"
            )
            tmp_disk_filename = os.path.join(cache_directory, DISK_FILENAME + "_tmp")
            download(
                [
                    {"from": kernel_url, "to": tmp_kernel_filename},
                    {"from": initrd_url, "to": tmp_initrd_filename},
                    {"from": disk_url, "to": tmp_disk_filename},
                ]
            )
            os.rename(
                tmp_kernel_filename, os.path.join(cache_directory, KERNAL_FILENAME)
            )
            os.rename(
                tmp_initrd_filename, os.path.join(cache_directory, INITRD_FILENAME)
            )
            os.rename(tmp_disk_filename, os.path.join(cache_directory, DISK_FILENAME))
            cls.process_downloaded_files(cache_directory)

    @classmethod
    def get_kernel_url(cls):
        raise NotImplementedError()

    @classmethod
    def get_initrd_url(cls):
        raise NotImplementedError()

    @classmethod
    def get_disk_image_url(cls):
        raise NotImplementedError()

    @classmethod
    def render_cloudinit_data(cls, username, ssh_key):
        raise NotImplementedError()

    def get_boot_files_from_filesystem(self, filesystem):
        pass
