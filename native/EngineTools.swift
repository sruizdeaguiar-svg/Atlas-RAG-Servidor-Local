import AppKit
import Foundation
let identifier = "ai.elementlabs.lmstudio"
func apps() -> [NSRunningApplication] { NSRunningApplication.runningApplications(withBundleIdentifier: identifier).filter { !$0.isTerminated } }
func result(_ value: [String:Any]) { let data = try! JSONSerialization.data(withJSONObject:value); print(String(data:data,encoding:.utf8)!) }
let action = CommandLine.arguments.last ?? "status"
switch action {
case "status": result(["running": !apps().isEmpty, "pids": apps().map { Int($0.processIdentifier) }])
case "start":
 if apps().isEmpty {
  let config = NSWorkspace.OpenConfiguration();config.activates = false
  var finished=false
  NSWorkspace.shared.openApplication(at:URL(fileURLWithPath:"/Applications/LM Studio.app"),configuration:config){_,error in finished=true;if let error=error {fputs(error.localizedDescription,stderr)}}
  let end=Date().addingTimeInterval(15)
  while !finished && Date()<end {RunLoop.current.run(until:Date().addingTimeInterval(0.1))}
 }
 result(["running": !apps().isEmpty])
 if apps().isEmpty {exit(1)}
case "quit":
 let running=apps();for app in running {_ = app.terminate()}
 let end=Date().addingTimeInterval(12)
 while !apps().isEmpty && Date()<end {RunLoop.current.run(until:Date().addingTimeInterval(0.1))}
 for app in apps() {_ = app.forceTerminate()}
 let deadline=Date().addingTimeInterval(3)
 while !apps().isEmpty && Date()<deadline {RunLoop.current.run(until:Date().addingTimeInterval(0.1))}
 result(["running": !apps().isEmpty])
 if !apps().isEmpty {exit(1)}
default: fputs("Use status, start or quit for LM Studio",stderr);exit(1)
}
