import os
import tarfile

import yaml
from fs.base import FS
from rich.progress import Progress
from rich.console import Console

from macos_virt.profiles import BaseProfile, PLATFORM, DISK_FILENAME

PATH = os.path.dirname(os.path.abspath(__file__))


class Ubuntu2004(BaseProfile):
    name = "ubuntu-20.04"
    description = "Ubuntu 20.04 Server Cloud Image"
    extracted_name = f"focal-server-cloudimg-{PLATFORM}.img"

    cloudinit_file = "ubuntu-cloudinit.yaml"

    @classmethod
    def process_downloaded_files(cls, cache_directory):
        disk_full_path = os.path.join(cache_directory, DISK_FILENAME)
        disk_directory = os.path.dirname(disk_full_path)
        with Progress() as progress:
            progress.add_task(
                "Extracting Root Image for Ubuntu", total=100, start=False
            )
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
        write_files.append(
            {
                "content": open(
                    os.path.join(PATH, "../service/macos-virt-service.service")
                ).read(),
                "path": "/etc/systemd/system/macos-virt-service.service",
            }
        )
        template["write_files"] = write_files
        return template


class Ubuntu2004K3S(Ubuntu2004):
    name = "ubuntu-20.04-k3s"
    description = (
        "Ubuntu 20.04 Server Cloud Image with K3S and Docker (Qemu emulation included)"
    )
    k3s_installer = """
      #!/bin/sh
      curl -sfL https://get.k3s.io | sudo INSTALL_K3S_VERSION=v1.23.3+k3s1 INSTALL_K3S_EXEC="--write-kubeconfig-mode 644 --docker" sh -
    """

    @classmethod
    def post_provision_customizations(cls, vm):
        vm_ip_address = vm.get_ip_address()
        vm_directory = vm.vm_directory
        k3s_path = os.path.join(vm_directory, "k3s.yaml")
        vm.cp("vm://etc/rancher/k3s/k3s.yaml", k3s_path)
        with open(k3s_path) as f:
            k3s_file_contents = f.read()

        k3s_file_contents = k3s_file_contents.replace(
            "127.0.0.1", vm_ip_address)
        with open(k3s_path, "w") as f:
            f.write(k3s_file_contents)

        console = Console()
        console.print("[bold red]To use th VM Kubernetes/Docker, set the following environment variables.")
        console.print(f"export DOCKER_HOST=tcp://{vm_ip_address}")
        console.print(f"export KUBECONFIG={k3s_path}")

    @classmethod
    def render_cloudinit_data(cls, username, ssh_key):
        template = Ubuntu2004.render_cloudinit_data(username, ssh_key)
        apt_sources = template.get("apt_sources", [])
        apt_sources.append({"source": "ppa:canonical-server/server-backports"})
        template["apt_sources"] = apt_sources

        packages = template.get("packages", [])
        packages.append("docker.io")
        packages.append("qemu")
        packages.append("binfmt-support")
        packages.append("qemu-user-static")
        template["packages"] = packages
        write_files = template.get("write_files", [])
        write_files.append({"content": cls.k3s_installer, "path": "/root/k3s-init.sh"})
        write_files.append(
            {
                "content": open(
                    os.path.join(PATH, "../service/docker-service-override.conf")
                ).read(),
                "path": "/etc/systemd/system/docker.service.d/override.conf",
            }
        )
        template["write_files"] = write_files
        runcmd = template.get("runcmd", [])
        runcmd.append(["systemctl", "restart", "docker"])
        runcmd.append(["bash", "/root/k3s-init.sh"])
        template["runcmd"] = runcmd
        return template


class Ubuntu2104(Ubuntu2004):
    name = "ubuntu-21.04"
    extracted_name = f"hirsute-server-cloudimg-{PLATFORM}.img"
    description = "Ubuntu 21.04 Server Cloud Image"

    @classmethod
    def get_kernel_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/releases/hirsute/release/unpacked/"
            f"ubuntu-21.04-server-cloudimg-{PLATFORM}-vmlinuz-generic"
        )

    @classmethod
    def get_initrd_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/releases/hirsute/release/unpacked/"
            f"ubuntu-21.04-server-cloudimg-{PLATFORM}-initrd-generic"
        )

    @classmethod
    def get_disk_image_url(cls):
        return (
            "https://cloud-images.ubuntu.com/releases/hirsute/release/"
            f"ubuntu-21.04-server-cloudimg-{PLATFORM}.tar.gz"
        )


class Ubuntu2110(Ubuntu2004):
    name = "ubuntu-21.10"
    extracted_name = f"impish-server-cloudimg-{PLATFORM}.img"
    description = "Ubuntu 21.10 Server Cloud Image"

    @classmethod
    def get_kernel_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/"
            f"releases/impish/release/unpacked/"
            f"ubuntu-21.10-server-cloudimg-{PLATFORM}-vmlinuz-generic"
        )

    @classmethod
    def get_initrd_url(cls):
        return (
            f"https://cloud-images.ubuntu.com/"
            f"releases/impish/release/unpacked/"
            f"ubuntu-21.10-server-cloudimg-{PLATFORM}-initrd-generic"
        )

    @classmethod
    def get_disk_image_url(cls):
        return (
            "https://cloud-images.ubuntu.com/releases/impish/release-20220118/"
            f"ubuntu-21.10-server-cloudimg-{PLATFORM}.tar.gz"
        )
