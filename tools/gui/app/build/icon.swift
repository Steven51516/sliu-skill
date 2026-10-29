// Draws the Research Desk icon (1024 px PNG): a squircle in the app's accent colours with a small white DAG.
import AppKit
let size = 1024.0, inset = 100.0
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size), pixelsHigh: Int(size), bitsPerSample: 8, samplesPerPixel: 4,
                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let body = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
let shape = NSBezierPath(roundedRect: body, xRadius: 185, yRadius: 185)
NSShadow().with { $0.shadowColor = NSColor.black.withAlphaComponent(0.28); $0.shadowBlurRadius = 28; $0.shadowOffset = NSSize(width: 0, height: -12); $0.set() }
NSColor.black.setFill(); shape.fill()
NSShadow().set()
NSGradient(colors: [NSColor(srgbRed: 0.27, green: 0.38, blue: 0.93, alpha: 1), NSColor(srgbRed: 0.53, green: 0.33, blue: 0.93, alpha: 1)])!
  .draw(in: shape, angle: -55)
NSGradient(colors: [NSColor.white.withAlphaComponent(0.18), NSColor.white.withAlphaComponent(0)])!
  .draw(in: NSBezierPath(roundedRect: NSRect(x: inset, y: size / 2, width: size - 2 * inset, height: size / 2 - inset), xRadius: 185, yRadius: 185), angle: -90)
// the DAG: two sources feed a middle node, which feeds the destination ring
let a = NSPoint(x: 300, y: 650), b = NSPoint(x: 300, y: 380), c = NSPoint(x: 520, y: 515), d = NSPoint(x: 730, y: 515)
NSColor.white.withAlphaComponent(0.85).setStroke()
for (p, q) in [(a, c), (b, c), (c, d)] {
  let l = NSBezierPath(); l.lineWidth = 30; l.lineCapStyle = .round
  l.move(to: p); l.curve(to: q, controlPoint1: NSPoint(x: (p.x + q.x) / 2, y: p.y), controlPoint2: NSPoint(x: (p.x + q.x) / 2, y: q.y)); l.stroke()
}
NSColor.white.setFill()
for p in [a, b, c] { NSBezierPath(ovalIn: NSRect(x: p.x - 58, y: p.y - 58, width: 116, height: 116)).fill() }
let ring = NSBezierPath(ovalIn: NSRect(x: d.x - 78, y: d.y - 78, width: 156, height: 156)); ring.lineWidth = 34; NSColor.white.setStroke(); ring.stroke()
NSBezierPath(ovalIn: NSRect(x: d.x - 26, y: d.y - 26, width: 52, height: 52)).fill()
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
extension NSShadow { func with(_ f: (NSShadow) -> Void) -> NSShadow { f(self); return self } }
