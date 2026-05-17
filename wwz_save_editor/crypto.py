"""Decrypt and re-encrypt World War Z PlatformStorage save files (*.dat).

Reverse-engineered from wwzRetailEgs.exe (function FUN_140806f20 in Ghidra).

On-disk layout:
    [ XOR-obfuscated 4-byte zlib header ][ rest of the zlib stream ]

The "encryption" is just an XOR over the first 4 bytes (i.e. the zlib magic
header) with a 4-byte key derived from the filename plus two .rdata constants.
Everything past byte 4 is a stock zlib (deflate) stream.

Key derivation (32-bit math, wrapped mod 2^32):

    seed     = filename[3] if len(filename) >= 4 else filename[0]
    key_int  = (C1 * MUL + C2) * seed  mod 2^32
    key      = key_int packed little-endian (4 bytes)

The constants come from the executable's .rdata segment:

    C1  = 0x358637bd
    C2  = 0x40490fdb   # == float(pi) reinterpreted as int
    MUL = 0x49f42400

After zlib-inflate, the plaintext is normally compact JSON with an optional
trailing NUL byte. Saved files use deflate level 1 with the default window
bits, matching the game's `deflateInit_(strm, 1, "1.2.3")`.
"""
from __future__ import annotations

import struct
import zlib

C1 = 0x358637BD
C2 = 0x40490FDB
MUL = 0x49F42400
_MASK32 = 0xFFFFFFFF


def derive_key(filename: str) -> bytes:
    """Return the 4-byte XOR key for a given save filename (e.g. 'user_progression.dat')."""
    name = filename.encode("latin-1")
    if not name:
        raise ValueError("Empty filename: cannot derive key.")
    seed = name[0] if len(name) < 4 else name[3]
    key_int = ((C1 * MUL + C2) * seed) & _MASK32
    return struct.pack("<I", key_int)


def _xor_header(buf: bytes, key: bytes) -> bytes:
    out = bytearray(buf)
    for i in range(min(4, len(out))):
        out[i] ^= key[i]
    return bytes(out)


def decrypt(encrypted: bytes, filename: str) -> bytes:
    """Decrypt + inflate a save file's bytes. Returns the plaintext payload."""
    deobfuscated = _xor_header(encrypted, derive_key(filename))
    return zlib.decompress(deobfuscated)


def encrypt(plaintext: bytes, filename: str) -> bytes:
    """Deflate + obfuscate a plaintext payload. Output is byte-for-byte loadable by the game."""
    deflated = zlib.compress(plaintext, level=1)
    return _xor_header(deflated, derive_key(filename))
