// 투명 배경에 글자만 그려 PNG 로 저장한다.
//
// 워터마크 글자를 만드는 데 쓴다. 설치된 ImageMagick 에 폰트(FreeType) 지원이
// 없어서 magick 으로는 글자를 그릴 수 없기 때문에, 폰트 렌더링만 AppKit 이 맡는다.
//
//   swift make-text.swift <출력.png> <문구> <글자크기>

import Cocoa

let a = CommandLine.arguments
let out = a.count > 1 ? a[1] : "text.png"
let str = a.count > 2 ? a[2] : "© Brothrone"
let pt  = CGFloat(a.count > 3 ? Double(a[3]) ?? 46 : 46)

let font = NSFont(name: "HelveticaNeue-Medium", size: pt)
        ?? NSFont.systemFont(ofSize: pt, weight: .medium)
let text = NSAttributedString(string: str, attributes: [
    .font: font,
    .foregroundColor: NSColor.white,
])

let sz = text.size()
let W = Int(ceil(sz.width)) + 20
let H = Int(ceil(sz.height)) + 20

guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
text.draw(at: NSPoint(x: 10, y: 10))
NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try! png.write(to: URL(fileURLWithPath: out))
print("\(W)x\(H)")
