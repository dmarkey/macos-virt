import typer
from profiles.registry import registry
from controller import Controller, DuplicateVMException


app = typer.Typer()


@app.command()
def start(name="default", distribution: str = registry.get_distributions()[0],
          memory: int = 1024,
          cpus: int = 1, disk_size: int = 5000, cloudinit: typer.FileText = None):
    try:
        Controller.start(distribution, name, cpus, memory, disk_size,
                         cloudinit)
    except DuplicateVMException as e:
        typer.echo(e, err=True)
        raise typer.Exit(code=1)


@app.command()
def ls():
    [typer.echo(x) for x in Controller.get_valid_vms()]


@app.command()
def stop(name="default", force=False):
    return


@app.command()
def shell(name="default"):
    return


@app.command()
def console(name="default"):
    return


@app.command()
def delete(name="default"):
    Controller.delete(name)


if __name__ == "__main__":
    app()
