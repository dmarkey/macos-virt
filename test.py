#!env python3
import tarfile
import urllib.request
import gzip
urllib.request.urlretrieve("https://cloud-images.ubuntu.com/releases/focal/release/unpacked/ubuntu-20.04-server-cloudimg-amd64-vmlinuz-generic", "kernel")
urllib.request.urlretrieve("https://cloud-images.ubuntu.com/releases/focal/release/unpacked/ubuntu-20.04-server-cloudimg-amd64-initrd-generic", "initrd")
urllib.request.urlretrieve("https://cloud-images.ubuntu.com/releases/focal/release/ubuntu-20.04-server-cloudimg-amd64.tar.gz", "image.tar.gz")
tf = tarfile.open("image.tar.gz")
tf.extractall()
tf.close()
try:
    kern = gzip.open("kernel")
    uncompressed = kern.read()
    kern.close()
    with open("kernel", "wb") as f:
        f.write(uncompressed)
except gzip.BadGzipFile:
    pass

