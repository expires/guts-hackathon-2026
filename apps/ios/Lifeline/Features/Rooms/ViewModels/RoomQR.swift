import CoreImage.CIFilterBuiltins
import UIKit

/// QR image for the lobby. The backend sends `qr_png_base64`. When that PNG does not decode
/// (the contract example is a bare PNG header), the app draws the same join link locally.
enum RoomQR {
    static func png(base64: String, joinURL: String) -> Data? {
        if let data = Data(base64Encoded: base64), UIImage(data: data) != nil { return data }
        return generate(joinURL)
    }

    static func generate(_ text: String) -> Data? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 8, y: 8)) else { return nil }
        let context = CIContext()
        guard let image = context.createCGImage(output, from: output.extent) else { return nil }
        return UIImage(cgImage: image).pngData()
    }
}
