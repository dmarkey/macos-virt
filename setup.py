#!/usr/bin/env python

from distutils.core import setup

setup(name='macos-virt',
      version='1.0',
      description='MacOS utility to run Linux using Virtualization.Framework',
      author='David Markey',
      author_email='david@dmarkey.com',
      url='https://github.com/dmarkey/macos-virt',
      packages=['macos_virt', "macos_virt.profiles"],
      entry_points={
          'console_scripts': [
              'macos-virt=macos_virt.main:main',
          ]
      },
      include_package_data=True,
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
                         "profiles/ubuntu-cloudinit-k3s.yaml",
                         "profiles/ubuntu-cloudinit.yaml"],
       }
     )
