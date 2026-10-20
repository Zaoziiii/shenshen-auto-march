import Vision
import AppKit
// usage: ocr image.png  → 每行: x y w h text（像素坐标，左上原点）
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }
let W = Double(cg.width), H = Double(cg.height)
let req = VNRecognizeTextRequest { r, _ in
  for o in (r.results as? [VNRecognizedTextObservation]) ?? [] {
    guard let t = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    print(Int(b.minX*W), Int((1-b.maxY)*H), Int(b.width*W), Int(b.height*H), t.string)
  }
}
req.recognitionLanguages = ["ja-JP", "en-US"]
req.recognitionLevel = .accurate
try VNImageRequestHandler(cgImage: cg).perform([req])
