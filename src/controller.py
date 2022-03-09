import os
import glob
import pathlib
import random
import xdg as xdg
import json

base_path = os.path.join(xdg.xdg_config_home(), "macos-virt/vms")

pathlib.Path(base_path).mkdir(parents=True, exist_ok=True)


class DuplicateVMException(Exception):
    pass


class Controller:

    @classmethod
    def get_vm_directory(cls, name):
        path = os.path.join(base_path, name)
        pathlib.Path(path).mkdir(exist_ok=True)
        return path

    @classmethod
    def get_valid_vms(cls):
        return [os.path.basename(os.path.dirname(x)) for x in
                glob.glob(f"{base_path}/*/vm.json")]

    @classmethod
    def start(cls, profile, name, cpus, memory, cloudinit):
        if name in cls.get_valid_vms():
            raise DuplicateVMException(f"VM {name} already exists")
        configuration = {
            "memory": memory,
            "cpus": cpus,
            "profile": profile,
            "mac_address": ':'.join('%02x' % random.randint(0,255)
                                    for x in range(6))
        }
        with open(os.path.join(cls.get_vm_directory(name), "vm.json"),
                  "w") as f:
            json.dump(configuration, f)


