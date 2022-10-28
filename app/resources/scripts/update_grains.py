#!/usr/bin/python
# type: ignore pylint: disable=E0401
"""Script to update grains.

Once sonic_device_util will be available as python3 lib, this script should use it to
fill /etc/salt/grain file directly (grain file can be a python returning a Dict).
"""

import os

import yaml

try:
    import sonic_device_util as sonic_info
    from show.main import get_hw_info_dict
except (ImportError, ModuleNotFoundError):
    from sonic_py_common import device_info as sonic_info
    from sonic_py_common import get_platform_info as get_hw_info_dict


class Grains:
    """Grains handler."""

    def __init__(self, grains_file):
        """Initialize Grains attributes."""
        self.grains_file = grains_file
        self.grains = {}

    def _save(self):
        """Save grains to file."""
        with open(self.grains_file, "w") as grains_file:  # pylint: disable=W1514
            yaml.safe_dump(self.grains, grains_file, default_flow_style=False)

    def load(self):
        """Load grains from file."""
        if os.path.isfile(self.grains_file):
            with open(self.grains_file, "r") as grains_file:  # pylint: disable=W1514
                self.grains = yaml.safe_load(grains_file)

        if not self.grains:
            self.grains = {}

    def _update_version(self):
        """Get fresh version."""
        version_info = sonic_info.get_sonic_version_info()
        hw_info = get_hw_info_dict()
        self.grains = {
            "nos": "sonic",
            "sonic_asic_type": version_info["asic_type"],
            "sonic_build_date": version_info["build_date"],
            "sonic_build_version": version_info["build_version"],
            "sonic_commit_id": version_info["commit_id"],
            "sonic_built_by": version_info["built_by"],
            "hwsku": hw_info["hwsku"],
        }

    def update(self):
        """Get fresh info and write the new grains file."""
        self._update_version()
        self._save()


if __name__ == "__main__":
    grains = Grains("/etc/salt/grains")
    grains.load()
    grains.update()
