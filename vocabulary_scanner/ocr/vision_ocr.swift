// Apple Vision OCR 輔助程式（僅 macOS）
// 用法：vision_ocr <圖片1> <圖片2> ...
// 對每個圖片用 Vision 框架認字，逐張輸出文字。

import Foundation
import Vision
import AppKit

func recognizeText(in path: String) -> String {
    guard let image = NSImage(contentsOfFile: path),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("cannot load image: \(path)\n".data(using: .utf8)!)
        return ""
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["en-US", "zh-Hant", "zh-Hans"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        FileHandle.standardError.write("ocr failed: \(error)\n".data(using: .utf8)!)
        return ""
    }

    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return ""
    }
    return observations
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
}

for path in CommandLine.arguments.dropFirst() {
    print(recognizeText(in: path))
}
