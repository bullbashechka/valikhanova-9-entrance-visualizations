import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

// Coordinates refer to a 1800 × 1273 rendering of each source page.
// The source PDF is drawn through these clipping paths, so its linework
// remains sharp and apartment interiors never enter the exported images.
struct Plan {
    let section: Int
    let page: Int
    let crop: CGRect
    let regions: [[CGPoint]]
}

func polygon(_ values: [(Double, Double)]) -> [CGPoint] {
    values.map { CGPoint(x: $0.0, y: $0.1) }
}

let plans = [
    Plan(
        section: 1, page: 2, crop: CGRect(x: 866, y: 329, width: 425, height: 373),
        regions: [
            polygon([(902, 352), (1263, 352), (1263, 482), (902, 482)]),
            polygon([(902, 478), (1122, 478), (1122, 629), (902, 629)]),
            polygon([(902, 626), (952, 626), (952, 674), (902, 674)]),
            polygon([(1031, 626), (1122, 626), (1122, 674), (1031, 674)])
        ]
    ),
    Plan(
        section: 2, page: 13, crop: CGRect(x: 540, y: 218, width: 656, height: 431),
        regions: [
            polygon([(565, 370), (679, 370), (679, 502), (565, 502)]),
            polygon([(858, 239), (979, 239), (979, 375), (1147, 375),
                     (1147, 617), (858, 617)])
        ]
    ),
    Plan(
        section: 3, page: 22, crop: CGRect(x: 645, y: 167, width: 493, height: 492),
        regions: [
            polygon([(673, 190), (840, 190), (840, 394), (683, 394),
                     (683, 312), (673, 312)]),
            polygon([(683, 390), (813, 390), (813, 538), (720, 538),
                     (720, 515), (683, 515)]),
            polygon([(808, 387), (1069, 387), (1069, 475), (808, 475)]),
            polygon([(809, 472), (1009, 472), (1009, 634), (809, 634)]),
            polygon([(1008, 611), (1110, 611), (1110, 634), (1008, 634)])
        ]
    )
]

let source = URL(fileURLWithPath: "Планировки ЖК v1.pdf")
guard let pdf = CGPDFDocument(source as CFURL) else {
    fatalError("Cannot open source PDF")
}
let outputDirectory = URL(fileURLWithPath: "plans", isDirectory: true)
let referenceSize = CGSize(width: 1800, height: 1273)
let outputScale = 6

for plan in plans {
    guard let page = pdf.page(at: plan.page) else {
        fatalError("Missing PDF page \(plan.page)")
    }
    let width = Int(plan.crop.width) * outputScale
    let height = Int(plan.crop.height) * outputScale
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    guard let context = CGContext(
        data: nil, width: width, height: height, bitsPerComponent: 8,
        bytesPerRow: 0, space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
    ) else {
        fatalError("Cannot create bitmap context")
    }

    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))

    // Work in the top-left coordinate system of the reference rendering.
    context.translateBy(x: 0, y: CGFloat(height))
    context.scaleBy(x: 1, y: -1)
    context.scaleBy(x: CGFloat(outputScale), y: CGFloat(outputScale))
    context.translateBy(x: -plan.crop.minX, y: -plan.crop.minY)

    context.beginPath()
    for region in plan.regions {
        guard let first = region.first else { continue }
        context.move(to: first)
        for point in region.dropFirst() { context.addLine(to: point) }
        context.closePath()
    }
    context.clip()

    let pageBox = page.getBoxRect(.mediaBox)
    context.translateBy(x: 0, y: referenceSize.height)
    context.scaleBy(
        x: referenceSize.width / pageBox.width,
        y: -referenceSize.height / pageBox.height
    )
    context.drawPDFPage(page)

    guard let image = context.makeImage() else { fatalError("Cannot render image") }
    let output = outputDirectory.appendingPathComponent("section-\(plan.section)-common-areas.png")
    guard let destination = CGImageDestinationCreateWithURL(
        output as CFURL, UTType.png.identifier as CFString, 1, nil
    ) else {
        fatalError("Cannot create PNG destination")
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else { fatalError("Cannot write PNG") }
    print("\(output.path): \(width) × \(height)")
}
