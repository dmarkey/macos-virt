#!/bin/sh -e
mkudffs -m hd -l boot /dev/vdb
mkdir /tmp/boot
mount /dev/vdb /tmp/boot
cp -var /boot/* /tmp/boot || true
umount /tmp/boot
echo "LABEL=boot      /boot    udf   defaults        0 1" >> /etc/fstab
mount -a
