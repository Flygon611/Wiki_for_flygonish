# -*- coding: utf-8 -*-
"""纯 Python 的 AES-GCM（只用 AES 正向加密），只依赖标准库。

为什么自己写：构建期要把未公开作品的正文加密成 AES-GCM 密文（浏览器端用
WebCrypto 解密），而 Python 标准库没有 AES。为了守住「只依赖标准库、开箱即用」
这条线——不给构建加第三方依赖——这里实现一份最小可用的 AES-128/192/256 + GCM。

对外只有两个函数：
    seal(key, iv, plaintext, aad=b"")   -> bytes   （密文 ‖ 16 字节 GCM 认证标签）
    open_(key, iv, data, aad=b"")       -> bytes   （校验失败抛 ValueError）

GCM 只支持 96 位 IV（本站每页固定随机 12 字节），AAD 一般为空。
"""

import hmac

_ZERO = b"\x00" * 16
# GF(2^128) 里约简多项式 x^128 + x^7 + x^2 + x + 1 的低 128 位
_R = 0xE1000000000000000000000000000000

__all__ = ["AES", "seal", "open_"]


def _rotl8(x, n):
    return ((x << n) | (x >> (8 - n))) & 0xFF


def _xtime(a):
    a &= 0xFF
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _build_sbox():
    """按 FIPS-197 的仿射变换直接算 S 盒，免得把 256 个字节手抄错。"""
    sbox = bytearray(256)
    p = q = 1
    while True:
        p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)) & 0xFF   # p *= 3
        q ^= (q << 1) & 0xFF                                            # q /= 3
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ _rotl8(q, 1) ^ _rotl8(q, 2) ^ _rotl8(q, 3) ^ _rotl8(q, 4)
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()


def _rotl32(v, n):
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


def _build_tables():
    """Te0..Te3：把 S 盒、行移位和列混合并进查表，纯 Python 下快很多。

    Te0 一个字节的贡献是 [2,1,1,3]（从高位到低位），Te1/2/3 分别是它的
    循环左移 24/16/8 位，对应 [3,2,1,1]、[1,3,2,1]、[1,1,3,2]。
    """
    te0 = []
    for i in range(256):
        s = _SBOX[i]
        s2 = _xtime(s)
        te0.append((s2 << 24) | (s << 16) | (s << 8) | (s2 ^ s))
    return (te0, [_rotl32(v, 24) for v in te0],
            [_rotl32(v, 16) for v in te0], [_rotl32(v, 8) for v in te0])


_TE0, _TE1, _TE2, _TE3 = _build_tables()


class AES:
    """AES 分组加密（只做正向加密，GCM 用不到解密方向）。"""

    def __init__(self, key):
        if len(key) not in (16, 24, 32):
            raise ValueError("AES 密钥长度必须是 16/24/32 字节，收到 %d" % len(key))
        self.key = bytes(key)
        self.nk = len(key) // 4
        self.nr = self.nk + 6
        self.rk = self._expand()

    def _expand(self):
        nk, nr = self.nk, self.nr
        sbox = _SBOX
        w = [list(self.key[4 * i:4 * i + 4]) for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            temp = list(w[i - 1])
            if i % nk == 0:
                temp = [sbox[b] for b in temp[1:] + temp[:1]]
                temp[0] ^= rcon
                rcon = _xtime(rcon)
            elif nk > 6 and i % nk == 4:
                temp = [sbox[b] for b in temp]
            w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
        # 摊平成 4*(nr+1) 个 32 位轮密钥字（每列一个字），下标就是 4*轮数+列号
        return [(x[0] << 24) | (x[1] << 16) | (x[2] << 8) | x[3] for x in w]

    def encrypt_block(self, block):
        if len(block) != 16:
            raise ValueError("AES 分组必须是 16 字节")
        b = block
        s0 = int.from_bytes(b[0:4], "big")
        s1 = int.from_bytes(b[4:8], "big")
        s2 = int.from_bytes(b[8:12], "big")
        s3 = int.from_bytes(b[12:16], "big")
        rk = self.rk
        s0 ^= rk[0]
        s1 ^= rk[1]
        s2 ^= rk[2]
        s3 ^= rk[3]
        te0, te1, te2, te3 = _TE0, _TE1, _TE2, _TE3
        k = 4
        for _ in range(self.nr - 1):
            t0 = te0[s0 >> 24] ^ te1[(s1 >> 16) & 0xFF] ^ te2[(s2 >> 8) & 0xFF] ^ te3[s3 & 0xFF] ^ rk[k]
            t1 = te0[s1 >> 24] ^ te1[(s2 >> 16) & 0xFF] ^ te2[(s3 >> 8) & 0xFF] ^ te3[s0 & 0xFF] ^ rk[k + 1]
            t2 = te0[s2 >> 24] ^ te1[(s3 >> 16) & 0xFF] ^ te2[(s0 >> 8) & 0xFF] ^ te3[s1 & 0xFF] ^ rk[k + 2]
            t3 = te0[s3 >> 24] ^ te1[(s0 >> 16) & 0xFF] ^ te2[(s1 >> 8) & 0xFF] ^ te3[s2 & 0xFF] ^ rk[k + 3]
            s0, s1, s2, s3 = t0, t1, t2, t3
            k += 4
        sb = _SBOX
        t0 = ((sb[s0 >> 24] << 24) | (sb[(s1 >> 16) & 0xFF] << 16) |
              (sb[(s2 >> 8) & 0xFF] << 8) | sb[s3 & 0xFF]) ^ rk[k]
        t1 = ((sb[s1 >> 24] << 24) | (sb[(s2 >> 16) & 0xFF] << 16) |
              (sb[(s3 >> 8) & 0xFF] << 8) | sb[s0 & 0xFF]) ^ rk[k + 1]
        t2 = ((sb[s2 >> 24] << 24) | (sb[(s3 >> 16) & 0xFF] << 16) |
              (sb[(s0 >> 8) & 0xFF] << 8) | sb[s1 & 0xFF]) ^ rk[k + 2]
        t3 = ((sb[s3 >> 24] << 24) | (sb[(s0 >> 16) & 0xFF] << 16) |
              (sb[(s1 >> 8) & 0xFF] << 8) | sb[s2 & 0xFF]) ^ rk[k + 3]
        return t0.to_bytes(4, "big") + t1.to_bytes(4, "big") + \
            t2.to_bytes(4, "big") + t3.to_bytes(4, "big")


# ------------------------------------------------------------------ GCM

def _gf_mul(x, y):
    """GF(2^128) 乘法（比特串按 GCM 的约定：最高位是 x^0 的系数）。"""
    z = 0
    v = y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _R
        else:
            v >>= 1
    return z


def _ghash(h, data):
    """data 长度必须是 16 的整数倍。"""
    y = 0
    for i in range(0, len(data), 16):
        y = _gf_mul(y ^ int.from_bytes(data[i:i + 16], "big"), h)
    return y


def _pad16(data):
    rem = len(data) % 16
    return data if rem == 0 else data + b"\x00" * (16 - rem)


def _gctr(aes, icb, data):
    out = bytearray()
    cb = icb
    for i in range(0, len(data), 16):
        ks = aes.encrypt_block(cb.to_bytes(16, "big"))
        out += bytes(a ^ b for a, b in zip(data[i:i + 16], ks))
        low = (cb & 0xFFFFFFFF) + 1
        cb = (cb & ~0xFFFFFFFF) | (low & 0xFFFFFFFF)     # inc32
    return bytes(out)


def _ctx(key, iv):
    if len(iv) != 12:
        raise ValueError("本站只使用 96 位 IV，收到 %d 字节" % len(iv))
    aes = AES(key)
    h = int.from_bytes(aes.encrypt_block(_ZERO), "big")
    j0 = int.from_bytes(iv + b"\x00\x00\x00\x01", "big")
    return aes, h, j0


def _tag(aes, h, j0, aad, ct):
    lens = (len(aad) * 8).to_bytes(8, "big") + (len(ct) * 8).to_bytes(8, "big")
    s = _ghash(h, _pad16(aad) + _pad16(ct) + lens)
    return (s ^ int.from_bytes(aes.encrypt_block(j0.to_bytes(16, "big")), "big")).to_bytes(16, "big")


def seal(key, iv, plaintext, aad=b""):
    """AES-GCM 加密，返回 密文 + 16 字节认证标签（和 WebCrypto 的 ciphertext 一致）。"""
    aes, h, j0 = _ctx(key, iv)
    ct = _gctr(aes, (j0 & ~0xFFFFFFFF) | (((j0 & 0xFFFFFFFF) + 1) & 0xFFFFFFFF), plaintext)
    return ct + _tag(aes, h, j0, aad, ct)


def open_(key, iv, data, aad=b""):
    """AES-GCM 解密；认证标签对不上就抛 ValueError（不返回任何明文）。"""
    if len(data) < 16:
        raise ValueError("密文太短，缺少 GCM 认证标签")
    aes, h, j0 = _ctx(key, iv)
    ct, tag = data[:-16], data[-16:]
    if not hmac.compare_digest(_tag(aes, h, j0, aad, ct), tag):
        raise ValueError("GCM 认证标签校验失败：密钥不对或密文被改动过")
    return _gctr(aes, (j0 & ~0xFFFFFFFF) | (((j0 & 0xFFFFFFFF) + 1) & 0xFFFFFFFF), ct)
