import enum
from importlib.metadata import version as package_version

import typer
from rich.console import Console
from rich.table import Table

from macos_virt.controller import Controller, VMManager
from macos_virt.profiles.registry import registry

app = typer.Typer(name="macos-virt - a utility to run Linux VMs using Virtualization.Framework")

profiles = [(profile, profile) for profile in registry.profiles.keys()]

profiles_enum = enum.Enum("Profiles", dict(profiles))

vms = [(vm, vm) for vm in Controller.list_all_vms()]
vms_enum = enum.Enum("VMs", dict(vms))

running_vms = [(vm, vm) for vm in Controller.list_running_vms()]
running_vms_enum = enum.Enum("RunningVMs", dict(running_vms))


@app.command(help="Create a new VM")
def create(
        name="default",
        profile: profiles_enum = "ubuntu-20.04",
        memory: int = 2048,
        cpus: int = 1,
        disk_size: int = 5000,
):
    VMManager(name).create(profile.value, cpus, memory, disk_size)


@app.command(help="List all VMs")
def ls():
    Controller.get_all_vm_status()


@app.command(help="Stop a running VM")
def stop(
        name: running_vms_enum,
        force: bool = typer.Option(False, "--force", help="Kills the VM unceremoniously."),
):
    VMManager(name.value).stop(force=force)


@app.command(help="Start an already created VM")
def start(name: vms_enum):
    VMManager(name.value).start()


@app.command(help="Get high level status of a running VM")
def status(name: running_vms_enum):
    VMManager(name.value).print_realtime_status()


@app.command(help="Update memory or CPU on a stopped VM")
def update(name: vms_enum = "default", memory: int = None, cpus: int = None):
    VMManager(name.value).update_resources(memory, cpus)


@app.command(help="Mount a local directory into the VM")
def mount(name: running_vms_enum, source, destination,
          ro: bool = typer.Option(False, "--ro",
                                  help="Mount read only.")):
    VMManager(name.value).mount(source, destination, ro)


@app.command(help="Unmount a directory in the VM")
def umount(name: running_vms_enum, mountpoint):
    VMManager(name.value).umount(mountpoint)


@app.command(help="Access a shell to a running VM")
def shell(name: running_vms_enum, command: str = None):
    VMManager(name.value).shell(command)


@app.command(help="Copy a file to/from a running VM, macos-virt cp default vm:/etc/passwd")
def cp(
        name: running_vms_enum,
        src,
        destination,
        recursive: bool = typer.Option(False, "--recursive"),
):
    VMManager(name.value).cp(source=src, destination=destination, recursive=recursive)


@app.command(help="Delete a stopped VM")
def rm(name: vms_enum):
    confirm = typer.confirm(f"Are you sure you want to delete {name}?")
    if confirm:
        VMManager(name.value).delete()


@app.command(help="Show Version information")
def version():
    typer.echo(f"Macos-virt version {package_version('macos_virt')}")


@app.command(help="Describe profiles that are available")
def profiles():
    console = Console()
    tab = Table()
    tab.add_column("Profile name")
    tab.add_column("Description")
    for name, profile in registry.profiles.items():
        tab.add_row(name, profile.description)
    console.print(tab)


def main():
    app()
