"""QR PNG data URLs. Stdlib only. Moved out of panel.py unchanged."""
import base64
import struct
import sys
import zlib

_QR_VER_L = {
    1:  (19,   7,  1, 19,  0, 0,   ()),
    2:  (34,  10,  1, 34,  0, 0,   (6, 18)),
    3:  (55,  15,  1, 55,  0, 0,   (6, 22)),
    4:  (80,  20,  1, 80,  0, 0,   (6, 26)),
    5:  (108, 26,  1, 108, 0, 0,   (6, 30)),
    6:  (136, 18,  2, 68,  0, 0,   (6, 34)),
    7:  (156, 20,  2, 78,  0, 0,   (6, 22, 38)),
    8:  (194, 24,  2, 97,  0, 0,   (6, 24, 42)),
    9:  (232, 30,  2, 116, 0, 0,   (6, 26, 46)),
    10: (274, 18,  2, 68,  2, 69,  (6, 28, 50)),
    11: (324, 20,  4, 81,  0, 0,   (6, 30, 54)),
    12: (370, 24,  2, 92,  2, 93,  (6, 32, 58)),
}
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_EXP[_i + 255] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
_QR_CACHE = {}


def _gf_mul(a: int, b: int) -> int:
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]] if (a and b) else 0


def _rs_encode(data: list, nsym: int) -> list:
    g = [1]
    for i in range(nsym):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= _gf_mul(c, _GF_EXP[i])
        g = ng
    res = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = res[i]
        if coef:
            for j in range(1, len(g)):
                res[i + j] ^= _gf_mul(g[j], coef)
    return res[len(data):]


def _make_qr_matrix(text: str) -> list:
    raw = text.encode("utf-8")
    n = len(raw)
    ver = 1
    for v in sorted(_QR_VER_L):
        cap = _QR_VER_L[v][0]
        cc_bits = 8 if v <= 9 else 16
        if 4 + cc_bits + 8 * n <= 8 * cap:
            ver = v
            break
    else:
        raise ValueError("QR data too long")
    total_dc, ec_len, nb1, db1, nb2, db2, aligns = _QR_VER_L[ver]
    cc_bits = 8 if ver <= 9 else 16
    bits = [0, 1, 0, 0]
    for i in range(cc_bits - 1, -1, -1):
        bits.append((n >> i) & 1)
    for b in raw:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    max_bits = total_dc * 8
    for _ in range(min(4, max_bits - len(bits))):
        bits.append(0)
    while len(bits) % 8 != 0:
        bits.append(0)
    codewords = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    pi = 0
    while len(codewords) < total_dc:
        codewords.append(pads[pi & 1])
        pi += 1

    blocks_d, blocks_e = [], []
    idx = 0
    for _ in range(nb1):
        blk = codewords[idx:idx + db1]
        idx += db1
        blocks_d.append(blk)
        blocks_e.append(_rs_encode(blk, ec_len))
    for _ in range(nb2):
        blk = codewords[idx:idx + db2]
        idx += db2
        blocks_d.append(blk)
        blocks_e.append(_rs_encode(blk, ec_len))

    interleaved = []
    for i in range(max(db1, db2)):
        for b in blocks_d:
            if i < len(b):
                interleaved.append(b[i])
    for i in range(ec_len):
        for e in blocks_e:
            interleaved.append(e[i])

    final_bits = []
    for cw in interleaved:
        for i in range(7, -1, -1):
            final_bits.append((cw >> i) & 1)
    if ver in (2, 3, 4, 5, 6):
        final_bits.extend([0] * 7)

    size = 17 + 4 * ver
    grid = [[0] * size for _ in range(size)]
    is_func = [[False] * size for _ in range(size)]

    def set_func(r, c, val):
        if 0 <= r < size and 0 <= c < size:
            grid[r][c] = 1 if val else 0
            is_func[r][c] = True

    def place_finder(tr, tc):
        for r in range(-1, 8):
            for c in range(-1, 8):
                v = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4)) if (0 <= r <= 6 and 0 <= c <= 6) else False
                set_func(tr + r, tc + c, v)

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)
    for i in range(8, size - 8):
        set_func(6, i, i % 2 == 0)
        set_func(i, 6, i % 2 == 0)
    for r in aligns:
        for c in aligns:
            if (r < 9 and c < 9) or (r < 9 and c > size - 10) or (r > size - 10 and c < 9):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    set_func(r + dr, c + dc, abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
    set_func(4 * ver + 9, 8, True)
    for i in range(9):
        if not is_func[8][i]:
            set_func(8, i, False)
        if not is_func[i][8]:
            set_func(i, 8, False)
    for i in range(8):
        set_func(8, size - 1 - i, False)
        set_func(size - 1 - i, 8, False)
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        vinfo = (ver << 12) | rem
        for i in range(18):
            bit = (vinfo >> i) & 1
            r, c = i // 3, size - 11 + (i % 3)
            set_func(r, c, bit)
            set_func(c, r, bit)

    bi = 0
    up = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not is_func[r][c]:
                    b = final_bits[bi] if bi < len(final_bits) else 0
                    bi += 1
                    if (r + c) % 2 == 0:
                        b ^= 1
                    grid[r][c] = b
        up = not up
        col -= 2

    f_data = 0b01000
    rem = f_data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    f_bits = ((f_data << 10) | rem) ^ 0x5412
    f_pos1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    f_pos2 = [(size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8), (size - 5, 8), (size - 6, 8), (size - 7, 8),
              (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1)]
    for i in range(15):
        bit = (f_bits >> i) & 1
        grid[f_pos1[i][0]][f_pos1[i][1]] = bit
        grid[f_pos2[i][0]][f_pos2[i][1]] = bit
    return grid


def qr_png_data_url(text: str, scale: int = 4, border: int = 2) -> str:
    """Render a QR code PNG data URL for sub_url using stdlib only."""
    if not text:
        return ""
    cached = _QR_CACHE.get(text)
    if cached:
        return cached
    try:
        grid = _make_qr_matrix(text)
        n = len(grid)
        dim = (n + 2 * border) * scale
        white_row = b"\x00" + (b"\xff" * dim)
        rows = [white_row] * (border * scale)
        for r in range(n):
            line = bytearray(b"\x00")
            line.extend(b"\xff" * (border * scale))
            for c in range(n):
                line.extend((b"\x00" if grid[r][c] else b"\xff") * scale)
            line.extend(b"\xff" * (border * scale))
            row_bytes = bytes(line)
            for _ in range(scale):
                rows.append(row_bytes)
        rows.extend([white_row] * (border * scale))
        raw = b"".join(rows)

        def _chunk(tag: bytes, body: bytes) -> bytes:
            return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", dim, dim, 8, 0, 0, 0, 0)
        png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
        res = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        if len(_QR_CACHE) > 16:
            _QR_CACHE.clear()
        _QR_CACHE[text] = res
        return res
    except Exception as e:
        sys.stderr.write(f"qr_png_data_url warning: {e}\n")
        return ""


