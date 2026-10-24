import SwiftUI
import WebKit
import CryptoKit
import Security

func localURL(_ value:String)->URL? {
 guard let u=URL(string:value.trimmingCharacters(in:.whitespacesAndNewlines)),u.scheme=="https",u.user==nil,u.password==nil,u.query==nil,u.fragment==nil,(u.path.isEmpty || u.path=="/"),let host=u.host else{return nil}
 let n=host.split(separator:".").compactMap{Int($0)}
 guard n.count==4,n.allSatisfy({0...255 ~= $0}),(n[0]==10 || (n[0]==172 && 16...31 ~= n[1]) || (n[0]==192 && n[1]==168)) else{return nil}
 return u
}

@main struct AtlasRAGApp:App {
 var body:some Scene {WindowGroup{ConnectionView()}}
}
struct ConnectionView:View {
 @AppStorage("atlas.server") private var savedServer=""
 @AppStorage("atlas.pin") private var savedPin=""
 @State private var server=""
 @State private var pin=""
 @State private var connected=false
 @State private var error=""
 private enum ConnectionField:Hashable {case server,pin,connect}
 @FocusState private var focusedField:ConnectionField?
 var body:some View {
  NavigationStack {
   Group {
    if connected,let url=localURL(savedServer) {
     AtlasWeb(url:url,pin:savedPin,error:$error).ignoresSafeArea(.container,edges:.bottom)
    }else{
     ScrollView {
      VStack(alignment:.leading,spacing:22){
       Text("a").font(.custom("Georgia-Italic",size:78)).foregroundStyle(.white).frame(width:100,height:100).background(Color(red:0.08,green:0.43,blue:0.38),in:RoundedRectangle(cornerRadius:24))
       Text("Tu biblioteca, en tu red.").font(.largeTitle.bold())
       Text("En el Mac abre Atlas RAG → Servidor / Server → iPhone / iPad. Activa el acceso local y escanea su QR con la cámara del iPhone o pega el enlace de conexión aquí.").foregroundStyle(.secondary)
       TextField("https://192.168.1.20:8766 o enlace atlasrag://…",text:$server).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder).accessibilityIdentifier("serverURL").focused($focusedField,equals:.server).submitLabel(.next).onSubmit{focusedField = .pin}.onKeyPress(keys:[.tab],phases:.down){press in focusedField = press.modifiers.contains(.shift) ? .connect:.pin;return .handled}
       TextField("Huella SHA-256 del Mac",text:$pin).font(.system(.caption,design:.monospaced)).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder).accessibilityIdentifier("certificatePin").focused($focusedField,equals:.pin).submitLabel(.go).onSubmit(connect).onKeyPress(keys:[.tab],phases:.down){press in focusedField = press.modifiers.contains(.shift) ? .server:.connect;return .handled}
       Button("Conectar al Mac",action:connect).buttonStyle(.borderedProminent).tint(Color(red:0.08,green:0.43,blue:0.38)).accessibilityIdentifier("connect").focused($focusedField,equals:.connect).onKeyPress(keys:[.tab],phases:.down){press in focusedField = press.modifiers.contains(.shift) ? .pin:.server;return .handled}
       Text("Conecta ambos dispositivos a la misma red. La huella identifica el certificado de tu Mac. Inicia sesión con tu usuario de Atlas; los archivos y el análisis se procesan en el servidor del Mac.").font(.footnote).foregroundStyle(.secondary)
      }.padding(28).frame(maxWidth:640)
     }.frame(maxWidth:.infinity)
    }
   }
   .navigationTitle("Atlas RAG").navigationBarTitleDisplayMode(.inline)
   .toolbar {if connected {ToolbarItem(placement:.topBarTrailing){Button("Servidor"){connected=false;error=""}}}}
   .safeAreaInset(edge:.bottom){if !error.isEmpty {Text(error).font(.footnote).foregroundStyle(.red).padding().frame(maxWidth:.infinity).background(.regularMaterial)}}
   .onAppear{server=savedServer;pin=savedPin}
   .onOpenURL{u in guard u.scheme=="atlasrag",u.host=="connect",let c=URLComponents(url:u,resolvingAgainstBaseURL:false) else{return};server=c.queryItems?.first(where:{$0.name=="url"})?.value ?? "";pin=c.queryItems?.first(where:{$0.name=="pin"})?.value ?? "";connected=false;error=""}
  }
 }
 func connect(){
  if server.hasPrefix("atlasrag://"),let u=URLComponents(string:server) {pin=u.queryItems?.first(where:{$0.name=="pin"})?.value ?? "";server=u.queryItems?.first(where:{$0.name=="url"})?.value ?? ""}
  let cleanPin=pin.lowercased().replacingOccurrences(of:":",with:"").trimmingCharacters(in:.whitespacesAndNewlines)
  guard let url=localURL(server),cleanPin.count==64,cleanPin.allSatisfy({"0123456789abcdef".contains($0)}) else{error="Introduce una dirección HTTPS privada y la huella de 64 caracteres que muestra tu Mac.";return}
  let open = {savedServer=url.absoluteString;savedPin=cleanPin;error="";connected=true}
  if savedServer != url.absoluteString || savedPin != cleanPin {WKWebsiteDataStore.default().removeData(ofTypes:WKWebsiteDataStore.allWebsiteDataTypes(),modifiedSince:.distantPast,completionHandler:{DispatchQueue.main.async(execute:open)})}else{open()}
 }
}

// Route hardware Tab before WebKit turns it into text input on iPadOS.
final class AtlasKeyboardWebView:WKWebView {
 override var keyCommands:[UIKeyCommand]? {
  let next=UIKeyCommand(input:"\t",modifierFlags:[],action:#selector(nextControl))
  let previous=UIKeyCommand(input:"\t",modifierFlags:[.shift],action:#selector(previousControl))
  next.wantsPriorityOverSystemBehavior=true;previous.wantsPriorityOverSystemBehavior=true
  return [next,previous]+(super.keyCommands ?? [])
 }
 @objc private func nextControl(){evaluateJavaScript("window.atlasMoveFocus?.(false)",completionHandler:nil)}
 @objc private func previousControl(){evaluateJavaScript("window.atlasMoveFocus?.(true)",completionHandler:nil)}
}

struct AtlasWeb:UIViewRepresentable {
 let url:URL;let pin:String;@Binding var error:String
 func makeCoordinator()->Coordinator{Coordinator(self)}
 func makeUIView(context:Context)->WKWebView {
  let view=AtlasKeyboardWebView(frame:.zero);view.navigationDelegate=context.coordinator;view.uiDelegate=context.coordinator;view.allowsBackForwardNavigationGestures=true;view.load(URLRequest(url:url,cachePolicy:.reloadRevalidatingCacheData));return view
 }
 func updateUIView(_ uiView:WKWebView,context:Context){context.coordinator.parent=self}
 final class Coordinator:NSObject,WKNavigationDelegate,WKUIDelegate,WKDownloadDelegate {
  var parent:AtlasWeb
  init(_ p:AtlasWeb){parent=p}
  func trusted(_ url:URL)->Bool{url.scheme=="https" && url.host==parent.url.host && url.port==parent.url.port}
  func webView(_ webView:WKWebView,didReceive challenge:URLAuthenticationChallenge,completionHandler:@escaping(URLSession.AuthChallengeDisposition,URLCredential?)->Void){
   guard challenge.protectionSpace.authenticationMethod==NSURLAuthenticationMethodServerTrust,challenge.protectionSpace.host==parent.url.host,let trust=challenge.protectionSpace.serverTrust,let chain=SecTrustCopyCertificateChain(trust) as? [SecCertificate],let cert=chain.first else {completionHandler(.cancelAuthenticationChallenge,nil);return}
   let hash=SHA256.hash(data:SecCertificateCopyData(cert) as Data).map{String(format:"%02x",$0)}.joined()
   guard hash==parent.pin else {parent.error="La huella del servidor ha cambiado. Comprueba el QR en tu Mac antes de conectar.";completionHandler(.cancelAuthenticationChallenge,nil);return}
   SecTrustSetAnchorCertificates(trust,[cert] as CFArray);SecTrustSetAnchorCertificatesOnly(trust,true);SecTrustSetPolicies(trust,SecPolicyCreateSSL(true,parent.url.host! as CFString))
   guard SecTrustEvaluateWithError(trust,nil) else{parent.error="El certificado no es válido para este servidor o ha caducado.";completionHandler(.cancelAuthenticationChallenge,nil);return}
   completionHandler(.useCredential,URLCredential(trust:trust))
  }
  func webView(_ webView:WKWebView,decidePolicyFor action:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void){guard let u=action.request.url,trusted(u) else{decisionHandler(.cancel);return};decisionHandler(action.shouldPerformDownload ? .download:.allow)}
  func webView(_ webView:WKWebView,decidePolicyFor response:WKNavigationResponse,decisionHandler:@escaping(WKNavigationResponsePolicy)->Void){decisionHandler(response.canShowMIMEType ? .allow:.download)}
  func webView(_ webView:WKWebView,createWebViewWith configuration:WKWebViewConfiguration,for action:WKNavigationAction,windowFeatures:WKWindowFeatures)->WKWebView?{if let u=action.request.url,trusted(u){webView.load(URLRequest(url:u))};return nil}
  func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error){if parent.error.isEmpty{parent.error="No se pudo conectar. Comprueba la red local, el permiso de red en Ajustes y que Atlas esté abierto en el Mac. "+error.localizedDescription}}
  func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!){parent.error=""}
  func presenter()->UIViewController?{UIApplication.shared.connectedScenes.compactMap{$0 as? UIWindowScene}.flatMap{$0.windows}.first(where:{$0.isKeyWindow})?.rootViewController}
  func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping(Bool)->Void){guard let p=presenter() else{completionHandler(false);return};let a=UIAlertController(title:"Atlas RAG",message:message,preferredStyle:.alert);a.addAction(UIAlertAction(title:"Cancelar",style:.cancel){_ in completionHandler(false)});a.addAction(UIAlertAction(title:"Continuar",style:.default){_ in completionHandler(true)});p.present(a,animated:true)}
  func webView(_ webView:WKWebView,navigationAction:WKNavigationAction,didBecome download:WKDownload){download.delegate=self}
  func webView(_ webView:WKWebView,navigationResponse:WKNavigationResponse,didBecome download:WKDownload){download.delegate=self}
  var downloadURL:URL?
  func download(_ download:WKDownload,decideDestinationUsing response:URLResponse,suggestedFilename:String,completionHandler:@escaping(URL?)->Void){let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try? FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true);let file=folder.appendingPathComponent((suggestedFilename as NSString).lastPathComponent);downloadURL=file;completionHandler(file)}
  func downloadDidFinish(_ download:WKDownload){guard let file=downloadURL,let p=presenter() else{return};let share=UIActivityViewController(activityItems:[file],applicationActivities:nil);share.popoverPresentationController?.sourceView=p.view;share.popoverPresentationController?.sourceRect=CGRect(x:p.view.bounds.midX,y:p.view.bounds.midY,width:1,height:1);p.present(share,animated:true)}
 }
}
