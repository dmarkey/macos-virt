# Macos-Virt

A utility to get up and running with MacOS's Virtualization.Framework in 5 minutes.

[![asciicast](https://asciinema.org/a/pHX3Kjn7BHC6DSukRkKaIntw2.svg)](https://asciinema.org/a/pHX3Kjn7BHC6DSukRkKaIntw2)

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

> :warning: **This package contains a swift binary called macos-virt-runner. It is not signed. An attempt is made to sign it using your Mac's inbuilt cert, if this causes you any problems open an issue.**

> :warning: **This is alpha software. Please don't run your production DB on this.**

### Features

* Quickstart seamless setup, 5 minutes until your VM is ready to use.
* Any prerequisite kernels/initrds/root filesystems are downloaded automatically.
* Selection of VM profiles (all based on ubuntu for now)
* Ability to copy files to/from the VM
* Uses latest kernel in your VM to boot - Kernel updates are applied.
* Wake from Suspend notification to keep VM time in sync
* Mount Host directories to the VM using sshfs (Native Virtualization.Framework implementation seems unreliable)
* Shell Completion
* Less than 1MB in size (slightly more with dependencies)

# What it doesn't do

* MacOS guests
* Memory Ballooning
* VM Suspend/Resume
* Any Graphical Desktops

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
  cp        Copy a file to/from a running VM, macos-virt cp default...
  create    Create a new VM
  ls        List all VMs
  mount     Mount a local directory into the VM
  profiles  Describe profiles that are available
  rm        Delete a stopped VM
  shell     Access a shell to a running VM
  start     Start an already created VM
  status    Get high level status of a running VM
  stop      Stop a running VM
  umount    Unmount a directory in the VM
  update    Update memory or CPU on a stopped VM
  version   Show Version information

```
### Quickstart

```
(venv) ➜  macos-virt git:(main) ✗ macos-virt create --name=default --profile=ubuntu-20.04
Creating Boot image... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
Expanding Root Image... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
🥚 VM has been created
🐣 VM has made first contact
🐥 Initialization complete
Uptime                                  66 seconds
CPU Count                               1
CPU Usage                               53.3%
Process Count                           101
Memory Usage                            17.9%
Root Filesystem Usage                   37.5%
Network Addresses                       [['192.168.64.31', '255.255.255.0']]
(venv) ➜  macos-virt git:(main) ✗ macos-virt shell default
Warning: Permanently added '192.168.64.31' (ED25519) to the list of known hosts.
Welcome to Ubuntu 20.04.4 LTS (GNU/Linux 5.4.0-100-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

  System information as of Thu Mar 24 16:11:25 UTC 2022

  System load:             0.63
  Usage of /:              37.6% of 4.70GB
  Memory usage:            15%
  Swap usage:              0%
  Processes:               108
  Users logged in:         0
  IPv4 address for enp0s1: 192.168.64.31
  IPv6 address for enp0s1: fd32:490d:5ffc:3690:5054:ff:fe6d:5522

0 updates can be applied immediately.


*** System restart required ***

The programs included with the Ubuntu system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Ubuntu comes with ABSOLUTELY NO WARRANTY, to the extent permitted by
applicable law.

To run a command as administrator (user "root"), use "sudo <command>".
See "man sudo_root" for details.

macos-virt@ubuntu:~$ sudo poweroff
macos-virt git:(main) ✗ macos-virt start default
💾 Booting with Kernel vmlinuz-5.4.0-105-generic and Ramdisk initrd.img-5.4.0-105-generic from Boot volume
/Users/dmarkey/src/macos-virt/macos_virt/macos_virt_runner/macos_virt_runner: replacing existing signature
🥚 VM has been created
🐣 VM has made first contact
🐥 Initialization complete
Uptime                                  12 seconds
CPU Count                               1
CPU Usage                               89.6%
Process Count                           95
Memory Usage                            15.4%
Root Filesystem Usage                   37.6%
Network Addresses                       [['192.168.64.31', '255.255.255.0']]
(venv) ➜  macos-virt git:(main) ✗ macos-virt shell default
Welcome to Ubuntu 20.04.4 LTS (GNU/Linux 5.4.0-105-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

  System information as of Thu Mar 24 16:13:18 UTC 2022

  System load:             0.57
  Usage of /:              37.5% of 4.70GB
  Memory usage:            10%
  Swap usage:              0%
  Processes:               100
  Users logged in:         0
  IPv4 address for enp0s1: 192.168.64.31
  IPv6 address for enp0s1: fd32:490d:5ffc:3690:5054:ff:fe6d:5522


0 updates can be applied immediately.


Last login: Thu Mar 24 16:11:26 2022 from 192.168.64.1
macos-virt@ubuntu:~$ uname -a
Linux ubuntu 5.4.0-105-generic #119-Ubuntu SMP Mon Mar 7 18:49:24 UTC 2022 x86_64 x86_64 x86_64 GNU/Linux

```

### Profiles

| Profile Name          | Description                                                                   |
|-----------------------|-------------------------------------------------------------------------------|
| ubuntu-20.04(default) | Ubuntu 20.04 Server Cloud Image                                               |
| ubuntu-21.04          | Ubuntu 21.04 Server Cloud Image                                               |
| ubuntu-21.10          | Ubuntu 21.10 Server Cloud Image                                               |
| ubuntu-20.04-k3s      | Ubuntu 20.04 Server Cloud Image with K3S and Docker (Qemu emulation included) |

## References

[vmcli](https://github.com/gyf304/vmcli) The Swift part of this system is based on vmcli, thanks it wouldnt exist
without you.