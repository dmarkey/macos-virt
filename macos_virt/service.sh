#!/bin/sh -e

MACOS_VIRT_DIRECTORY=/var/lib/macos-virt
CONTROL_DIRECTORY=$MACOS_VIRT_DIRECTORY/control


sync_time(){
  echo "Setting time"
  rdate -s time.nist.gov || rdate -s time.nist.gov || rdate -s time.nist.gov || echo "Failed to set time."
}

detect_ip() {
  IP_ADDRESS=""
  touch $CONTROL_DIRECTORY/ip_not_detected
  while [ "$IP_ADDRESS" = "" ] ; do
    IP_ADDRESS=$(ip addr | grep "inet " | grep 192.168 | cut -d " " -f6 | cut -d "/" -f1)
    sleep 1;
  done
  echo "$IP_ADDRESS" >> "$CONTROL_DIRECTORY"/ip
  rm $CONTROL_DIRECTORY/ip_not_detected
}


inject_ssh_key(){
  mkdir -p ~macos-virt/.ssh/
  cat "$CONTROL_DIRECTORY"/ssh_key >> ~macos-virt/.ssh/authorized_keys
}


main_loop(){
  while true ; do

    if [ -f "$CONTROL_DIRECTORY"/time_sync ] ; then
      echo "Setting time"
      sync_time_wrapper
      rm "$CONTROL_DIRECTORY"/time_sync
    fi
    if [ -f "$CONTROL_DIRECTORY"/poweroff ] ; then
      echo "Powering off"
      rm "$CONTROL_DIRECTORY"/poweroff
      poweroff
      exit
    fi
    echo "MemoryUsage:" $(free | grep Mem | awk '{print $3/$2 * 100.0}') > "$CONTROL_DIRECTORY"/heartbeat_tmp
    echo "CPUUsage:" $(grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage }') >> "$CONTROL_DIRECTORY"/heartbeat_tmp
    echo "RootFsUsage:" $(df -h / | tail -1 | awk '{ print $5 }' | tr -d "%" ) >> "$CONTROL_DIRECTORY"/heartbeat_tmp
    mv "$CONTROL_DIRECTORY"/heartbeat_tmp "$CONTROL_DIRECTORY"/heartbeat
    sleep 1
  done
}

resize_root(){
  resize2fs /dev/vda
}
mount_usr_directory(){
  if [ -f "$CONTROL_DIRECTORY"/mnt_usr_directory ] ; then
    usr_directory=$(cat "$CONTROL_DIRECTORY"/mnt_usr_directory)
    if [ ! -d "$usr_directory" ] ; then
      mkdir -p "$usr_directory"
      mount -t virtiofs user-home "$usr_directory"
    fi
  fi
}

rotate_host_sshd_key(){
  rm /etc/ssh/ssh_host_*
  ssh-keygen -f /etc/ssh/ssh_host_rsa_key     -N '' -q -t rsa
  ssh-keygen -f /etc/ssh/ssh_host_ecdsa_key   -N '' -q -t ecdsa
  ssh-keygen -f /etc/ssh/ssh_host_ed25519_key -N '' -q -t ed25519
  pkill -HUP sshd
}

inject_ssh_key
detect_ip

if [ ! -f "$MACOS_VIRT_DIRECTORY"/initialized ] ; then
  rotate_host_sshd_key
  inject_ssh_key
  touch "$MACOS_VIRT_DIRECTORY"/initialized
fi
resize_root
mount_usr_directory
sync_time
main_loop
