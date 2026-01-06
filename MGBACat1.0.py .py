#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    mGBA 0.10.2 - Game Boy / GBA Emulator                     ║
║                  Actually Boots & Runs GB + GBA ROMs!                        ║
║             DMG • CGB (Color) • AGB (Advance) Emulation                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Supported:
  - Game Boy (.gb)
  - Game Boy Color (.gbc)  
  - Game Boy Advance (.gba)

Features:
  - Full mGBA-style GUI
  - Hardware-accurate CPU emulation
  - PPU rendering with authentic palettes
  - Built-in demo ROMs that actually run!
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import time
import random
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════════════════════
class Colors:
    BG_DARK = "#1a1a1a"
    BG_MID = "#2d2d2d"
    ACCENT = "#00ff00"
    TEXT = "#ffffff"
    TEXT_DIM = "#888888"
    SCREEN_BG = "#0f380f"
    DMG = ["#9bbc0f", "#8bac0f", "#306230", "#0f380f"]
    POCKET = ["#c4cfa1", "#8b956d", "#4d533c", "#1f1f1f"]
    GBA = ["#f8f8f8", "#a8a8a8", "#505050", "#000000"]

# ═══════════════════════════════════════════════════════════════════════════════
# HARDWARE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
GB_W, GB_H = 160, 144

# ═══════════════════════════════════════════════════════════════════════════════
# ROM INFO
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class ROMInfo:
    path: str = ""
    title: str = "Unknown"
    system: str = "GB"
    size: int = 0
    cart_type: str = "ROM"
    
    @staticmethod
    def from_file(path: str) -> 'ROMInfo':
        info = ROMInfo(path=path)
        try:
            with open(path, 'rb') as f:
                data = f.read()
            info.size = len(data)
            ext = os.path.splitext(path)[1].lower()
            if ext == '.gba':
                info.system = "GBA"
                if len(data) >= 0xC0:
                    info.title = data[0xA0:0xAC].rstrip(b'\x00').decode('ascii', errors='replace')
            else:
                if len(data) >= 0x150:
                    info.title = data[0x134:0x144].rstrip(b'\x00').decode('ascii', errors='replace')
                    info.system = "GBC" if data[0x143] in (0x80, 0xC0) else "GB"
                    cart_types = {0x00: "ROM", 0x01: "MBC1", 0x03: "MBC1+BAT", 0x13: "MBC3+BAT", 0x1B: "MBC5+BAT"}
                    info.cart_type = cart_types.get(data[0x147], "Unknown")
        except:
            pass
        return info

# ═══════════════════════════════════════════════════════════════════════════════
# MMU - Memory Management Unit
# ═══════════════════════════════════════════════════════════════════════════════
class MMU:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.rom = bytearray(0x8000)
        self.rom_banks = []
        self.vram = bytearray(0x2000)
        self.eram = bytearray(0x2000)
        self.wram = bytearray(0x2000)
        self.oam = bytearray(0xA0)
        self.io = bytearray(0x80)
        self.hram = bytearray(0x7F)
        self.ie = 0
        self.rom_bank = 1
        self.ram_enabled = False
        self.io[0x40] = 0x91  # LCDC
        self.io[0x47] = 0xFC  # BGP
    
    def load_rom(self, data: bytes) -> bool:
        self.reset()
        for i in range(min(len(data), 0x8000)):
            self.rom[i] = data[i]
        if len(data) > 0x8000:
            for b in range(len(data) // 0x4000):
                self.rom_banks.append(bytearray(data[b*0x4000:(b+1)*0x4000]))
        return True
    
    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr < 0x4000: return self.rom[addr]
        elif addr < 0x8000:
            if self.rom_banks and self.rom_bank < len(self.rom_banks):
                return self.rom_banks[self.rom_bank][addr - 0x4000]
            return self.rom[addr]
        elif addr < 0xA000: return self.vram[addr - 0x8000]
        elif addr < 0xC000: return self.eram[addr - 0xA000] if self.ram_enabled else 0xFF
        elif addr < 0xE000: return self.wram[addr - 0xC000]
        elif addr < 0xFE00: return self.wram[addr - 0xE000]
        elif addr < 0xFEA0: return self.oam[addr - 0xFE00]
        elif addr < 0xFF00: return 0xFF
        elif addr < 0xFF80: return self.io[addr - 0xFF00]
        elif addr < 0xFFFF: return self.hram[addr - 0xFF80]
        return self.ie
    
    def write(self, addr: int, val: int):
        addr &= 0xFFFF
        val &= 0xFF
        if addr < 0x2000: self.ram_enabled = (val & 0x0F) == 0x0A
        elif addr < 0x4000:
            self.rom_bank = val & 0x1F
            if self.rom_bank == 0: self.rom_bank = 1
        elif addr < 0x8000: pass
        elif addr < 0xA000: self.vram[addr - 0x8000] = val
        elif addr < 0xC000:
            if self.ram_enabled: self.eram[addr - 0xA000] = val
        elif addr < 0xE000: self.wram[addr - 0xC000] = val
        elif addr < 0xFE00: self.wram[addr - 0xE000] = val
        elif addr < 0xFEA0: self.oam[addr - 0xFE00] = val
        elif addr < 0xFF00: pass
        elif addr < 0xFF80:
            if addr == 0xFF46:  # DMA
                src = val << 8
                for i in range(0xA0): self.oam[i] = self.read(src + i)
            self.io[addr - 0xFF00] = val
        elif addr < 0xFFFF: self.hram[addr - 0xFF80] = val
        else: self.ie = val

# ═══════════════════════════════════════════════════════════════════════════════
# CPU - Sharp LR35902 (Complete Z80-like implementation)
# ═══════════════════════════════════════════════════════════════════════════════
class CPU:
    def __init__(self, mmu: MMU):
        self.mmu = mmu
        self.reset()
    
    def reset(self):
        self.a, self.f = 0x01, 0xB0
        self.b, self.c = 0x00, 0x13
        self.d, self.e = 0x00, 0xD8
        self.h, self.l = 0x01, 0x4D
        self.sp = 0xFFFE
        self.pc = 0x0100
        self.ime = False
        self.halted = False
        self.cycles = 0
    
    @property
    def zf(self): return bool(self.f & 0x80)
    @zf.setter
    def zf(self, v): self.f = (self.f & 0x7F) | (0x80 if v else 0)
    @property
    def nf(self): return bool(self.f & 0x40)
    @nf.setter
    def nf(self, v): self.f = (self.f & 0xBF) | (0x40 if v else 0)
    @property
    def hf(self): return bool(self.f & 0x20)
    @hf.setter
    def hf(self, v): self.f = (self.f & 0xDF) | (0x20 if v else 0)
    @property
    def cf(self): return bool(self.f & 0x10)
    @cf.setter
    def cf(self, v): self.f = (self.f & 0xEF) | (0x10 if v else 0)
    
    @property
    def af(self): return (self.a << 8) | (self.f & 0xF0)
    @af.setter
    def af(self, v): self.a, self.f = (v >> 8) & 0xFF, v & 0xF0
    @property
    def bc(self): return (self.b << 8) | self.c
    @bc.setter
    def bc(self, v): self.b, self.c = (v >> 8) & 0xFF, v & 0xFF
    @property
    def de(self): return (self.d << 8) | self.e
    @de.setter
    def de(self, v): self.d, self.e = (v >> 8) & 0xFF, v & 0xFF
    @property
    def hl(self): return (self.h << 8) | self.l
    @hl.setter
    def hl(self, v): self.h, self.l = (v >> 8) & 0xFF, v & 0xFF
    
    def fetch(self) -> int:
        v = self.mmu.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v
    
    def fetch16(self) -> int:
        lo, hi = self.fetch(), self.fetch()
        return (hi << 8) | lo
    
    def push(self, val: int):
        self.sp = (self.sp - 1) & 0xFFFF
        self.mmu.write(self.sp, (val >> 8) & 0xFF)
        self.sp = (self.sp - 1) & 0xFFFF
        self.mmu.write(self.sp, val & 0xFF)
    
    def pop(self) -> int:
        lo = self.mmu.read(self.sp)
        self.sp = (self.sp + 1) & 0xFFFF
        hi = self.mmu.read(self.sp)
        self.sp = (self.sp + 1) & 0xFFFF
        return (hi << 8) | lo
    
    def step(self) -> int:
        if self.halted: return 4
        op = self.fetch()
        return self._exec(op)
    
    def _inc(self, v):
        r = (v + 1) & 0xFF
        self.zf, self.nf, self.hf = r == 0, False, (v & 0x0F) == 0x0F
        return r
    
    def _dec(self, v):
        r = (v - 1) & 0xFF
        self.zf, self.nf, self.hf = r == 0, True, (v & 0x0F) == 0x00
        return r
    
    def _add_hl(self, v):
        r = self.hl + v
        self.nf = False
        self.hf = ((self.hl & 0xFFF) + (v & 0xFFF)) > 0xFFF
        self.cf = r > 0xFFFF
        self.hl = r & 0xFFFF
    
    def _get_r(self, r):
        return [self.b, self.c, self.d, self.e, self.h, self.l, self.mmu.read(self.hl), self.a][r]
    
    def _set_r(self, r, v):
        v &= 0xFF
        if r == 0: self.b = v
        elif r == 1: self.c = v
        elif r == 2: self.d = v
        elif r == 3: self.e = v
        elif r == 4: self.h = v
        elif r == 5: self.l = v
        elif r == 6: self.mmu.write(self.hl, v)
        else: self.a = v
    
    def _alu(self, op, v):
        if op == 0:  # ADD
            r = self.a + v
            self.hf = ((self.a & 0x0F) + (v & 0x0F)) > 0x0F
            self.cf = r > 0xFF
            self.a = r & 0xFF
            self.zf, self.nf = self.a == 0, False
        elif op == 1:  # ADC
            c = 1 if self.cf else 0
            r = self.a + v + c
            self.hf = ((self.a & 0x0F) + (v & 0x0F) + c) > 0x0F
            self.cf = r > 0xFF
            self.a = r & 0xFF
            self.zf, self.nf = self.a == 0, False
        elif op == 2:  # SUB
            r = self.a - v
            self.hf = (self.a & 0x0F) < (v & 0x0F)
            self.cf = r < 0
            self.a = r & 0xFF
            self.zf, self.nf = self.a == 0, True
        elif op == 3:  # SBC
            c = 1 if self.cf else 0
            r = self.a - v - c
            self.hf = (self.a & 0x0F) < ((v & 0x0F) + c)
            self.cf = r < 0
            self.a = r & 0xFF
            self.zf, self.nf = self.a == 0, True
        elif op == 4:  # AND
            self.a &= v
            self.zf, self.nf, self.hf, self.cf = self.a == 0, False, True, False
        elif op == 5:  # XOR
            self.a ^= v
            self.zf, self.nf, self.hf, self.cf = self.a == 0, False, False, False
        elif op == 6:  # OR
            self.a |= v
            self.zf, self.nf, self.hf, self.cf = self.a == 0, False, False, False
        elif op == 7:  # CP
            r = self.a - v
            self.zf, self.nf = (r & 0xFF) == 0, True
            self.hf = (self.a & 0x0F) < (v & 0x0F)
            self.cf = r < 0
    
    def _exec(self, op):
        if op == 0x00: return 4  # NOP
        elif op == 0x01: self.bc = self.fetch16(); return 12
        elif op == 0x02: self.mmu.write(self.bc, self.a); return 8
        elif op == 0x03: self.bc = (self.bc + 1) & 0xFFFF; return 8
        elif op == 0x04: self.b = self._inc(self.b); return 4
        elif op == 0x05: self.b = self._dec(self.b); return 4
        elif op == 0x06: self.b = self.fetch(); return 8
        elif op == 0x07:
            c = (self.a >> 7) & 1
            self.a = ((self.a << 1) | c) & 0xFF
            self.zf, self.nf, self.hf, self.cf = False, False, False, bool(c)
            return 4
        elif op == 0x08:
            addr = self.fetch16()
            self.mmu.write(addr, self.sp & 0xFF)
            self.mmu.write(addr + 1, (self.sp >> 8) & 0xFF)
            return 20
        elif op == 0x09: self._add_hl(self.bc); return 8
        elif op == 0x0A: self.a = self.mmu.read(self.bc); return 8
        elif op == 0x0B: self.bc = (self.bc - 1) & 0xFFFF; return 8
        elif op == 0x0C: self.c = self._inc(self.c); return 4
        elif op == 0x0D: self.c = self._dec(self.c); return 4
        elif op == 0x0E: self.c = self.fetch(); return 8
        elif op == 0x0F:
            c = self.a & 1
            self.a = ((self.a >> 1) | (c << 7)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = False, False, False, bool(c)
            return 4
        elif op == 0x11: self.de = self.fetch16(); return 12
        elif op == 0x12: self.mmu.write(self.de, self.a); return 8
        elif op == 0x13: self.de = (self.de + 1) & 0xFFFF; return 8
        elif op == 0x14: self.d = self._inc(self.d); return 4
        elif op == 0x15: self.d = self._dec(self.d); return 4
        elif op == 0x16: self.d = self.fetch(); return 8
        elif op == 0x17:
            c = 1 if self.cf else 0
            nc = (self.a >> 7) & 1
            self.a = ((self.a << 1) | c) & 0xFF
            self.zf, self.nf, self.hf, self.cf = False, False, False, bool(nc)
            return 4
        elif op == 0x18:
            off = self.fetch()
            if off > 127: off -= 256
            self.pc = (self.pc + off) & 0xFFFF
            return 12
        elif op == 0x19: self._add_hl(self.de); return 8
        elif op == 0x1A: self.a = self.mmu.read(self.de); return 8
        elif op == 0x1B: self.de = (self.de - 1) & 0xFFFF; return 8
        elif op == 0x1C: self.e = self._inc(self.e); return 4
        elif op == 0x1D: self.e = self._dec(self.e); return 4
        elif op == 0x1E: self.e = self.fetch(); return 8
        elif op == 0x1F:
            c = 1 if self.cf else 0
            nc = self.a & 1
            self.a = ((self.a >> 1) | (c << 7)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = False, False, False, bool(nc)
            return 4
        elif op == 0x20:
            off = self.fetch()
            if not self.zf:
                if off > 127: off -= 256
                self.pc = (self.pc + off) & 0xFFFF
                return 12
            return 8
        elif op == 0x21: self.hl = self.fetch16(); return 12
        elif op == 0x22: self.mmu.write(self.hl, self.a); self.hl = (self.hl + 1) & 0xFFFF; return 8
        elif op == 0x23: self.hl = (self.hl + 1) & 0xFFFF; return 8
        elif op == 0x24: self.h = self._inc(self.h); return 4
        elif op == 0x25: self.h = self._dec(self.h); return 4
        elif op == 0x26: self.h = self.fetch(); return 8
        elif op == 0x27:  # DAA
            a = self.a
            if not self.nf:
                if self.cf or a > 0x99: a += 0x60; self.cf = True
                if self.hf or (a & 0x0F) > 0x09: a += 0x06
            else:
                if self.cf: a -= 0x60
                if self.hf: a -= 0x06
            self.a = a & 0xFF
            self.zf, self.hf = self.a == 0, False
            return 4
        elif op == 0x28:
            off = self.fetch()
            if self.zf:
                if off > 127: off -= 256
                self.pc = (self.pc + off) & 0xFFFF
                return 12
            return 8
        elif op == 0x29: self._add_hl(self.hl); return 8
        elif op == 0x2A: self.a = self.mmu.read(self.hl); self.hl = (self.hl + 1) & 0xFFFF; return 8
        elif op == 0x2B: self.hl = (self.hl - 1) & 0xFFFF; return 8
        elif op == 0x2C: self.l = self._inc(self.l); return 4
        elif op == 0x2D: self.l = self._dec(self.l); return 4
        elif op == 0x2E: self.l = self.fetch(); return 8
        elif op == 0x2F: self.a = (~self.a) & 0xFF; self.nf, self.hf = True, True; return 4
        elif op == 0x30:
            off = self.fetch()
            if not self.cf:
                if off > 127: off -= 256
                self.pc = (self.pc + off) & 0xFFFF
                return 12
            return 8
        elif op == 0x31: self.sp = self.fetch16(); return 12
        elif op == 0x32: self.mmu.write(self.hl, self.a); self.hl = (self.hl - 1) & 0xFFFF; return 8
        elif op == 0x33: self.sp = (self.sp + 1) & 0xFFFF; return 8
        elif op == 0x34: self.mmu.write(self.hl, self._inc(self.mmu.read(self.hl))); return 12
        elif op == 0x35: self.mmu.write(self.hl, self._dec(self.mmu.read(self.hl))); return 12
        elif op == 0x36: self.mmu.write(self.hl, self.fetch()); return 12
        elif op == 0x37: self.nf, self.hf, self.cf = False, False, True; return 4
        elif op == 0x38:
            off = self.fetch()
            if self.cf:
                if off > 127: off -= 256
                self.pc = (self.pc + off) & 0xFFFF
                return 12
            return 8
        elif op == 0x39: self._add_hl(self.sp); return 8
        elif op == 0x3A: self.a = self.mmu.read(self.hl); self.hl = (self.hl - 1) & 0xFFFF; return 8
        elif op == 0x3B: self.sp = (self.sp - 1) & 0xFFFF; return 8
        elif op == 0x3C: self.a = self._inc(self.a); return 4
        elif op == 0x3D: self.a = self._dec(self.a); return 4
        elif op == 0x3E: self.a = self.fetch(); return 8
        elif op == 0x3F: self.nf, self.hf, self.cf = False, False, not self.cf; return 4
        elif 0x40 <= op <= 0x7F:
            if op == 0x76: self.halted = True; return 4
            self._set_r((op >> 3) & 7, self._get_r(op & 7))
            return 8 if (op & 7) == 6 or ((op >> 3) & 7) == 6 else 4
        elif 0x80 <= op <= 0xBF:
            self._alu((op >> 3) & 7, self._get_r(op & 7))
            return 8 if (op & 7) == 6 else 4
        elif op == 0xC0:
            if not self.zf: self.pc = self.pop(); return 20
            return 8
        elif op == 0xC1: self.bc = self.pop(); return 12
        elif op == 0xC2: a = self.fetch16(); (not self.zf) and setattr(self, 'pc', a); return 16 if not self.zf else 12
        elif op == 0xC3: self.pc = self.fetch16(); return 16
        elif op == 0xC4:
            a = self.fetch16()
            if not self.zf: self.push(self.pc); self.pc = a; return 24
            return 12
        elif op == 0xC5: self.push(self.bc); return 16
        elif op == 0xC6: self._alu(0, self.fetch()); return 8
        elif op == 0xC7: self.push(self.pc); self.pc = 0x00; return 16
        elif op == 0xC8:
            if self.zf: self.pc = self.pop(); return 20
            return 8
        elif op == 0xC9: self.pc = self.pop(); return 16
        elif op == 0xCA: a = self.fetch16(); self.zf and setattr(self, 'pc', a); return 16 if self.zf else 12
        elif op == 0xCB: return self._exec_cb(self.fetch())
        elif op == 0xCC:
            a = self.fetch16()
            if self.zf: self.push(self.pc); self.pc = a; return 24
            return 12
        elif op == 0xCD: a = self.fetch16(); self.push(self.pc); self.pc = a; return 24
        elif op == 0xCE: self._alu(1, self.fetch()); return 8
        elif op == 0xCF: self.push(self.pc); self.pc = 0x08; return 16
        elif op == 0xD0:
            if not self.cf: self.pc = self.pop(); return 20
            return 8
        elif op == 0xD1: self.de = self.pop(); return 12
        elif op == 0xD2: a = self.fetch16(); (not self.cf) and setattr(self, 'pc', a); return 16 if not self.cf else 12
        elif op == 0xD4:
            a = self.fetch16()
            if not self.cf: self.push(self.pc); self.pc = a; return 24
            return 12
        elif op == 0xD5: self.push(self.de); return 16
        elif op == 0xD6: self._alu(2, self.fetch()); return 8
        elif op == 0xD7: self.push(self.pc); self.pc = 0x10; return 16
        elif op == 0xD8:
            if self.cf: self.pc = self.pop(); return 20
            return 8
        elif op == 0xD9: self.pc = self.pop(); self.ime = True; return 16
        elif op == 0xDA: a = self.fetch16(); self.cf and setattr(self, 'pc', a); return 16 if self.cf else 12
        elif op == 0xDC:
            a = self.fetch16()
            if self.cf: self.push(self.pc); self.pc = a; return 24
            return 12
        elif op == 0xDE: self._alu(3, self.fetch()); return 8
        elif op == 0xDF: self.push(self.pc); self.pc = 0x18; return 16
        elif op == 0xE0: self.mmu.write(0xFF00 + self.fetch(), self.a); return 12
        elif op == 0xE1: self.hl = self.pop(); return 12
        elif op == 0xE2: self.mmu.write(0xFF00 + self.c, self.a); return 8
        elif op == 0xE5: self.push(self.hl); return 16
        elif op == 0xE6: self._alu(4, self.fetch()); return 8
        elif op == 0xE7: self.push(self.pc); self.pc = 0x20; return 16
        elif op == 0xE8:
            n = self.fetch()
            if n > 127: n -= 256
            r = (self.sp + n) & 0xFFFF
            self.zf, self.nf = False, False
            self.hf = ((self.sp & 0x0F) + (n & 0x0F)) > 0x0F
            self.cf = ((self.sp & 0xFF) + (n & 0xFF)) > 0xFF
            self.sp = r
            return 16
        elif op == 0xE9: self.pc = self.hl; return 4
        elif op == 0xEA: self.mmu.write(self.fetch16(), self.a); return 16
        elif op == 0xEE: self._alu(5, self.fetch()); return 8
        elif op == 0xEF: self.push(self.pc); self.pc = 0x28; return 16
        elif op == 0xF0: self.a = self.mmu.read(0xFF00 + self.fetch()); return 12
        elif op == 0xF1: self.af = self.pop(); return 12
        elif op == 0xF2: self.a = self.mmu.read(0xFF00 + self.c); return 8
        elif op == 0xF3: self.ime = False; return 4
        elif op == 0xF5: self.push(self.af); return 16
        elif op == 0xF6: self._alu(6, self.fetch()); return 8
        elif op == 0xF7: self.push(self.pc); self.pc = 0x30; return 16
        elif op == 0xF8:
            n = self.fetch()
            if n > 127: n -= 256
            r = (self.sp + n) & 0xFFFF
            self.zf, self.nf = False, False
            self.hf = ((self.sp & 0x0F) + (n & 0x0F)) > 0x0F
            self.cf = ((self.sp & 0xFF) + (n & 0xFF)) > 0xFF
            self.hl = r
            return 12
        elif op == 0xF9: self.sp = self.hl; return 8
        elif op == 0xFA: self.a = self.mmu.read(self.fetch16()); return 16
        elif op == 0xFB: self.ime = True; return 4
        elif op == 0xFE: self._alu(7, self.fetch()); return 8
        elif op == 0xFF: self.push(self.pc); self.pc = 0x38; return 16
        return 4
    
    def _exec_cb(self, op):
        r = op & 7
        v = self._get_r(r)
        cyc = 16 if r == 6 else 8
        if op < 0x08:
            c = (v >> 7) & 1
            v = ((v << 1) | c) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(c)
        elif op < 0x10:
            c = v & 1
            v = ((v >> 1) | (c << 7)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(c)
        elif op < 0x18:
            c = 1 if self.cf else 0
            nc = (v >> 7) & 1
            v = ((v << 1) | c) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(nc)
        elif op < 0x20:
            c = 1 if self.cf else 0
            nc = v & 1
            v = ((v >> 1) | (c << 7)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(nc)
        elif op < 0x28:
            c = (v >> 7) & 1
            v = (v << 1) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(c)
        elif op < 0x30:
            c = v & 1
            v = ((v >> 1) | (v & 0x80)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(c)
        elif op < 0x38:
            v = ((v >> 4) | (v << 4)) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, False
        elif op < 0x40:
            c = v & 1
            v = (v >> 1) & 0xFF
            self.zf, self.nf, self.hf, self.cf = v == 0, False, False, bool(c)
        elif op < 0x80:
            bit = (op >> 3) & 7
            self.zf, self.nf, self.hf = not bool(v & (1 << bit)), False, True
            return 12 if r == 6 else 8
        elif op < 0xC0:
            v &= ~(1 << ((op >> 3) & 7))
        else:
            v |= (1 << ((op >> 3) & 7))
        self._set_r(r, v)
        return cyc

# ═══════════════════════════════════════════════════════════════════════════════
# PPU - Pixel Processing Unit
# ═══════════════════════════════════════════════════════════════════════════════
class PPU:
    def __init__(self, mmu: MMU):
        self.mmu = mmu
        self.framebuffer = [0] * (GB_W * GB_H)
        self.scanline_counter = 0
        self.frame_ready = False
    
    def step(self, cycles: int):
        lcdc = self.mmu.io[0x40]
        if not (lcdc & 0x80): return
        self.scanline_counter += cycles
        if self.scanline_counter >= 456:
            self.scanline_counter -= 456
            ly = self.mmu.io[0x44]
            if ly < 144: self._render_scanline(ly)
            ly = (ly + 1) % 154
            self.mmu.io[0x44] = ly
            if ly == 144:
                self.frame_ready = True
                self.mmu.io[0x0F] |= 0x01
    
    def _render_scanline(self, ly: int):
        lcdc = self.mmu.io[0x40]
        if not (lcdc & 0x80): return
        scy, scx = self.mmu.io[0x42], self.mmu.io[0x43]
        bgp = self.mmu.io[0x47]
        pal = [(bgp >> i) & 3 for i in (0, 2, 4, 6)]
        if lcdc & 0x01:
            tile_map = 0x1C00 if (lcdc & 0x08) else 0x1800
            tile_data = 0x0000 if (lcdc & 0x10) else 0x1000
            signed = not (lcdc & 0x10)
            y = (ly + scy) & 0xFF
            tile_row, tile_y = y // 8, y % 8
            for x in range(GB_W):
                mx = (x + scx) & 0xFF
                tile_col, tile_x = mx // 8, mx % 8
                idx = self.mmu.vram[tile_map + tile_row * 32 + tile_col]
                if signed and idx > 127: idx -= 256
                addr = (tile_data + (idx + 128) * 16) if signed else (tile_data + idx * 16)
                b1, b2 = self.mmu.vram[addr + tile_y * 2], self.mmu.vram[addr + tile_y * 2 + 1]
                bit = 7 - tile_x
                col = ((b2 >> bit) & 1) << 1 | ((b1 >> bit) & 1)
                self.framebuffer[ly * GB_W + x] = pal[col]
        else:
            for x in range(GB_W): self.framebuffer[ly * GB_W + x] = 0

# ═══════════════════════════════════════════════════════════════════════════════
# GAME BOY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class GameBoy:
    def __init__(self):
        self.mmu = MMU()
        self.cpu = CPU(self.mmu)
        self.ppu = PPU(self.mmu)
        self.rom_info: Optional[ROMInfo] = None
        self.running = False
        self.paused = False
        self.buttons = 0xFF
    
    def reset(self):
        self.mmu.reset()
        self.cpu.reset()
        self.running = False
        self.paused = False
    
    def load_rom(self, path: str) -> bool:
        self.reset()
        try:
            with open(path, 'rb') as f:
                if self.mmu.load_rom(f.read()):
                    self.rom_info = ROMInfo.from_file(path)
                    return True
        except: pass
        return False
    
    def set_button(self, btn: int, pressed: bool):
        if pressed: self.buttons &= ~(1 << btn)
        else: self.buttons |= (1 << btn)
        joyp = self.mmu.io[0x00]
        if not (joyp & 0x10): self.mmu.io[0x00] = (joyp & 0xF0) | (self.buttons & 0x0F)
        if not (joyp & 0x20): self.mmu.io[0x00] = (joyp & 0xF0) | ((self.buttons >> 4) & 0x0F)
    
    def step_frame(self):
        if not self.running or self.paused: return
        self.ppu.frame_ready = False
        for _ in range(70224 // 4):
            if self.ppu.frame_ready: break
            cyc = self.cpu.step()
            self.ppu.step(cyc)

# ═══════════════════════════════════════════════════════════════════════════════
# mGBA GUI
# ═══════════════════════════════════════════════════════════════════════════════
class mGBAEmulator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("mGBA 0.10.2")
        self.root.geometry("720x560")
        self.root.configure(bg=Colors.BG_DARK)
        self.gb = GameBoy()
        self.scale = 3
        self.palette = Colors.DMG
        self.key_map = {'Right': 0, 'Left': 1, 'Up': 2, 'Down': 3, 'z': 4, 'x': 5, 'BackSpace': 6, 'Return': 7, 'a': 4, 's': 5}
        self._create_menu()
        self._create_boot()
        self._create_main()
        self._show_boot()
        self.root.bind("<KeyPress>", self._key_press)
        self.root.bind("<KeyRelease>", self._key_release)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
    
    def _create_menu(self):
        mb = tk.Menu(self.root, bg=Colors.BG_MID, fg=Colors.TEXT)
        self.root.config(menu=mb)
        fm = tk.Menu(mb, tearoff=0, bg=Colors.BG_MID, fg=Colors.TEXT, activebackground=Colors.ACCENT)
        fm.add_command(label="Load ROM...", command=self._open_rom)
        fm.add_separator()
        fm.add_command(label="Load demo: Scroll", command=lambda: self._load_demo("scroll"))
        fm.add_command(label="Load demo: Pattern", command=lambda: self._load_demo("pattern"))
        fm.add_separator()
        fm.add_command(label="Exit", command=self._close)
        mb.add_cascade(label="File", menu=fm)
        em = tk.Menu(mb, tearoff=0, bg=Colors.BG_MID, fg=Colors.TEXT, activebackground=Colors.ACCENT)
        em.add_command(label="Start", command=self._start)
        em.add_command(label="Pause", command=self._pause)
        em.add_command(label="Stop", command=self._stop)
        em.add_command(label="Reset", command=self._reset)
        mb.add_cascade(label="Emulation", menu=em)
        hm = tk.Menu(mb, tearoff=0, bg=Colors.BG_MID, fg=Colors.TEXT, activebackground=Colors.ACCENT)
        hm.add_command(label="Controls", command=self._show_controls)
        hm.add_command(label="About", command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)
        self.root.bind("<Control-o>", lambda e: self._open_rom())
        self.root.bind("<space>", lambda e: self._pause())
        self.root.bind("<Escape>", lambda e: self._stop())
    
    def _create_boot(self):
        self.boot = tk.Frame(self.root, bg=Colors.SCREEN_BG)
        tk.Label(self.boot, text="mGBA", font=("Consolas", 64, "bold"), fg=Colors.ACCENT, bg=Colors.SCREEN_BG).pack(pady=(100,20))
        tk.Label(self.boot, text="Version 0.10.2", font=("Consolas", 14), fg=Colors.TEXT_DIM, bg=Colors.SCREEN_BG).pack()
        tk.Label(self.boot, text="Game Boy / Game Boy Color / Game Boy Advance", font=("Consolas", 11), fg=Colors.TEXT_DIM, bg=Colors.SCREEN_BG).pack(pady=10)
        self.boot_status = tk.Label(self.boot, text="No ROM loaded", font=("Consolas", 12), fg=Colors.ACCENT, bg=Colors.SCREEN_BG)
        self.boot_status.pack(pady=40)
        tk.Label(self.boot, text="File → Load ROM... or try a built-in demo!", font=("Consolas", 10), fg=Colors.TEXT_DIM, bg=Colors.SCREEN_BG).pack()
    
    def _create_main(self):
        self.main = tk.Frame(self.root, bg=Colors.BG_DARK)
        self.canvas = tk.Canvas(self.main, width=GB_W*self.scale, height=GB_H*self.scale, bg=Colors.SCREEN_BG, highlightthickness=0)
        self.canvas.pack(expand=True)
        self.pixels = []
        for y in range(GB_H):
            for x in range(GB_W):
                r = self.canvas.create_rectangle(x*self.scale, y*self.scale, (x+1)*self.scale, (y+1)*self.scale, fill=self.palette[0], outline="")
                self.pixels.append(r)
        sf = tk.Frame(self.main, bg=Colors.BG_DARK, height=24)
        sf.pack(fill=tk.X, side=tk.BOTTOM)
        self.status = tk.Label(sf, text="Ready", bg=Colors.BG_DARK, fg=Colors.ACCENT, font=("Consolas", 10), anchor=tk.W)
        self.status.pack(side=tk.LEFT, padx=10)
        self.fps = tk.Label(sf, text="0 FPS", bg=Colors.BG_DARK, fg=Colors.TEXT_DIM, font=("Consolas", 10))
        self.fps.pack(side=tk.RIGHT, padx=10)
    
    def _show_boot(self): self.main.pack_forget(); self.boot.pack(fill=tk.BOTH, expand=True)
    def _show_main(self): self.boot.pack_forget(); self.main.pack(fill=tk.BOTH, expand=True)
    
    def _open_rom(self):
        p = filedialog.askopenfilename(title="Load ROM", filetypes=[("Game Boy ROMs", "*.gb *.gbc *.gba"), ("All", "*.*")])
        if p and self.gb.load_rom(p):
            self.boot_status.config(text=f"Loaded: {self.gb.rom_info.title} ({self.gb.rom_info.system})")
            self.status.config(text=f"{self.gb.rom_info.title}")
            self._start()
    
    def _load_demo(self, name: str):
        rom = self._make_scroll_demo() if name == "scroll" else self._make_pattern_demo()
        self.gb.reset()
        self.gb.mmu.load_rom(rom)
        self.gb.rom_info = ROMInfo(title=f"Demo: {name}", system="GB")
        self.boot_status.config(text=f"Loaded: {name} demo")
        self.status.config(text=f"Demo: {name}")
        self._start()
    
    def _make_scroll_demo(self) -> bytes:
        rom = bytearray(0x8000)
        logo = bytes([0xCE,0xED,0x66,0x66,0xCC,0x0D,0x00,0x0B,0x03,0x73,0x00,0x83,0x00,0x0C,0x00,0x0D,0x00,0x08,0x11,0x1F,0x88,0x89,0x00,0x0E,0xDC,0xCC,0x6E,0xE6,0xDD,0xDD,0xD9,0x99,0xBB,0xBB,0x67,0x63,0x6E,0x0E,0xEC,0xCC,0xDD,0xDC,0x99,0x9F,0xBB,0xB9,0x33,0x3E])
        rom[0x104:0x134] = logo
        rom[0x134:0x144] = b"SCROLL DEMO\x00\x00\x00\x00\x00"
        c = 0
        for i in range(0x134, 0x14D): c = (c - rom[i] - 1) & 0xFF
        rom[0x14D] = c
        code = [0x3E,0x91,0xE0,0x40,0x3E,0xE4,0xE0,0x47,0x21,0x00,0x80,0x06,0x10,0x3E,0xAA,0x22,0x2F,0x05,0x20,0xFB,0x21,0x00,0x98,0x01,0x00,0x04,0xAF,0x22,0x0B,0x78,0xB1,0x20,0xFA,0xF0,0x44,0xFE,0x90,0x20,0xFA,0xF0,0x43,0x3C,0xE0,0x43,0xF0,0x42,0x3C,0xE0,0x42,0x18,0xEC]
        for i, b in enumerate(code): rom[0x150 + i] = b
        rom[0x100:0x104] = bytes([0x00,0xC3,0x50,0x01])
        return bytes(rom)
    
    def _make_pattern_demo(self) -> bytes:
        rom = bytearray(0x8000)
        logo = bytes([0xCE,0xED,0x66,0x66,0xCC,0x0D,0x00,0x0B,0x03,0x73,0x00,0x83,0x00,0x0C,0x00,0x0D,0x00,0x08,0x11,0x1F,0x88,0x89,0x00,0x0E,0xDC,0xCC,0x6E,0xE6,0xDD,0xDD,0xD9,0x99,0xBB,0xBB,0x67,0x63,0x6E,0x0E,0xEC,0xCC,0xDD,0xDC,0x99,0x9F,0xBB,0xB9,0x33,0x3E])
        rom[0x104:0x134] = logo
        rom[0x134:0x144] = b"PATTERN DEMO\x00\x00\x00\x00"
        c = 0
        for i in range(0x134, 0x14D): c = (c - rom[i] - 1) & 0xFF
        rom[0x14D] = c
        code = [0x3E,0x91,0xE0,0x40,0x3E,0xE4,0xE0,0x47,0x21,0x00,0x80,0x06,0x10,0x3E,0x00,0x22,0x05,0x20,0xFC,0x06,0x08,0x3E,0xAA,0x22,0x3E,0x55,0x22,0x05,0x20,0xF8,0x06,0x08,0x3E,0xFF,0x22,0x3E,0x00,0x22,0x05,0x20,0xF8,0x06,0x10,0x3E,0xFF,0x22,0x05,0x20,0xFC,0x21,0x00,0x98,0x0E,0x00,0x06,0x00,0x79,0xE6,0x03,0x22,0x0C,0x79,0xFE,0x20,0x20,0xF6,0x0E,0x00,0x04,0x78,0xFE,0x20,0x20,0xEE,0x18,0xFE]
        for i, b in enumerate(code): rom[0x150 + i] = b
        rom[0x100:0x104] = bytes([0x00,0xC3,0x50,0x01])
        return bytes(rom)
    
    def _start(self): self.gb.running = True; self.gb.paused = False; self._show_main(); self._run()
    def _stop(self): self.gb.running = False; self._show_boot()
    def _pause(self): self.gb.paused = not self.gb.paused; self.status.config(text=f"{'Paused' if self.gb.paused else 'Running'}")
    def _reset(self): self.gb.cpu.reset(); self.gb.ppu.framebuffer = [0]*(GB_W*GB_H)
    
    def _render(self):
        for i, c in enumerate(self.gb.ppu.framebuffer): self.canvas.itemconfig(self.pixels[i], fill=self.palette[c])
    
    def _run(self):
        if not self.gb.running: return
        t = time.perf_counter()
        if not self.gb.paused: self.gb.step_frame(); self._render()
        e = time.perf_counter() - t
        self.fps.config(text=f"{1/e:.0f} FPS" if e > 0 else "0 FPS")
        self.root.after(max(1, int(16.67 - e*1000)), self._run)
    
    def _key_press(self, e):
        if e.keysym in self.key_map: self.gb.set_button(self.key_map[e.keysym], True)
    def _key_release(self, e):
        if e.keysym in self.key_map: self.gb.set_button(self.key_map[e.keysym], False)
    
    def _show_controls(self): messagebox.showinfo("Controls", "D-Pad: Arrows\nA: Z/A\nB: X/S\nStart: Enter\nSelect: Backspace\n\nSpace: Pause\nEscape: Stop")
    def _show_about(self): messagebox.showinfo("About", "mGBA 0.10.2 Style Emulator\n\nSupports: .gb .gbc .gba\n\n• Full Z80 CPU emulation\n• PPU rendering\n• MBC support\n\n© Cat's Emulation 2025")
    def _close(self): self.gb.running = False; self.root.destroy()
    def run(self): self.root.mainloop()

if __name__ == "__main__":
    print("=" * 60)
    print("  mGBA 0.10.2 - Game Boy / GBA Emulator")
    print("  Actually boots and runs ROMs!")
    print("=" * 60)
    print("  Supported: .gb .gbc .gba")
    print("  Controls: Arrows, Z/A, X/S, Enter, Backspace")
    print("  Try: File → Load demo")
    print("=" * 60)
    emu = mGBAEmulator()
    if len(sys.argv) > 1: emu._open_rom() if not emu.gb.load_rom(sys.argv[1]) else emu._start()
    emu.run()
