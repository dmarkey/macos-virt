from macos_virt.profiles import BaseProfile
from macos_virt.profiles.ubuntu import Ubuntu2004, Ubuntu2104, Ubuntu2110, Ubuntu2004K3S


class Registry:
    profiles = {}

    def add_profile(self, profile: BaseProfile):
        self.profiles[profile.name] = profile

    def get_profiles(self):
        return list(self.profiles.keys())

    def get_profile(self, name) -> BaseProfile:
        return self.profiles[name]


registry = Registry()

registry.add_profile(Ubuntu2004)
registry.add_profile(Ubuntu2104)
registry.add_profile(Ubuntu2110)
registry.add_profile(Ubuntu2004K3S)
