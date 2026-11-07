// Local Apple Vision OCR worker. One JSON request and response per line.
import Foundation
import Vision
import ImageIO

func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value),
       let text = String(data: data, encoding: .utf8) {
        print(text)
        fflush(stdout)
    }
}
emit(["ready": true])
while let line = readLine() {
    autoreleasepool {
        do {
            guard let data = line.data(using: .utf8),
                  let paths = try JSONSerialization.jsonObject(with: data) as? [String],
                  paths.count <= 16 else {
                throw NSError(domain: "StintrixOCR", code: 1)
            }
            var texts: [String] = []
            for path in paths {
                let request = VNRecognizeTextRequest()
                request.recognitionLevel = .accurate
                request.recognitionLanguages = ["en-US"]
                request.usesLanguageCorrection = false
                let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path))
                try handler.perform([request])
                texts.append((request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: " "))
            }
            emit(["texts": texts])
        } catch { emit(["error": error.localizedDescription]) }
    }
}
