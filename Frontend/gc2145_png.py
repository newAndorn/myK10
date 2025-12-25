# gc2145_png.py
class GC2145PngEncoder:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def encode(self, raw_rgb565):
        if len(raw_rgb565) != self.width * self.height * 2:
            raise ValueError("raw buffer size does not match width*height*2")
        rgb = self._rgb565_to_rgb888(raw_rgb565)
        scanlines = self._add_png_filters(rgb)
        idat = self._zlib_uncompressed(scanlines)
        chunks = (
            self._chunk(b'IHDR', self._ihdr_payload()) +
            self._chunk(b'IDAT', idat) +
            self._chunk(b'IEND', b'')
        )
        return b'\x89PNG\r\n\x1a\n' + chunks

    # --- color conversion -------------------------------------------------
    def _rgb565_to_rgb888(self, raw):
        out = bytearray(self.width * self.height * 3)
        mv = memoryview(raw)
        o = 0
        for i in range(0, len(mv), 2):
            lo = mv[i]
            hi = mv[i + 1]
            value = (hi << 8) | lo  # little-endian RGB565
            r5 = (value >> 11) & 0x1F
            g6 = (value >> 5) & 0x3F
            b5 = value & 0x1F
            out[o] = (r5 * 527 + 23) >> 6
            out[o + 1] = (g6 * 259 + 33) >> 6
            out[o + 2] = (b5 * 527 + 23) >> 6
            o += 3
        return out

    def _add_png_filters(self, rgb):
        row_size = self.width * 3
        out = bytearray((row_size + 1) * self.height)
        src = 0
        dst = 0
        for _ in range(self.height):
            out[dst] = 0  # filter type 0
            dst += 1
            out[dst:dst + row_size] = rgb[src:src + row_size]
            dst += row_size
            src += row_size
        return out

    # --- PNG internals ----------------------------------------------------
    def _ihdr_payload(self):
        return (
            self.width.to_bytes(4, "big") +
            self.height.to_bytes(4, "big") +
            b"\x08\x02\x00\x00\x00"  # 8-bit RGB, deflate, no filter/interlace tweaks
        )

    def _chunk(self, ctype, data):
        crc = self._crc32(ctype + data)
        return (
            len(data).to_bytes(4, "big") +
            ctype +
            data +
            crc.to_bytes(4, "big")
        )

    def _zlib_uncompressed(self, data):
        out = bytearray(b"\x78\x01")  # zlib header (CMF/FLG for no preset dict)
        idx = 0
        remaining = len(data)
        while remaining:
            block = min(65535, remaining)
            remaining -= block
            final = 1 if remaining == 0 else 0
            out.append(final)  # BFINAL + BTYPE=00
            out += block.to_bytes(2, "little")
            out += (~block & 0xFFFF).to_bytes(2, "little")
            out += data[idx:idx + block]
            idx += block
        out += self._adler32(data).to_bytes(4, "big")
        return out

    # --- tiny checksum helpers -------------------------------------------
    def _crc32(self, data):
        crc = 0xFFFFFFFF
        for b in data:
            crc ^= b << 24
            for _ in range(8):
                mask = 0xFFFFFFFF if (crc & 0x80000000) else 0
                crc = ((crc << 1) ^ (0x04C11DB7 & mask)) & 0xFFFFFFFF
        return crc ^ 0xFFFFFFFF

    def _adler32(self, data):
        s1 = 1
        s2 = 0
        for b in data:
            s1 = (s1 + b) % 65521
            s2 = (s2 + s1) % 65521
        return (s2 << 16) | s1