#!/usr/bin/env python
import platform
from distutils.core import setup
from distutils.version import StrictVersion
import sys
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

mac_version = platform.mac_ver()[0]

if not mac_version:
    print('This package only works on Mac, Sorry.')
    sys.exit(1)
mac_version = StrictVersion(mac_version)
if mac_version < StrictVersion("12.3"):
    print('This package has been tested on MacOS 12.3, Please upgrade.')
    sys.exit(1)


setup(name='macos-virt',
      version='0.1.1',
      description='MacOS utility to run Linux using Virtualization.Framework',
      author='David Markey',
      author_email='david@dmarkey.com',
      url='https://github.com/dmarkey/macos-virt',
      packages=['macos_virt', "macos_virt.profiles", "macos_virt.service"],
      entry_points={
          'console_scripts': [
              'macos-virt=macos_virt.main:main',
          ]
      },
      include_package_data=True,
      classifiers=['Development Status :: 3 - Alpha',
                   'License :: OSI Approved :: MIT License'],
      long_description=long_description,
      long_description_content_type='text/markdown',
      install_requires=[
          'appdirs==1.4.4',
          "click==8.0.4",
          "commonmark==0.9.1",
          "fs==2.4.15",
          "pycdlib==1.12.0",
          "pyfatfs==1.0.3",
          "Pygments==2.11.2",
          "pyserial==3.5",
          "pytz==2022.1",
          "PyYAML==6.0",
          "rich==12.0.0",
          "six==1.16.0",
          "typer==0.4.0",
          "xdg==5.1.1"
      ],
      package_data={
          "macos_virt": ["macos_virt_runner/macos_virt_runner",
                         "macos_virt_runner/macos_virt_runner.entitlements",
                         "profiles/ubuntu-cloudinit.yaml"],
          "macos_virt.service": ["install_boot.sh", "macos-virt-service.service"
                                                    "docker-service-override.conf"],
      }
      )
