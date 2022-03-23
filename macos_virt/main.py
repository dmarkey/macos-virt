import typer
from macos_virt.controller import Controller, DuplicateVMException
from macos_virt.profiles.registry import registry

app = typer.Typer()


@app.command()
def create(name="default", distribution: str = registry.get_distributions()[0],
           memory: int = 2048,
           cpus: int = 1, disk_size: int = 5000):
    try:
        Controller.create(distribution, name, cpus, memory, disk_size)
    except DuplicateVMException as e:
        typer.echo(e, err=True)
        raise typer.Exit(code=1)


@app.command()
def ls():
    Controller.get_all_vm_status()


@app.command()
def stop(name="default", force: bool = typer.Option(False, "--force")):
    Controller.stop(name, force)


@app.command()
def start(name="default", force=False):
    Controller.start(name)


@app.command()
def mount(source, destination, name="default"):
    Controller.mount(name, source, destination)


@app.command()
def shell(name="default", command: str = None):
    Controller.shell(name, command)


@app.command()
def cp(src, destination, name="default", recursive: bool = typer.Option(False, "--recursive")):
    Controller.cp(name, src, destination, recursive=recursive)


@app.command()
def delete(name="default"):
    confirm = typer.confirm(f"Are you sure you want to delete {name}?")
    if confirm:
        Controller.delete(name)


def main():
    app()
