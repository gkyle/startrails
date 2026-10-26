import AppKit

final class Installer: NSObject, NSApplicationDelegate {
  private var window: NSWindow!
  private var status: NSTextField!
  private var log: NSTextView!
  private var closeButton: NSButton!
  private var process: Process?

  func applicationDidFinishLaunching(_ notification: Notification) {
    NSApp.setActivationPolicy(.regular)

    let content = NSView(frame: NSRect(x: 0, y: 0, width: 640, height: 420))
    status = NSTextField(labelWithString: "Installing StarTrails AI…")
    status.font = NSFont.boldSystemFont(ofSize: 16)
    status.frame = NSRect(x: 20, y: 375, width: 600, height: 25)
    content.addSubview(status)

    let scroll = NSScrollView(frame: NSRect(x: 20, y: 65, width: 600, height: 295))
    scroll.hasVerticalScroller = true
    scroll.borderType = .bezelBorder
    log = NSTextView(frame: scroll.bounds)
    log.isEditable = false
    log.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
    scroll.documentView = log
    content.addSubview(scroll)

    closeButton = NSButton(title: "Close", target: self, action: #selector(close))
    closeButton.frame = NSRect(x: 530, y: 20, width: 90, height: 30)
    closeButton.isEnabled = false
    content.addSubview(closeButton)

    window = NSWindow(
      contentRect: content.frame,
      styleMask: [.titled, .miniaturizable],
      backing: .buffered,
      defer: false
    )
    window.title = "Install StarTrails AI"
    window.contentView = content
    window.center()
    window.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    startInstallation()
  }

  private func startInstallation() {
    guard let script = Bundle.main.url(forResource: "install", withExtension: "sh") else {
      finish("Installer script is missing.", succeeded: false)
      return
    }

    let output = Pipe()
    output.fileHandleForReading.readabilityHandler = { [weak self] handle in
      let data = handle.availableData
      guard !data.isEmpty else {
        handle.readabilityHandler = nil
        return
      }
      DispatchQueue.main.async {
        self?.log.textStorage?.append(
          NSAttributedString(string: String(decoding: data, as: UTF8.self)))
        self?.log.scrollToEndOfDocument(nil)
      }
    }

    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/bin/bash")
    process.arguments = [script.path]
    process.standardOutput = output
    process.standardError = output
    process.terminationHandler = { [weak self] task in
      DispatchQueue.main.async {
        let succeeded = task.terminationStatus == 0
        self?.finish(
          succeeded ? "StarTrails AI is ready." : "Installation failed. See the output below.",
          succeeded: succeeded
        )
      }
    }
    self.process = process
    do {
      try process.run()
    } catch {
      finish("Could not start the installer: \(error)", succeeded: false)
    }
  }

  private func finish(_ message: String, succeeded: Bool) {
    status.stringValue = message
    closeButton.isEnabled = true
    if !succeeded {
      NSApp.requestUserAttention(.criticalRequest)
    }
  }

  @objc private func close() {
    NSApp.terminate(nil)
  }
}

let application = NSApplication.shared
let installer = Installer()
application.delegate = installer
application.run()
