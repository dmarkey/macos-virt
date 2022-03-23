PREFIX?=/usr/local

.PHONY: all clean install

all: macos_virt/macos_virt_runner/macos_virt/macos_virt_runner

build:
	mkdir -p macos_virt/macos_virt_runner

macos_virt/macos_virt_runner/macos_virt/macos_virt_runner: build vmcli/Sources/vmcli/main.swift vmcli/Package.swift
	cd vmcli && xcrun swift build -c release --arch arm64 --arch x86_64
	cp vmcli/.build/apple/Products/Release/vmcli macos_virt/macos_virt_runner/macos_virt_runner
	chmod +x macos_virt/macos_virt_runner/macos_virt_runner

clean:
	rm -rf macos_virt/macos_virt_runner

