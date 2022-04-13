#!/bin/sh -e
mkudffs -m hd -l boot /dev/vdb
mkdir /mnt/boot
mount -t udf /dev/vdb /mnt/boot
cp -var /boot/* /mnt/boot
umount /mnt/boot
echo "/dev/vdb      /boot    udf   defaults        0 0" >> /etc/fstab
mount -a
