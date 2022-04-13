#!/bin/sh -e
nohup python3 /usr/sbin/macos-virt-service.py &
depmod -a
mkudffs -m hd -l boot /dev/vdb
mkdir /tmp/boot
mount /dev/vdb /tmp/boot
cp -var /boot/* /tmp/boot
umount /tmp/boot
echo "/dev/vdb      /boot    udf   defaults        0 1" >> /etc/fstab
mount -a
