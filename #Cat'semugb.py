#!/usr/bin/env python3
"""
Mini-mGBA-GB (Tkinter Edition)
Author: CatSDK / Defensive Emulator Lab
Purpose: Educational Game Boy emulator scaffold
Status: WORKING PROTOTYPE (UI + ROM load + CPU loop)
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import struct

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
SCREEN_W, SCREEN_H = 160, 144
SCALE = 3
CLOCK_HZ = 4_194_304  # GB clock
FPS = 60

# ─────────────────────────────────────────────
# CPU (MINIMAL / SAFE SUBSET)
# ─────────────────────────────────────────────
class MiniGB_CPU:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pc = 0x100
        self.sp = 0xFFFE
        self.a = self.f = 0
        self.b = self.c = 0
        self.d = self.e = 0
        self.h = self.l = 0
        self.halted = False

    def step(self, mem):
        if self.halted:
            return 4

        opcode = mem[self.pc]
        self.pc += 1

        # VERY SMALL OPCODE SET (SAFE)
        if opcode == 0x00:      # NOP
            return 4
        elif opcode == 0x76:    # HALT
            self.halted = True
            return 4
        else:
            # Unknown opcode → safely skip
            return 4

# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────
class MiniGB_Memory:
    def __init__(self):
        self.mem = bytearray(0x10000)

    def load_rom(self, path):
        with open(path, "rb") as f:
            data = f.read()
        self.mem[0x0000:0x8000] = data[:0x8000]

    def __getitem__(self, addr):
        return self.mem[addr & 0xFFFF]

    def __setitem__(self, addr, val):
        self.mem[addr & 0xFFFF] = val & 0xFF

# ─────────────────────────────────────────────
# EMULATOR CORE
# ─────────────────────────────────────────────
class MiniGB:
    def __init__(self):
        self.cpu = MiniGB_CPU()
        self.mem = MiniGB_Memory()
        self.running = False

    def reset(self):
        self.cpu.reset()
        self.running = False

    def load_rom(self, path):
        self.mem.load_rom(path)
        self.reset()

    def run_frame(self):
        cycles = 0
        while cycles < CLOCK_HZ // FPS:
            cycles += self.cpu.step(self.mem)

# ─────────────────────────────────────────────
# TKINTER UI (mGBA-STYLE)
# ─────────────────────────────────────────────
class MiniMGBAGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini-mGBA-GB (CatSDK)")
        self.root.resizable(False, False)

        self.gb = MiniGB()

        self.canvas = tk.Canvas(
            root,
            width=SCREEN_W * SCALE,
            height=SCREEN_H * SCALE,
            bg="black"
        )
        self.canvas.pack()

        self.status = tk.Label(root, text="No ROM loaded", anchor="w")
        self.status.pack(fill="x")

        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Load ROM", command=self.load_rom)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        root.config(menu=menubar)

        self.running = False
        self.root.after(16, self.tick)

    def load_rom(self):
        path = filedialog.askopenfilename(
            title="Open Game Boy ROM",
            filetypes=[("Game Boy ROM", "*.gb"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.gb.load_rom(path)
            self.running = True
            self.status.config(text=f"Loaded: {path.split('/')[-1]}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def tick(self):
        if self.running:
            self.gb.run_frame()
            self.draw_placeholder()
        self.root.after(1000 // FPS, self.tick)

    def draw_placeholder(self):
        # Placeholder frame (grid = proof of life)
        self.canvas.delete("all")
        for y in range(0, SCREEN_H, 8):
            for x in range(0, SCREEN_W, 8):
                c = "#2aff2a" if (x ^ y) & 8 else "#145214"
                self.canvas.create_rectangle(
                    x * SCALE,
                    y * SCALE,
                    (x + 8) * SCALE,
                    (y + 8) * SCALE,
                    fill=c,
                    outline=""
                )

# ─────────────────────────────────────────────
# BOOT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = MiniMGBAGUI(root)
    root.mainloop()
