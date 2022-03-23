# Macos-Virt

A utility to get up and running with MacOS's Virtualization.Framework in 5 minutes.


## Installation
You need python3 installed, either install it via Brew or Command Line Tools
```bash
pip install macos-virt
```

Or within a virtualenv to be cleaner:

```bash
python3 -m venv venv
source venv/bin/activate
pip install macos-virt
```

### Prerequisites

* macOS Monterey (12.3+)
* Intel or Arm Mac.

### Usage

```bash
Usage: macos-virt [OPTIONS] COMMAND [ARGS]...

Options:
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.
  --help                          Show this message and exit.

Commands:
  cp        Copy a file to/from the VM, macos-virt cp default...
  create    Create a new VM.
  delete    Delete a stopped VM.
  ls        List all VMs
  mount     Mount a local directory into the VM.
  profiles  Describe profiles that are available
  shell     Access a shell to the VM
  start     Start an already created VM.
  status    Get high level status of a VM
  stop      Stop a running VM.
  update    Update memory or CPU on a stopped VM

```

## References

[vmcli](https://github.com/gyf304/vmcli) The Swift part of this system is based on vmcli, thanks it wouldnt exist without you.