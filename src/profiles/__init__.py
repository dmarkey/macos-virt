import xdg
import os
import platform

base_path = os.path.join(xdg.xdg_config_home(), "macos-virt/base-files/")

KERNAL_FILENAME = "kernel"
INITRD_FILENAME = "initrd"
DISK_FILENAME = "disk.img"

if platform.machine() == "x86_64":
    PLATFORM = "amd64"
else:
    PLATFORM = "arm64"


class BaseProfile:
    name = None
    version = None

    @classmethod
    def cache_directory(cls):
        return os.path.join(base_path, cls.name, cls.version)

    @classmethod
    def check_required_files(cls):
        cache_directory = cls.cache_directory()
        for filename in [KERNAL_FILENAME, INITRD_FILENAME, DISK_FILENAME]:
            if not os.path.exists(os.path.join(cache_directory, filename)):
                return False

    @classmethod
    def get_kernel_url(cls):
        raise NotImplementedError()

    @classmethod
    def get_initrd_url(cls):
        raise NotImplementedError()

    @classmethod
    def get_disk_image_url(cls):
        raise NotImplementedError()



