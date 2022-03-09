from profiles import BaseProfile
from profiles.ubuntu import Ubuntu2004


class Registry:
    profiles = {}

    def add_profile(self, profile: BaseProfile):
        self.profiles[profile.name] = profile

    def get_distributions(self):
        return list(self.profiles.keys())

    def get_versions_for(self, name):
        return sorted(list(self.profiles.keys()))

    def get_profile(self, name):
        return self.profiles[name]


registry = Registry()

registry.add_profile(Ubuntu2004)
