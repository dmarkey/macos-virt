//
//  main.swift
//  virt
//
//  Created by Alexander Pinske on 06.12.20.
//

import Virtualization

struct ConfigObj: Decodable {
    let cpus: Int
    let memory: Int
    let share_home: Bool
    let mac: String
    let kernel: String
    let initrd: String!
    
}

let fileManager = FileManager()

func cleanup_files(){

    try? fileManager.removeItem(atPath: "pid.file")
 
  }

let data = try Data(contentsOf: URL(fileURLWithPath: "./boot_config.json"))
let vmConfig: ConfigObj = try! JSONDecoder().decode(ConfigObj.self, from: data)
let verbose = CommandLine.arguments.contains("-v")

let tcattr = UnsafeMutablePointer<termios>.allocate(capacity: 1)
tcgetattr(FileHandle.standardInput.fileDescriptor, tcattr)
let oldValue = tcattr.pointee.c_lflag
atexit {
    tcattr.pointee.c_lflag = oldValue
    tcsetattr(FileHandle.standardInput.fileDescriptor, TCSAFLUSH, tcattr)
    tcattr.deallocate()
}
tcattr.pointee.c_lflag &= ~UInt(ECHO | ICANON | ISIG)
tcsetattr(FileHandle.standardInput.fileDescriptor, TCSAFLUSH, tcattr)

let config = VZVirtualMachineConfiguration()
config.cpuCount = 2
config.memorySize = 4 * 1024 * 1024 * 1024

do {
    let vda = try VZDiskImageStorageDeviceAttachment(url: URL(fileURLWithPath: "root.img"), readOnly: false)
    let vdb = try VZDiskImageStorageDeviceAttachment(url: URL(fileURLWithPath: "boot.img"), readOnly: false)
    config.storageDevices = [VZVirtioBlockDeviceConfiguration(attachment: vda), VZVirtioBlockDeviceConfiguration(attachment: vdb)]
} catch {
    fatalError("Virtual Machine Storage Error: \(error)")
}

config.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]

let network = VZVirtioNetworkDeviceConfiguration()
network.macAddress = VZMACAddress(string: vmConfig.mac)!

network.attachment = VZNATNetworkDeviceAttachment()
config.networkDevices = [network]

let bootloader = VZLinuxBootLoader(kernelURL: URL(fileURLWithPath: vmConfig.kernel))
if vmConfig.initrd != nil{
    bootloader.initialRamdiskURL = URL(fileURLWithPath: vmConfig.initrd)
}
bootloader.commandLine = "console=hvc0 root=/dev/vda" + (verbose ? "" : " quiet")
config.bootLoader = bootloader

let fs0 = VZVirtioFileSystemDeviceConfiguration(tag: "fs0")
fs0.share = VZMultipleDirectoryShare(directories: [
    "home": VZSharedDirectory(url: FileManager.default.homeDirectoryForCurrentUser, readOnly: false),
])
config.directorySharingDevices = [fs0]
/*#if compiler(>=5.7)
if VZLinuxRosettaDirectoryShare.availability == .installed {
    let rosetta = VZVirtioFileSystemDeviceConfiguration(tag: "rosetta")
    rosetta.share = try VZLinuxRosettaDirectoryShare()
    config.directorySharingDevices += [rosetta]
}
#endif*/

let serial = VZVirtioConsoleDeviceSerialPortConfiguration()
serial.attachment = VZFileHandleSerialPortAttachment(
    fileHandleForReading: FileHandle.standardInput,
    fileHandleForWriting: FileHandle.standardOutput
)
config.serialPorts = [serial]

do {
    try config.validate()
} catch {
    fatalError("Virtual Machine Config Error: \(error)")
}
let vm = VZVirtualMachine(configuration: config)
class VMDelegate : NSObject, VZVirtualMachineDelegate {
    func guestDidStop(_ virtualMachine: VZVirtualMachine) {
        if verbose { NSLog("Virtual Machine Stopped") }
        exit(0)
    }

    func virtualMachine(_ virtualMachine: VZVirtualMachine, didStopWithError error: Error) {
        fatalError("Virtual Machine Run Error: \(error)")
    }
}
let delegate = VMDelegate()
vm.delegate = delegate
vm.start { result in
    switch result {
    case .success:
        if verbose { NSLog("Virtual Machine Started") }
    case let .failure(error):
        fatalError("Virtual Machine Start Error: \(error)")
    }
}
let pid = String(getpid())
fileManager.createFile(atPath: "pid.file", contents: pid.data(using: .utf8))

NSWorkspace.shared.notificationCenter.addObserver(
      forName: NSWorkspace.didWakeNotification, object: nil, queue: nil,
      using: { _ in

            })

dispatchMain()
