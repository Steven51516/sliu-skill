// Draws the menu-bar template image (black on transparent; macOS tints it): the icon's DAG glyph.
import AppKit
func draw(_ px: Int, _ path: String) {
  let s = Double(px) / 22.0
  let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                             isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
  NSGraphicsContext.saveGraphicsState()
  NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
  NSColor.black.set()
  let a = NSPoint(x: 4 * s, y: 16 * s), b = NSPoint(x: 4 * s, y: 6 * s), c = NSPoint(x: 11 * s, y: 11 * s), d = NSPoint(x: 18 * s, y: 11 * s)
  for (p, q) in [(a, c), (b, c), (c, d)] {
    let l = NSBezierPath(); l.lineWidth = 1.6 * s; l.move(to: p)
    l.curve(to: q, controlPoint1: NSPoint(x: (p.x + q.x) / 2, y: p.y), controlPoint2: NSPoint(x: (p.x + q.x) / 2, y: q.y)); l.stroke()
  }
  for p in [a, b, c] { NSBezierPath(ovalIn: NSRect(x: p.x - 2.6 * s, y: p.y - 2.6 * s, width: 5.2 * s, height: 5.2 * s)).fill() }
  let ring = NSBezierPath(ovalIn: NSRect(x: d.x - 3.2 * s, y: d.y - 3.2 * s, width: 6.4 * s, height: 6.4 * s)); ring.lineWidth = 1.6 * s; ring.stroke()
  NSGraphicsContext.restoreGraphicsState()
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: path))
}
draw(22, CommandLine.arguments[1] + "/trayTemplate.png")
draw(44, CommandLine.arguments[1] + "/trayTemplate@2x.png")
