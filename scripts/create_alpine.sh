#!/bin/bash -e
RELEASE=3.15
DOWNLOAD_URL=https://dl-cdn.alpinelinux.org/alpine/v$RELEASE/releases/`uname -m`/alpine-minirootfs-$RELEASE.0-`uname -m`.tar.gz
dd if=/dev/zero of=/alpine bs=1M count=1024
mkfs.ext4 /alpine
mkdir /tmp/alpine
mount /alpine /tmp/alpine
cd /tmp/alpine
curl $DOWNLOAD_URL | tar zxvf -
mount --bind /dev /tmp/alpine/dev
mount --bind /sys /tmp/alpine/sys
mount --bind /proc /tmp/alpine/proc
echo "nameserver 8.8.8.8" >> /tmp/alpine/etc/resolv.conf
cat << EOF >> /tmp/alpine/tmp/init.sh
#!/bin/sh
apk update
apk add cloud-init openrc linux-virt py3-pyserial openssh py3-psutil
apk add e2fsprogs-extra udftools
apk add busybox-initscripts bash
apk add openssh-server-pam sudo
rc-update add syslog boot
rc-update add localmount
rc-update add udev-trigger
rc-update add udev-settle
rc-update add cloud-init-local
rc-update add cloud-init
rc-update add cloud-init-hotplugd
rc-update add cloud-final
rc-update add cloud-config
rc-update add hostname
rc-update add networking
rc-update add modules
rc-update add root
rc-update add sshd
rc-update add local
echo "/dev/vda      /    ext4   defaults        0 1" >> /etc/fstab
echo 'root:password' | chpasswd
echo "hvc0::respawn:/sbin/getty -L 0 hvc0 vt100" >> /etc/inittab
echo "alpine" > /etc/hostname
echo "auto eth0" > /etc/network/interfaces
echo "UsePAM yes" >> /etc/ssh/sshd_config
EOF
chroot /tmp/alpine /bin/sh /tmp/init.sh
cp /tmp/alpine/boot/vmlinuz-virt /tmp
cp /tmp/alpine/boot/initramfs-virt /tmp
cd /
umount /tmp/alpine/dev /tmp/alpine/proc /tmp/alpine/sys  /tmp/alpine
rmdir /tmp/alpine
gzip /alpine
