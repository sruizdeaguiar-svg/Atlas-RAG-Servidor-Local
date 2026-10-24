import Foundation
import NaturalLanguage
import PDFKit
import Vision
import AppKit
func output(_ value: Any) { let data = try! JSONSerialization.data(withJSONObject:value, options:[.fragmentsAllowed]); print(String(data:data, encoding:.utf8)!) }
do {
 if CommandLine.arguments.contains("--ocr") {
  guard let doc = PDFDocument(url:URL(fileURLWithPath:CommandLine.arguments.last!)) else { throw NSError(domain:"PDF",code:1) }
  var pages:[[String:Any]]=[]
  for i in 0..<min(doc.pageCount,500) {
   guard let page=doc.page(at:i) else {continue}
   if let s=page.string, s.trimmingCharacters(in:.whitespacesAndNewlines).count>20 { pages.append(["page":i+1,"text":s,"ocr":false]); continue }
   let image=page.thumbnail(of:NSSize(width:1800,height:2400), for:.mediaBox)
   var rect=NSRect(origin:.zero,size:image.size)
   guard let cg=image.cgImage(forProposedRect:&rect, context:nil,hints:nil) else {continue}
   let req=VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.recognitionLanguages=["es-ES","en-US"]; req.usesLanguageCorrection=true
   try VNImageRequestHandler(cgImage:cg).perform([req])
   pages.append(["page":i+1,"text":(req.results ?? []).compactMap{$0.topCandidates(1).first?.string}.joined(separator:"\n"),"ocr":true])
  }
  output(pages)
 } else {
  let input=FileHandle.standardInput.readDataToEndOfFile()
  let obj=try JSONSerialization.jsonObject(with:input) as! [String:Any]
  let language=NLLanguage(rawValue:obj["language"] as? String ?? "es")
  guard let embedding=NLEmbedding.sentenceEmbedding(for:language) else { throw NSError(domain:"Embedding unavailable",code:2) }
  let vectors=(obj["texts"] as! [String]).map{embedding.vector(for:$0) ?? Array(repeating:0.0,count:embedding.dimension)}
  output(["model":"apple-sentence-\(language.rawValue)-rev\(embedding.revision)-\(embedding.dimension)","vectors":vectors])
 }
} catch { fputs("Document tools failed: \(error)\n",stderr); exit(1) }
