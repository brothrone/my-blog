// favicon.ico 의 세리프 "B" 를 앱 아이콘용으로 크고 선명하게 그린다.
//
// favicon 은 32x32 라 그대로 확대하면 뭉개진다. 그런데 설치된 ImageMagick 에는
// 폰트(FreeType) 지원이 없어 글자를 못 그린다. 그래서 글자 렌더링만 AppKit 이 맡고,
// 배경·가운데 정렬은 make-app.sh 가 ImageMagick 의 -trim 으로 처리한다.
// (폰트 메트릭으로 가운데를 맞추면 글자 위아래 여백 때문에 치우친다)
//
//   swift make-icon.swift <출력.png>   → 투명 배경에 검은 B

import Cocoa

let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "glyph.png"
let S = 1400

guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil, pixelsWide: S, pixelsHigh: S,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

let side = CGFloat(S)
let size = side * 0.6

// favicon 과 같은 볼드 세리프
let font = NSFont(name: "Times New Roman Bold", size: size)
    ?? NSFont(name: "TimesNewRomanPS-BoldMT", size: size)
    ?? NSFont(name: "Georgia-Bold", size: size)
    ?? NSFont.boldSystemFont(ofSize: size)

let para = NSMutableParagraphStyle()
para.alignment = .center

let text = NSAttributedString(string: "B", attributes: [
    .font: font,
    .foregroundColor: NSColor.black,
    .paragraphStyle: para,
])

let h = text.size().height
text.draw(in: NSRect(x: 0, y: (side - h) / 2, width: side, height: h))

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try! png.write(to: URL(fileURLWithPath: out))
print("glyph: \(out)")
