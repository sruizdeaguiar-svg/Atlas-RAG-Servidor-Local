import Cocoa
import WebKit
import CoreImage.CIFilterBuiltins

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKDownloadDelegate, WKUIDelegate {
 var window:NSWindow!; var web:WKWebView!; var statusLabel:NSTextField!; var memoryLabel:NSTextField!; var startButton:NSButton!;var stopButton:NSButton!;var restartButton:NSButton!
 var logsButton:NSButton!;var browserButton:NSButton!
 var timer:Timer?;var setupPending=false;var loading=false;var serviceURL="";var statePath="";var secretPath="";var project="";var currentRunning=false;var networkInfo:[String:Any]=[:]
 var english:Bool { UserDefaults.standard.string(forKey:"AtlasLanguage")=="en" }
 func tr(_ es:String,_ en:String)->String { english ? en:es }
 func applicationDidFinishLaunching(_ notification:Notification) {
  let args=CommandLine.arguments
  project=Bundle.main.resourceURL!.appendingPathComponent("runtime").path
  if let i=args.firstIndex(of:"--state-dir"),i+1<args.count {statePath=args[i+1];secretPath=statePath}
  else {
   let source=(try? String(contentsOf:Bundle.main.resourceURL!.appendingPathComponent("source.path"),encoding:.utf8))?.trimmingCharacters(in:.whitespacesAndNewlines)
   let suggested=FileManager.default.fileExists(atPath:"/Volumes/Seguridad") ? "/Volumes/Seguridad/Atlas RAG/datos" : FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Atlas RAG").path
   let defaultData=source.flatMap{FileManager.default.fileExists(atPath:$0) ? URL(fileURLWithPath:$0).appendingPathComponent("datos").path : nil} ?? suggested
   statePath=UserDefaults.standard.string(forKey:"AtlasStateDirectory") ?? defaultData
   secretPath=UserDefaults.standard.string(forKey:"AtlasSecretDirectory") ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Atlas RAG Credentials").path
  }
  var vaults=UserDefaults.standard.dictionary(forKey:"AtlasCredentialDirectories") as? [String:String] ?? [:]
  vaults[statePath]=secretPath;UserDefaults.standard.set(vaults,forKey:"AtlasCredentialDirectories")
  buildMenu()
  window=NSWindow(contentRect:NSRect(x:0,y:0,width:1300,height:900),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
  window.title="Atlas RAG Local";window.minSize=NSSize(width:850,height:650);window.delegate=self;window.center()
  let container=NSView(frame:NSRect(x:0,y:0,width:1300,height:900));container.autoresizingMask=[.width,.height];window.contentView=container
  let bar=NSView();bar.translatesAutoresizingMaskIntoConstraints=false;container.addSubview(bar)
  startButton=NSButton(title:tr("Arrancar","Start"),target:self,action:#selector(startServer));stopButton=NSButton(title:tr("Parar","Stop"),target:self,action:#selector(stopServer));restartButton=NSButton(title:tr("Reiniciar","Restart"),target:self,action:#selector(restartServer))
  logsButton=NSButton(title:tr("Registros","Logs"),target:self,action:#selector(openLogs));browserButton=NSButton(title:tr("Abrir navegador","Open browser"),target:self,action:#selector(openBrowser));let logs=logsButton!;let browser=browserButton!;let language=NSButton(title:"ES / EN",target:self,action:#selector(toggleLanguage))
  statusLabel=NSTextField(labelWithString:tr("Preparando servidor…","Preparing server…"));statusLabel.font=NSFont.systemFont(ofSize:11,weight:.medium)
  memoryLabel=NSTextField(labelWithString:"");memoryLabel.maximumNumberOfLines=2;memoryLabel.lineBreakMode = .byTruncatingMiddle;memoryLabel.font=NSFont.monospacedDigitSystemFont(ofSize:10,weight:.regular);memoryLabel.textColor = .secondaryLabelColor
  let controls=NSStackView(views:[startButton,stopButton,restartButton,logs,browser,language,statusLabel]);controls.spacing=10;controls.translatesAutoresizingMaskIntoConstraints=false;bar.addSubview(controls)
  memoryLabel.translatesAutoresizingMaskIntoConstraints=false;bar.addSubview(memoryLabel)
  let config=WKWebViewConfiguration();let controller=WKUserContentController();controller.add(self,name:"chooseFolder");controller.add(self,name:"openExternal");config.userContentController=controller
  web=WKWebView(frame:NSRect(x:0,y:0,width:1300,height:823),configuration:config);web.translatesAutoresizingMaskIntoConstraints=false;web.navigationDelegate=self;web.uiDelegate=self;container.addSubview(web)
  NSLayoutConstraint.activate([bar.topAnchor.constraint(equalTo:container.topAnchor),bar.leadingAnchor.constraint(equalTo:container.leadingAnchor),bar.trailingAnchor.constraint(equalTo:container.trailingAnchor),bar.heightAnchor.constraint(equalToConstant:77),controls.topAnchor.constraint(equalTo:bar.topAnchor,constant:12),controls.leadingAnchor.constraint(equalTo:bar.leadingAnchor,constant:18),memoryLabel.topAnchor.constraint(equalTo:controls.bottomAnchor,constant:8),memoryLabel.leadingAnchor.constraint(equalTo:controls.leadingAnchor),web.topAnchor.constraint(equalTo:bar.bottomAnchor),web.leadingAnchor.constraint(equalTo:container.leadingAnchor),web.trailingAnchor.constraint(equalTo:container.trailingAnchor),web.bottomAnchor.constraint(equalTo:container.bottomAnchor)])
  window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
  if args.contains("--setup") || (UserDefaults.standard.string(forKey:"AtlasStateDirectory")==nil && !args.contains("--state-dir")) {setupPending=true;showInitialSetup(automatic:true)}
  else {perform(UserDefaults.standard.object(forKey:"AtlasAutoStart") as? Bool == false ? "native-status":"start",navigate:true)}
  timer=Timer.scheduledTimer(withTimeInterval:4,repeats:true){[weak self] _ in if self?.setupPending != true {self?.perform("native-status",navigate:false)}}
 }
 var setupPathField:NSTextField?;var setupLocation:NSPopUpButton?;var setupLocations:[String]=[]
 func detectedDataLocations()->[String] {
  var locations=[String]()
  if !statePath.isEmpty && (statePath.hasPrefix("/Volumes/") || UserDefaults.standard.string(forKey:"AtlasStateDirectory") != nil) {locations.append(statePath)}
  let keys:Set<URLResourceKey>=[.volumeIsInternalKey,.volumeIsReadOnlyKey,.volumeAvailableCapacityKey]
  if let volumes=try? FileManager.default.contentsOfDirectory(at:URL(fileURLWithPath:"/Volumes"),includingPropertiesForKeys:Array(keys),options:[.skipsHiddenFiles]) {
   for volume in volumes.sorted(by:{$0.path<$1.path}) {
    guard let values=try? volume.resourceValues(forKeys:keys),values.volumeIsInternal != true,values.volumeIsReadOnly != true else {continue}
    let path=volume.appendingPathComponent("Atlas RAG/datos").path
    if !locations.contains(path){locations.append(path)}
   }
  }
  let local=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Atlas RAG").path
  if !locations.contains(local){locations.append(local)}
  return locations
 }
 @objc func chooseSetupFolder(){
  let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=true
  panel.message=tr("Elige una carpeta base. Atlas guardará sus datos en Atlas RAG/datos.","Choose a base folder. Atlas will store data in Atlas RAG/datos.")
  if panel.runModal() == .OK,let url=panel.url {setupPathField?.stringValue=url.appendingPathComponent("Atlas RAG/datos").path}
 }
 @objc func setupLocationChanged(){if let index=setupLocation?.indexOfSelectedItem,index>=0,index<setupLocations.count {setupPathField?.stringValue=setupLocations[index]}}
 @objc func openInitialSetup(){showInitialSetup(automatic:false)}
 func showInitialSetup(automatic:Bool){
  if loading{return}
  let alert=NSAlert();alert.messageText=tr("Configuración inicial de Atlas","Atlas initial setup")
  alert.informativeText=tr("Elige dónde guardar la base de datos, índices y análisis. Se priorizan las unidades externas. Los espacios existentes se conservan. Los motores se detectan sin cargar modelos.","Choose where to store the database, indexes and analyses. External drives are preferred. Existing workspaces are preserved. Engines are detected without loading models.")
  alert.addButton(withTitle:tr("Guardar y arrancar","Save and start"));alert.addButton(withTitle:tr("Cancelar","Cancel"))
  let view=NSView(frame:NSRect(x:0,y:0,width:560,height:270))
  setupLocations=detectedDataLocations()
  let locations=NSPopUpButton(frame:NSRect(x:0,y:226,width:560,height:30));setupLocation=locations
  for path in setupLocations {
   let url=URL(fileURLWithPath:path);var ancestor=url
   while !FileManager.default.fileExists(atPath:ancestor.path) && ancestor.path != "/" {ancestor.deleteLastPathComponent()}
   let values=try? ancestor.resourceValues(forKeys:[.volumeAvailableCapacityKey]);let free=Double(values?.volumeAvailableCapacity ?? 0)/1073741824
   locations.addItem(withTitle:String(format:"%@ · %.1f GB",path,free))
  }
  locations.target=self;locations.action=#selector(setupLocationChanged);view.addSubview(locations)
  let field=NSTextField(wrappingLabelWithString:setupLocations.first ?? statePath);field.frame=NSRect(x:0,y:167,width:560,height:48);field.font=NSFont.monospacedSystemFont(ofSize:11,weight:.regular);setupPathField=field;view.addSubview(field)
  let browse=NSButton(title:tr("Elegir otra carpeta…","Choose another folder…"),target:self,action:#selector(chooseSetupFolder));browse.frame=NSRect(x:0,y:126,width:220,height:30);view.addSubview(browse)
  let available=[("llama.cpp",["/opt/homebrew/bin/llama-server","/Volumes/Seguridad/Llama/optimizacion-m4-pro/bin/llama-server","/Volumes/Seguridad/Llama/llama.cpp/build/bin/llama-server"]),("oMLX",["/opt/homebrew/bin/omlx","/Applications/oMLX.app/Contents/MacOS/omlx-cli"]),("vLLM",["/opt/homebrew/bin/vllm"]),("LM Studio",["/Applications/LM Studio.app"]),("R",["/opt/homebrew/bin/Rscript","/usr/local/bin/Rscript","/Library/Frameworks/R.framework/Resources/bin/Rscript"])]
  let text=available.map{name,paths in name+": "+(paths.contains{FileManager.default.fileExists(atPath:$0)} ? tr("detectado","detected"):tr("no instalado","not installed"))}.joined(separator:"\n")
  let detected=NSTextField(wrappingLabelWithString:text);detected.frame=NSRect(x:0,y:12,width:560,height:105);detected.font=NSFont.systemFont(ofSize:12);view.addSubview(detected)
  alert.accessoryView=view
  alert.beginSheetModal(for:window){r in
   guard r == .alertFirstButtonReturn,let path=self.setupPathField?.stringValue else {if automatic {self.statusLabel.stringValue=self.tr("Configuración pendiente. Abre Servidor → Configuración inicial.","Setup pending. Open Server → Initial setup.")};return}
   self.loading=true
   DispatchQueue.global(qos:.userInitiated).async {
    if self.currentRunning {_ = self.command("stop")}
    do {try FileManager.default.createDirectory(atPath:path,withIntermediateDirectories:true)}catch {DispatchQueue.main.async{self.loading=false;let errorAlert=NSAlert(error:error);errorAlert.beginSheetModal(for:self.window)};return}
    DispatchQueue.main.async {
     self.statePath=path
     var vaults=UserDefaults.standard.dictionary(forKey:"AtlasCredentialDirectories") as? [String:String] ?? [:]
     self.secretPath=vaults[path] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Atlas RAG Credentials/workspace-"+UUID().uuidString).path
     vaults[path]=self.secretPath;UserDefaults.standard.set(vaults,forKey:"AtlasCredentialDirectories")
     UserDefaults.standard.set(path,forKey:"AtlasStateDirectory");UserDefaults.standard.set(self.secretPath,forKey:"AtlasSecretDirectory");UserDefaults.standard.set(true,forKey:"AtlasInitialSetupCompleted")
     self.setupPending=false;self.loading=false;self.perform("start",navigate:true)
    }
   }
  }
 }

 func buildMenu(){
  let menu=NSMenu();let appItem=NSMenuItem();menu.addItem(appItem);let appMenu=NSMenu();appItem.submenu=appMenu
  appMenu.addItem(withTitle:"Quit Atlas RAG",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q")
  let serviceItem=NSMenuItem();menu.addItem(serviceItem);let service=NSMenu(title:"Servidor / Server");serviceItem.submenu=service
  service.addItem(withTitle:"Arrancar / Start",action:#selector(startServer),keyEquivalent:"s")
  service.addItem(withTitle:"Parar / Stop",action:#selector(stopServer),keyEquivalent:".")
  service.addItem(withTitle:"Reiniciar / Restart",action:#selector(restartServer),keyEquivalent:"r")
  service.addItem(withTitle:"iPhone / iPad · Red local…",action:#selector(showNetwork),keyEquivalent:"n")
  service.addItem(NSMenuItem.separator())
  service.addItem(withTitle:"Configuración inicial / Initial setup…",action:#selector(openInitialSetup),keyEquivalent:"")
  service.addItem(withTitle:"Carpeta de datos / Data folder…",action:#selector(chooseDataDirectory),keyEquivalent:"")
  let auto=service.addItem(withTitle:"Arrancar al abrir / Start on launch",action:#selector(toggleAutoStart),keyEquivalent:"");auto.state=UserDefaults.standard.object(forKey:"AtlasAutoStart") as? Bool == false ? .off:.on
  let editItem=NSMenuItem();menu.addItem(editItem);let edit=NSMenu(title:"Edit");editItem.submenu=edit
  edit.addItem(withTitle:"Copy",action:#selector(NSText.copy(_:)),keyEquivalent:"c");edit.addItem(withTitle:"Paste",action:#selector(NSText.paste(_:)),keyEquivalent:"v");edit.addItem(withTitle:"Cut",action:#selector(NSText.cut(_:)),keyEquivalent:"x");edit.addItem(withTitle:"Select All",action:#selector(NSText.selectAll(_:)),keyEquivalent:"a");NSApp.mainMenu=menu
 }
 func command(_ action:String)->[String:Any] {
  if setupPending {return ["error":tr("Completa la configuración inicial.","Complete initial setup first.")]}
  if statePath.hasPrefix("/Volumes/") {let parts=URL(fileURLWithPath:statePath).pathComponents;if parts.count>2 && !FileManager.default.fileExists(atPath:"/Volumes/"+parts[2]) {return ["error":tr("Conecta la unidad de datos: ","Connect the data drive: ")+parts[2]]}}

  let p=Process();p.executableURL=URL(fileURLWithPath:project+"/python/bin/python3.14");p.arguments=["-B",project+"/scripts/control.py",action];p.currentDirectoryURL=URL(fileURLWithPath:project)
  p.environment=ProcessInfo.processInfo.environment.filter { !$0.key.hasPrefix("PYTHON") && $0.key != "__PYVENV_LAUNCHER__" }.merging(["RAG_STATE_DIR":statePath,"RAG_SECRET_DIR":secretPath,"PYTHONDONTWRITEBYTECODE":"1","PATH":"/opt/homebrew/bin:/usr/bin:/bin"]){_,new in new}
  let out=Pipe();let err=Pipe();p.standardOutput=out;p.standardError=err
  do{try p.run();DispatchQueue.global().asyncAfter(deadline:.now()+20){if p.isRunning {p.terminate()}};let data=out.fileHandleForReading.readDataToEndOfFile();p.waitUntilExit();return (try? JSONSerialization.jsonObject(with:data)) as? [String:Any] ?? ["error":"Invalid controller response"]}catch{return ["error":error.localizedDescription]}
 }
 func perform(_ action:String,navigate:Bool){
  if loading{return};loading=true
  if action != "native-status" {statusLabel.stringValue=tr("Procesando…","Working…");startButton.isEnabled=false;stopButton.isEnabled=false;restartButton.isEnabled=false}
  DispatchQueue.global(qos:.userInitiated).async{let info=self.command(action);DispatchQueue.main.async{self.loading=false;self.apply(info,navigate:navigate)}}
 }
 func apply(_ info:[String:Any],navigate:Bool){
  if let error=info["error"] as? String {statusLabel.stringValue=error;startButton.isEnabled=true;return}
  networkInfo=info["network"] as? [String:Any] ?? [:]
  currentRunning=info["running"] as? Bool ?? false;serviceURL=info["url"] as? String ?? ""
  statusLabel.stringValue=currentRunning ? tr("● Servidor activo","● Server running"):tr("○ Servidor parado","○ Server stopped")
  statusLabel.textColor=currentRunning ? NSColor.systemGreen:NSColor.secondaryLabelColor
  startButton.isEnabled = !currentRunning;stopButton.isEnabled=currentRunning;restartButton.isEnabled=currentRunning
  let rss=info["rss"] as? Double ?? 0;let free=info["disk_free"] as? Double ?? 0;let available=info["memory_available"] as? Double ?? 0;let swap=info["swap"] as? Double ?? 0
  memoryLabel.stringValue=String(format:tr("RAG: %.1f MB RAM  ·  Disco libre: %.1f GB  ·  RAM sistema disponible: %.1f GB  ·  Swap sistema: %.1f GB","RAG: %.1f MB RAM  ·  Free disk: %.1f GB  ·  System available RAM: %.1f GB  ·  System swap: %.1f GB"),rss/1048576,free/1073741824,available/1073741824,swap/1073741824)+"\n"+tr("Datos: ","Data: ")+statePath
  if navigate {
   if currentRunning {var url=serviceURL;if let setup=info["setup_token"] as? String {url+="#setup="+setup};if let u=URL(string:url){web.load(URLRequest(url:u))}}
   else {web.loadHTMLString("<html><body style='font-family:-apple-system;background:#f0f4ef;color:#203b39;display:grid;place-items:center;height:95vh'><div><h1>Atlas RAG</h1><p>"+tr("Servidor parado. Pulsa Arrancar para continuar.","Server stopped. Click Start to continue.")+"</p></div></body></html>",baseURL:nil)}
  }
 }
 @objc func showNetwork(){
  let alert=NSAlert();alert.messageText="iPhone / iPad · Atlas RAG"
  if networkInfo["enabled"] as? Bool == true,let url=networkInfo["url"] as? String,let pairing=networkInfo["pairing"] as? String {
   alert.informativeText=tr("Conecta el iPhone/iPad a la misma red y abre Atlas RAG. Escanea el QR o copia el enlace de conexión. Después inicia sesión con tu usuario de Atlas.\n\n","Connect your iPhone/iPad to the same network and open Atlas RAG. Scan the QR or copy the pairing link, then sign in with your Atlas user.\n\n")+url+"\nSHA-256: "+(networkInfo["fingerprint"] as? String ?? "")
   let filter=CIFilter.qrCodeGenerator();filter.message=Data(pairing.utf8)
   if let output=filter.outputImage {let view=NSImageView(frame:NSRect(x:0,y:0,width:240,height:240));let rep=NSCIImageRep(ciImage:output.transformed(by:CGAffineTransform(scaleX:8,y:8)));let image=NSImage(size:rep.size);image.addRepresentation(rep);view.image=image;alert.accessoryView=view}
   alert.addButton(withTitle:tr("Copiar conexión","Copy pairing link"));alert.addButton(withTitle:tr("Desactivar red local","Disable LAN access"));alert.addButton(withTitle:tr("Cerrar","Close"))
   alert.beginSheetModal(for:window){r in if r == .alertFirstButtonReturn {NSPasteboard.general.clearContents();NSPasteboard.general.setString(pairing,forType:.string)}else if r == .alertSecondButtonReturn {self.perform("network-disable",navigate:true)}}
  }else{
   alert.informativeText=tr("Activa HTTPS en la dirección privada del Mac para acceder desde la app de iPhone/iPad. Se conservan los usuarios y permisos. Solo se reinicia el servidor de Atlas; los motores de IA siguen abiertos.","Enable HTTPS on the Mac's private LAN address for the iPhone/iPad app. Existing users and permissions apply. Only Atlas restarts; AI engines remain running.")
   alert.addButton(withTitle:tr("Activar acceso local","Enable LAN access"));alert.addButton(withTitle:tr("Cancelar","Cancel"))
   alert.beginSheetModal(for:window){r in if r == .alertFirstButtonReturn {self.perform("network-enable",navigate:true)}}
  }
 }
 @objc func toggleAutoStart(_ sender:NSMenuItem){let enabled=sender.state != .on;UserDefaults.standard.set(enabled,forKey:"AtlasAutoStart");sender.state=enabled ? .on:.off}
 @objc func chooseDataDirectory(){
  if loading{return}
  let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=true;panel.message=tr("Elige dónde guardar los datos de Atlas. Los datos actuales se conservan en su carpeta.","Choose a folder for Atlas data. Existing data remains in its current folder.")
  panel.beginSheetModal(for:window){r in guard r == .OK,let url=panel.url else{return};self.loading=true;DispatchQueue.global(qos:.userInitiated).async{_ = self.command("stop");DispatchQueue.main.async{self.statePath=url.appendingPathComponent("Atlas RAG Data").path;var vaults=UserDefaults.standard.dictionary(forKey:"AtlasCredentialDirectories") as? [String:String] ?? [:];self.secretPath=vaults[self.statePath] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Atlas RAG Credentials/workspace-"+UUID().uuidString).path;vaults[self.statePath]=self.secretPath;UserDefaults.standard.set(vaults,forKey:"AtlasCredentialDirectories");UserDefaults.standard.set(self.secretPath,forKey:"AtlasSecretDirectory");UserDefaults.standard.set(self.statePath,forKey:"AtlasStateDirectory");self.setupPending=false;self.loading=false;self.perform("start",navigate:true)}}}
 }
 @objc func startServer(){perform("start",navigate:true)}
 @objc func stopServer(){perform("stop",navigate:true)}
 @objc func restartServer(){perform("restart",navigate:true)}
 @objc func openLogs(){NSWorkspace.shared.open(URL(fileURLWithPath:statePath+"/server.log"))}
 @objc func openBrowser(){if let u=URL(string:serviceURL),currentRunning{NSWorkspace.shared.open(u)}}
 @objc func toggleLanguage(){UserDefaults.standard.set(english ? "es":"en",forKey:"AtlasLanguage");startButton.title=tr("Arrancar","Start");stopButton.title=tr("Parar","Stop");restartButton.title=tr("Reiniciar","Restart");logsButton.title=tr("Registros","Logs");browserButton.title=tr("Abrir navegador","Open browser");let language=english ? "en":"es";web.evaluateJavaScript("document.querySelector('#language').value='\(language)';document.querySelector('#language').dispatchEvent(new Event('change'))",completionHandler:nil);perform("native-status",navigate:false)}
 func userContentController(_ userContentController:WKUserContentController,didReceive message:WKScriptMessage){
  guard message.frameInfo.securityOrigin.host=="127.0.0.1" else{return}
  if message.name=="chooseFolder" {let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false;panel.beginSheetModal(for:window){r in if r == .OK,let path=panel.url?.path,let data=try? JSONSerialization.data(withJSONObject:[path]),let arg=String(data:data,encoding:.utf8){self.web.evaluateJavaScript("window.atlasFolderChosen(\(arg)[0])",completionHandler:nil)}}}
  if message.name=="openExternal",let obj=message.body as? [String:Any],let s=obj["url"] as? String,let url=URL(string:s),url.scheme=="https",url.host=="auth.openai.com" {NSWorkspace.shared.open(url)}
 }
 func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error){statusLabel.stringValue=tr("Error al abrir interfaz: ","Interface error: ")+error.localizedDescription;web.loadHTMLString("<h2>Atlas RAG</h2><p>"+error.localizedDescription+"</p>",baseURL:nil)}
 func webView(_ webView:WKWebView,didFail navigation:WKNavigation!,withError error:Error){statusLabel.stringValue=error.localizedDescription}
 func webViewWebContentProcessDidTerminate(_ webView:WKWebView){statusLabel.stringValue=tr("La vista web se ha detenido. Reinicia Atlas.","Web view stopped. Restart Atlas.")}
 func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void){
  guard let url=navigationAction.request.url else{decisionHandler(.cancel);return}
  if url.scheme=="about" {decisionHandler(.allow);return}
  if url.host=="127.0.0.1",url.port==URL(string:serviceURL)?.port {
   if navigationAction.shouldPerformDownload {decisionHandler(.download)}else{decisionHandler(.allow)};return
  }
  if url.scheme=="https",url.host=="auth.openai.com" {NSWorkspace.shared.open(url)}
  decisionHandler(.cancel)
 }
 func webView(_ webView:WKWebView,decidePolicyFor navigationResponse:WKNavigationResponse,decisionHandler:@escaping(WKNavigationResponsePolicy)->Void){decisionHandler(navigationResponse.canShowMIMEType ? .allow:.download)}
 func webView(_ webView:WKWebView,navigationAction:WKNavigationAction,didBecome download:WKDownload){download.delegate=self}
 func webView(_ webView:WKWebView,navigationResponse:WKNavigationResponse,didBecome download:WKDownload){download.delegate=self}
 func download(_ download:WKDownload,decideDestinationUsing response:URLResponse,suggestedFilename:String,completionHandler:@escaping(URL?)->Void){let save=NSSavePanel();save.nameFieldStringValue=suggestedFilename;save.beginSheetModal(for:window){r in completionHandler(r == .OK ? save.url:nil)}}
 func webView(_ webView:WKWebView,createWebViewWith configuration:WKWebViewConfiguration,for navigationAction:WKNavigationAction,windowFeatures:WKWindowFeatures)->WKWebView?{if let u=navigationAction.request.url {web.load(URLRequest(url:u))};return nil}
 func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping(Bool)->Void){let alert=NSAlert();alert.messageText=message;alert.addButton(withTitle:tr("Continuar","Continue"));alert.addButton(withTitle:tr("Cancelar","Cancel"));alert.beginSheetModal(for:window){r in completionHandler(r == .alertFirstButtonReturn)}}
 func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool{return true}
 func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
  timer?.invalidate()
  DispatchQueue.global(qos:.userInitiated).async{_ = self.command("stop");DispatchQueue.main.async{NSApp.reply(toApplicationShouldTerminate:true)}}
  return .terminateLater
 }
}
let app=NSApplication.shared
let delegate=AppDelegate();app.delegate=delegate;app.setActivationPolicy(.regular);app.run()
