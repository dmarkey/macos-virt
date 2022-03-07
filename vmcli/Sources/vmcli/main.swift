import ArgumentParser
import Darwin.C
import Foundation
import Virtualization

enum BootLoader: String, ExpressibleByArgument {
  case linux
}

enum SizeSuffix: UInt64, ExpressibleByArgument {
  case none = 1
  case
    KB = 1000
  case KiB = 0x400
  case
    MB = 1_000_000
  case MiB = 0x100000
  case
    GB = 1_000_000_000
  case GiB = 0x4000_0000
}

var origStdinTerm: termios? = nil
var origStdoutTerm: termios? = nil

var vm: VZVirtualMachine? = nil

var stopRequested = false

// mask TERM signals so we can perform clean up
let signalMask = SIGPIPE | SIGINT | SIGTERM
signal(signalMask, SIG_IGN)
let sigintSrc = DispatchSource.makeSignalSource(signal: signalMask, queue: .main)
sigintSrc.setEventHandler {
  quit(1)
}
sigintSrc.resume()

// mask TERM signals so we can perform clean up
let signalMaskHup = SIGHUP
signal(signalMaskHup, SIG_IGN)
let sigintSrcHup = DispatchSource.makeSignalSource(signal: signalMask, queue: .main)
sigintSrcHup.setEventHandler {

}
sigintSrcHup.resume()

func resetTty() {
  if origStdinTerm != nil {
    tcsetattr(0, TCSANOW, &origStdinTerm!)
  }
  if origStdoutTerm != nil {
    tcsetattr(1, TCSANOW, &origStdoutTerm!)
  }
}

func quit(_ code: Int32) -> Never {
  resetTty()
  return exit(code)
}

func openDisk(path: String, readOnly: Bool) throws -> VZVirtioBlockDeviceConfiguration {
  let vmDiskURL = URL(fileURLWithPath: path)
  let vmDisk: VZDiskImageStorageDeviceAttachment
  do {
    vmDisk = try VZDiskImageStorageDeviceAttachment(url: vmDiskURL, readOnly: readOnly)
  } catch {
    throw error
  }
  let vmBlockDevCfg = VZVirtioBlockDeviceConfiguration(attachment: vmDisk)
  return vmBlockDevCfg
}

@available(macOS 12, *)
func openFolder(path: String) throws -> VZDirectorySharingDeviceConfiguration {
  let sharedDirectory = VZSharedDirectory(url: URL(fileURLWithPath: path), readOnly: false)
  let vzDirShare = VZVirtioFileSystemDeviceConfiguration(tag: path)
  vzDirShare.share = VZSingleDirectoryShare(directory: sharedDirectory)
  return vzDirShare
}

class OccurrenceCounter {
  let pattern: Data
  var i = 0
  init(_ pattern: Data) {
    self.pattern = pattern
  }

  func process(_ data: Data) -> Int {
    if pattern.count == 0 {
      return 0
    }
    var occurrences = 0
    for byte in data {
      if byte == pattern[i] {
        i += 1
        if i >= pattern.count {
          occurrences += 1
          i = 0
        }
      } else {
        i = 0
      }
    }
    return occurrences
  }
}

class VMCLIDelegate: NSObject, VZVirtualMachineDelegate {
  func guestDidStop(_ virtualMachine: VZVirtualMachine) {
    quit(0)
  }
  func virtualMachine(_ virtualMachine: VZVirtualMachine, didStopWithError error: Error) {
    quit(1)
  }
}

let delegate = VMCLIDelegate()

let vmCfg = VZVirtualMachineConfiguration()

struct VMCLI: ParsableCommand {
  @Option(name: .shortAndLong, help: "CPU count")
  var cpuCount: Int = 1

  @Option(name: .shortAndLong, help: "Memory Bytes")
  var memorySize: UInt64 = 512  // 512 MiB default

  @Option(name: .long, help: "Memory Size Suffix")
  var memorySizeSuffix: SizeSuffix = SizeSuffix.MiB

  @Option(name: [.short, .customLong("disk")], help: "Disks to use")
  var disks: [String] = []

  @Option(name: [.customLong("cdrom")], help: "CD-ROMs to use")
  var cdroms: [String] = []

  #if EXTRA_WORKAROUND_FOR_BIG_SUR
    // See comment below for similar #if
  #else
    @available(macOS 12, *)
    @Option(name: [.short, .customLong("folder")], help: "Folders to share")
    var folders: [String] = []
  #endif

  @Option(
    name: [.short, .customLong("network")],
    help: """
      Networks to use. e.g. aa:bb:cc:dd:ee:ff@nat for a nat device, \
      or ...@en0 for bridging to en0. \
      Omit mac address for a generated address.
      """)
  var networks: [String] = ["nat"]

  @Option(help: "Enable / Disable Memory Ballooning")
  var balloon: Bool = true

  @Option(name: .shortAndLong, help: "Bootloader to use")
  var bootloader: BootLoader = BootLoader.linux

  @Option(name: .shortAndLong, help: "Kernel to use")
  var kernel: String?

  @Option(name: .shortAndLong, help: "Pid file to write")
  var pidfile: String?

  @Option(name: .shortAndLong, help: "Serial Console Symlink Path")
  var consoleSymlink: String?

  @Option(name: .shortAndLong, help: "Serial Control Symlink Path")
  var controlSymlink: String?

  @Option(help: "Initrd to use")
  var initrd: String?

  @Option(help: "Kernel cmdline to use")
  var cmdline: String?

  @Option(help: "Escape Sequence, when using a tty")
  var escapeSequence: String = "q"

  mutating func run() throws {
    vmCfg.cpuCount = cpuCount
    vmCfg.memorySize = memorySize * memorySizeSuffix.rawValue

    // set up bootloader
    switch bootloader {
    case BootLoader.linux:
      if kernel == nil {
        throw ValidationError("Kernel not specified")
      }
      let vmKernelURL = URL(fileURLWithPath: kernel!)
      let vmBootLoader = VZLinuxBootLoader(kernelURL: vmKernelURL)
      if initrd != nil {
        vmBootLoader.initialRamdiskURL = URL(fileURLWithPath: initrd!)
      }
      if cmdline != nil {
        vmBootLoader.commandLine = cmdline!
      }
      vmCfg.bootLoader = vmBootLoader
    }

    // set up tty
    //let vmSerialIn = Pipe()
    //let vmSerialOut = Pipe()
    var amasterconsole: Int32 = 0
    var aslaveconsole: Int32 = 0
    if openpty(&amasterconsole, &aslaveconsole, nil, nil, nil) == -1 {
      print("Failed to open pty")
      quit(1)
    }
    print(String(cString: ttyname(aslaveconsole)))
    var amastercontrol: Int32 = 0
    var aslavecontrol: Int32 = 0
    if openpty(&amastercontrol, &aslavecontrol, nil, nil, nil) == -1 {
      print("Failed to open pty")
      quit(1)
    }

    print(String(cString: ttyname(aslavecontrol)))
    let fileManager = FileManager()
    if controlSymlink != nil {
      try? fileManager.createSymbolicLink(
        atPath: controlSymlink!, withDestinationPath: String(cString: ttyname(aslavecontrol)))

    }

    if consoleSymlink != nil {
      try? fileManager.createSymbolicLink(
        atPath: consoleSymlink!, withDestinationPath: String(cString: ttyname(aslaveconsole)))

    }

    if pidfile != nil {
      let pid = String(getpid())
      fileManager.createFile(atPath: pidfile!, contents: pid.data(using: .utf8))
    }
    let vmConsoleCfg = VZVirtioConsoleDeviceSerialPortConfiguration()
    let vmSerialPort = VZFileHandleSerialPortAttachment(
      fileHandleForReading: FileHandle(fileDescriptor: amasterconsole),
      fileHandleForWriting: FileHandle(fileDescriptor: amasterconsole)
    )
    let vmControlCfg = VZVirtioConsoleDeviceSerialPortConfiguration()

    let vmSerialPortControl = VZFileHandleSerialPortAttachment(
      fileHandleForReading: FileHandle(fileDescriptor: amastercontrol),
      fileHandleForWriting: FileHandle(fileDescriptor: amastercontrol)
    )
    vmConsoleCfg.attachment = vmSerialPort
    vmControlCfg.attachment = vmSerialPortControl
    vmCfg.serialPorts = [vmConsoleCfg, vmControlCfg]
    NSWorkspace.shared.notificationCenter.addObserver(
      forName: NSWorkspace.didWakeNotification, object: nil, queue: nil,
      using: { _ in

        let timeUpdateMessage =
          [
            "message_type": "time_update",
            "time": Int(Date().timeIntervalSince1970),
          ] as [String: Any]

        do {
          var jsonData = try JSONSerialization.data(withJSONObject: timeUpdateMessage)

          jsonData.append(10)

          jsonData.withUnsafeBytes { rawBufferPointer in
            let rawPtr = rawBufferPointer.baseAddress!
            write(amastercontrol, rawPtr, rawBufferPointer.count)
          }
          //do something with myStruct
        } catch {
          //do something with error
        }

      })

    // set up storage
    // TODO: better error handling
    vmCfg.storageDevices = []
    for disk in disks {
      try vmCfg.storageDevices.append(openDisk(path: disk, readOnly: false))
    }
    for cdrom in cdroms {
      try vmCfg.storageDevices.append(openDisk(path: cdrom, readOnly: true))
    }
    // The #available check still causes a runtime dyld error on macOS 11 (Big Sur),
    // apparently due to a Swift bug, so add an extra check to work around this until
    // the bug is resolved. See eg https://developer.apple.com/forums/thread/688678
    #if EXTRA_WORKAROUND_FOR_BIG_SUR
    #else
      if #available(macOS 12, *) {
        for folder in folders {
          puts("Adding shared folder '\(folder)', but be warned, this might be unstable.")
          try vmCfg.directorySharingDevices.append(openFolder(path: folder))
        }
      }
    #endif
    // set up networking
    // TODO: better error handling
    vmCfg.networkDevices = []
    for network in networks {
      let netCfg = VZVirtioNetworkDeviceConfiguration()
      let parts = network.split(separator: "@")
      var device = String(parts[0])
      if parts.count > 1 {
        netCfg.macAddress = VZMACAddress(string: String(parts[0]))!
        device = String(parts[1])
      }
      switch device {
      case "nat":
        netCfg.attachment = VZNATNetworkDeviceAttachment()
      default:
        for iface in VZBridgedNetworkInterface.networkInterfaces {
          if iface.identifier == network {
            netCfg.attachment = VZBridgedNetworkDeviceAttachment(interface: iface)
            break
          }
        }
        if netCfg.attachment == nil {
          throw ValidationError("Cannot find network: \(network)")
        }
      }
      vmCfg.networkDevices.append(netCfg)
    }

    // set up memory balloon
    let balloonCfg = VZVirtioTraditionalMemoryBalloonDeviceConfiguration()
    vmCfg.memoryBalloonDevices = [balloonCfg]

    vmCfg.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]

    try vmCfg.validate()

    // start VM
    vm = VZVirtualMachine(configuration: vmCfg)
    vm!.delegate = delegate

    vm!.start(completionHandler: { (result: Result<Void, Error>) -> Void in
      switch result {
      case .success:
        return
      case .failure(let error):
        FileHandle.standardError.write(error.localizedDescription.data(using: .utf8)!)
        FileHandle.standardError.write("\n".data(using: .utf8)!)
        quit(1)
      }
    })

    RunLoop.main.run()
  }
}

VMCLI.main()
