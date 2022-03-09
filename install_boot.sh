#!/bin/sh -e
mkfs.vfat -n boot -I /dev/vdb
mkdir /tmp/boot
mount /dev/vdb /tmp/boot
cp -var /boot/* /tmp/boot || true
umount /tmp/boot
echo "LABEL=boot      /boot    vfat   defaults        0 1" >> /etc/fstab
mount -a
