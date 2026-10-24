import AppKit
let dir=CommandLine.arguments[1]
for size in [16,32,64,128,256,512,1024] {
 let image=NSImage(size:NSSize(width:size,height:size));image.lockFocus()
 NSColor(calibratedRed:0.085,green:0.43,blue:0.38,alpha:1).setFill()
 if CommandLine.arguments.contains("--opaque") {NSBezierPath(rect:NSRect(x:0,y:0,width:size,height:size)).fill()}
 NSBezierPath(roundedRect:NSRect(x:0,y:0,width:size,height:size),xRadius:CGFloat(size)*0.23,yRadius:CGFloat(size)*0.23).fill()
 let paragraph=NSMutableParagraphStyle();paragraph.alignment = .center
 let attrs:[NSAttributedString.Key:Any]=[.font:NSFont(name:"Georgia-Italic",size:CGFloat(size)*0.88) ?? NSFont.systemFont(ofSize:CGFloat(size)*0.88),.foregroundColor:NSColor.white,.paragraphStyle:paragraph]
 ("a" as NSString).draw(in:NSRect(x:0,y:CGFloat(size)*0.02,width:CGFloat(size),height:CGFloat(size)),withAttributes:attrs)
 image.unlockFocus()
 let rep=NSBitmapImageRep(data:image.tiffRepresentation!)!;let data=rep.representation(using:.png,properties:[:])!
 try! data.write(to:URL(fileURLWithPath:dir+"/icon_\(size)x\(size).png"))
}
