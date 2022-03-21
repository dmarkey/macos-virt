import typer
from macos_virt.profiles.registry import registry
from macos_virt.controller import Controller, DuplicateVMException

app = typer.Typer()


@app.command()
def start(name="default", distribution: str = registry.get_distributions()[0],
          memory: int = 2048,
          cpus: int = 1, disk_size: int = 5000):
    try:
        Controller.start(distribution, name, cpus, memory, disk_size)
    except DuplicateVMException as e:
        typer.echo(e, err=True)
        raise typer.Exit(code=1)


@app.command()
def ls():
    [typer.echo(x) for x in Controller.get_valid_vms()]


@app.command()
def stop(name="default", force=False):
    Controller.stop(name)


@app.command()
def shell(name="default"):
    Controller.shell(name)


@app.command()
def console(name="default"):
    return


@app.command()
def delete(name="default"):
    confirm = typer.confirm(f"Are you sure you want to delete {name}?")
    if confirm:
        Controller.delete(name)


@app.command()
def setup():
    Controller.setup()


def main():
    app()
