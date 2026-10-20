export type Dimensions = { width: number; height: number };

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

// Pixel size read from an image header, without decoding any pixels. Null when the bytes are not
// a JPEG, PNG or WebP, or the header is cut off before the size.
export function readImageSize(bytes: Uint8Array): Dimensions | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const size = png(bytes, view) ?? jpeg(bytes, view) ?? webp(bytes, view);
  return size && size.width > 0 && size.height > 0 ? size : null;
}

function png(bytes: Uint8Array, view: DataView): Dimensions | null {
  if (bytes.length < 24 || !PNG_SIGNATURE.every((byte, i) => bytes[i] === byte)) return null;
  if (ascii(bytes, 12, 4) !== "IHDR") return null;
  return { width: view.getUint32(16), height: view.getUint32(20) };
}

function jpeg(bytes: Uint8Array, view: DataView): Dimensions | null {
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  let offset = 2;
  while (offset + 4 <= bytes.length) {
    if (bytes[offset] !== 0xff) return null;
    const marker = bytes[offset + 1]!;
    if (marker === 0xff) {
      offset += 1; // fill byte
      continue;
    }
    // Markers with no length: TEM, RSTn, SOI, EOI. Anything past them is not a header we walk.
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd9)) {
      offset += 2;
      continue;
    }
    const length = view.getUint16(offset + 2);
    // SOF0–SOF15, except DHT (C4), JPG (C8) and DAC (CC), which share the range.
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      if (offset + 9 > bytes.length) return null;
      return { height: view.getUint16(offset + 5), width: view.getUint16(offset + 7) };
    }
    offset += 2 + length;
  }
  return null;
}

function webp(bytes: Uint8Array, view: DataView): Dimensions | null {
  if (bytes.length < 30 || ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WEBP") return null;
  switch (ascii(bytes, 12, 4)) {
    case "VP8 ":
      // Lossy: a 3-byte frame tag, the start code 9D 01 2A, then 14-bit sizes.
      if (bytes[23] !== 0x9d || bytes[24] !== 0x01 || bytes[25] !== 0x2a) return null;
      return { width: view.getUint16(26, true) & 0x3fff, height: view.getUint16(28, true) & 0x3fff };
    case "VP8L": {
      // Lossless: signature 2F, then two 14-bit sizes minus one, packed little-endian.
      if (bytes[20] !== 0x2f) return null;
      const packed = view.getUint32(21, true);
      return { width: (packed & 0x3fff) + 1, height: ((packed >> 14) & 0x3fff) + 1 };
    }
    case "VP8X":
      // Extended: 24-bit sizes minus one.
      return {
        width: (bytes[24]! | (bytes[25]! << 8) | (bytes[26]! << 16)) + 1,
        height: (bytes[27]! | (bytes[28]! << 8) | (bytes[29]! << 16)) + 1,
      };
    default:
      return null;
  }
}

function ascii(bytes: Uint8Array, start: number, length: number) {
  return String.fromCharCode(...bytes.subarray(start, start + length));
}
