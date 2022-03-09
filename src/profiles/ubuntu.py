from profiles import BaseProfile, PLATFORM


class Ubuntu2004(BaseProfile):
    name = "ubuntu-20.04"

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
