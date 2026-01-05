
import tkinter as tk
from tkinter import filedialog
import random
import time


class Chip8:
    """
    Single-file CHIP-8 emulator core + Tkinter rendering.

    -------------------------------------------------------------------------
    Opcode table (classic CHIP-8; 35 instruction patterns)
    -------------------------------------------------------------------------
    0NNN  SYS addr        (ignored)
    00E0  CLS             Clear display
    00EE  RET             Return from subroutine
    1NNN  JP addr         Jump to addr
    2NNN  CALL addr       Call subroutine at addr
    3XNN  SE Vx, byte     Skip next if Vx == NN
    4XNN  SNE Vx, byte    Skip next if Vx != NN
    5XY0  SE Vx, Vy       Skip next if Vx == Vy
    6XNN  LD Vx, byte     Vx = NN
    7XNN  ADD Vx, byte    Vx += NN
    8XY0  LD Vx, Vy       Vx = Vy
    8XY1  OR Vx, Vy       Vx |= Vy
    8XY2  AND Vx, Vy      Vx &= Vy
    8XY3  XOR Vx, Vy      Vx ^= Vy
    8XY4  ADD Vx, Vy      Vx += Vy, VF = carry
    8XY5  SUB Vx, Vy      Vx -= Vy, VF = NOT borrow
    8XY6  SHR Vx {,Vy}    Vx = Vy >> 1 (classic), VF = LSB of Vy
    8XY7  SUBN Vx, Vy     Vx = Vy - Vx, VF = NOT borrow
    8XYE  SHL Vx {,Vy}    Vx = Vy << 1 (classic), VF = MSB of Vy
    9XY0  SNE Vx, Vy      Skip next if Vx != Vy
    ANNN  LD I, addr      I = NNN
    BNNN  JP V0, addr     Jump to NNN + V0
    CXNN  RND Vx, byte    Vx = (rand8() & NN)
    DXYN  DRW Vx,Vy,N     Draw N-byte sprite at (Vx,Vy), XOR, VF=collision
    EX9E  SKP Vx          Skip next if key[Vx] pressed
    EXA1  SKNP Vx         Skip next if key[Vx] not pressed
    FX07  LD Vx, DT       Vx = delay_timer
    FX0A  LD Vx, K        Wait for key, then Vx = key
    FX15  LD DT, Vx       delay_timer = Vx
    FX18  LD ST, Vx       sound_timer = Vx
    FX1E  ADD I, Vx       I += Vx
    FX29  LD F, Vx        I = font_addr(Vx)
    FX33  LD B, Vx        Store BCD of Vx at mem[I..I+2]
    FX55  LD [I], V0..Vx  Store V0..Vx at mem[I..], I += x+1 (classic)
    FX65  LD V0..Vx, [I]  Load V0..Vx from mem[I..], I += x+1 (classic)
    -------------------------------------------------------------------------
    """

    # --- Display constants ---
    W, H = 64, 32

    # Standard CHIP-8 font (IBM-style) 0-F, 5 bytes each.
    FONT_START = 0x050
    FONT = [
        0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
        0x20, 0x60, 0x20, 0x20, 0x70,  # 1
        0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
        0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
        0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
        0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
        0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
        0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
        0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
        0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
        0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
        0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
        0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
        0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
        0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
        0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
    ]

    # Keypad mapping (hex keypad -> modern keyboard)
    # CHIP-8 keypad:
    # 1 2 3 C     ->   1 2 3 4
    # 4 5 6 D     ->   Q W E R
    # 7 8 9 E     ->   A S D F
    # A 0 B F     ->   Z X C V
    KEYMAP = {
        '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
        'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
        'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
        'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF,
    }

    def __init__(self, root: tk.Tk, canvas: tk.Canvas, status_var: tk.StringVar,
                 display_scale: int = 9):
        self.root = root
        self.canvas = canvas
        self.status_var = status_var

        # Rendering config
        self.scale = int(display_scale)
        self.off_color = "#000000"
        self.on_color = "#00ff00"

        # Center the 64x32 display inside the canvas
        c_w = int(self.canvas["width"])
        c_h = int(self.canvas["height"])
        disp_w = self.W * self.scale
        disp_h = self.H * self.scale
        self.x_off = max(0, (c_w - disp_w) // 2)
        self.y_off = max(0, (c_h - disp_h) // 2)

        # Pre-create pixel rectangles (Canvas drawing; nearest-neighbor via integer scaling)
        self._pixel_ids = [0] * (self.W * self.H)
        for y in range(self.H):
            for x in range(self.W):
                x0 = self.x_off + x * self.scale
                y0 = self.y_off + y * self.scale
                x1 = x0 + self.scale
                y1 = y0 + self.scale
                rid = self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill=self.off_color,
                    outline=self.off_color,
                )
                self._pixel_ids[x + y * self.W] = rid

        # Emu config / quirks: "classic-ish" behavior
        self.shift_uses_vy = True          # 8XY6 / 8XYE: use Vy as source (original CHIP-8)
        self.fx55_fx65_increment_i = True  # FX55/FX65: I += x+1 (classic CHIP-8)

        # Runtime state
        self.running = True
        self.paused = True  # start paused until ROM loaded

        # Timing for ~60Hz tick (after-based; drift-corrected)
        self._tick_hz = 60.0
        self._ips_per_tick = 9  # 9 instructions per 60 Hz tick => ~540 IPS
        self._next_tick_t = time.perf_counter()
        self._after_id = None

        # Lightweight FPS estimate (EMA of tick rate)
        self._last_tick_t = time.perf_counter()
        self._fps = 0.0
        self._status_last_t = self._last_tick_t
        self._status_period_s = 0.25  # update label ~4x/sec

        # Input wait state (Fx0A)
        self.waiting_for_key = False
        self.wait_reg = 0

        # Init machine
        self.reset()
        self._render_full_clear()
        self._update_status(force=True)

    # ----------------------- Public API (UI calls) -----------------------

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._update_status(force=True)

    def load_rom_via_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Load CHIP-8 ROM",
            filetypes=[("CHIP-8 ROMs", "*.ch8 *.c8 *.rom *.bin"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.load_rom(path)
        except Exception as e:
            self.status_var.set(f"Load failed: {e}")

    def load_rom(self, path: str) -> None:
        with open(path, "rb") as f:
            data = f.read()

        # Hard limit: program area 0x200..0xFFF
        max_len = 4096 - 0x200
        if len(data) > max_len:
            raise ValueError(f"ROM too large ({len(data)} bytes > {max_len} bytes)")

        self.reset()
        for i, b in enumerate(data):
            self.memory[0x200 + i] = b

        self.paused = False
        self.waiting_for_key = False
        self._render_full_clear()
        self._update_status(force=True)

    def shutdown(self) -> None:
        self.running = False
        try:
            if self._after_id is not None:
                self.root.after_cancel(self._after_id)
        except Exception:
            pass
        self._after_id = None

    # ----------------------- Machine init/reset --------------------------

    def reset(self) -> None:
        # Core components
        self.memory = bytearray(4096)
        self.V = [0] * 16
        self.I = 0
        self.pc = 0x200

        self.stack = [0] * 16
        self.sp = 0

        self.delay_timer = 0
        self.sound_timer = 0

        self.keys = [0] * 16

        self.gfx = [0] * (self.W * self.H)
        self.dirty = set()  # indices that changed since last render

        # Load font into memory at 0x050.
        # (Requirement text mentions 0x050–0x1A4; classic font occupies 0x050–0x09F.)
        for i, b in enumerate(self.FONT):
            self.memory[self.FONT_START + i] = b

    # ----------------------- Tk scheduling loop --------------------------

    def start(self) -> None:
        """Begin the 60Hz tick loop."""
        self._next_tick_t = time.perf_counter()
        self._last_tick_t = self._next_tick_t
        if self._after_id is None:
            self._schedule_next_tick()

    def _schedule_next_tick(self) -> None:
        if not self.running:
            return

        now = time.perf_counter()
        delay_s = self._next_tick_t - now
        delay_ms = max(0, int(delay_s * 1000))
        self._after_id = self.root.after(delay_ms, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return

        now = time.perf_counter()

        # FPS (tick rate) estimate via EMA
        dt = now - self._last_tick_t
        self._last_tick_t = now
        if dt > 0:
            inst = 1.0 / dt
            self._fps = inst if self._fps <= 0 else (self._fps * 0.9 + inst * 0.1)

        # --- Emulation work (60Hz) ---
        if not self.paused:
            # Execute ~540 IPS => 9 opcodes per tick at 60Hz
            for _ in range(self._ips_per_tick):
                if self.waiting_for_key:
                    break
                self._cycle()

            # Timers tick at 60Hz (even if waiting for key)
            if self.delay_timer > 0:
                self.delay_timer -= 1
            if self.sound_timer > 0:
                # Minimal audible cue; real CHIP-8 buzz is continuous.
                if self.sound_timer == 1:
                    try:
                        self.root.bell()
                    except Exception:
                        pass
                self.sound_timer -= 1

        # Render if needed
        if self.dirty:
            self._render_dirty()

        # Status update (throttled)
        if (now - self._status_last_t) >= self._status_period_s:
            self._status_last_t = now
            self._update_status(force=False)

        # Maintain 60Hz target by advancing the ideal tick time
        self._next_tick_t += 1.0 / self._tick_hz

        # If we're super behind (window moved, breakpoint, etc.), reset to "now"
        if self._next_tick_t < now - 0.25:
            self._next_tick_t = now

        self._schedule_next_tick()

    # ----------------------- CPU: fetch/decode/execute -------------------

    def _cycle(self) -> None:
        # Fetch (big endian)
        op = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc = (self.pc + 2) & 0x0FFF

        x = (op & 0x0F00) >> 8
        y = (op & 0x00F0) >> 4
        n = op & 0x000F
        nn = op & 0x00FF
        nnn = op & 0x0FFF

        top = op & 0xF000

        if op == 0x00E0:  # CLS
            self._cls()
        elif op == 0x00EE:  # RET
            self._ret()
        elif top == 0x0000:
            # 0NNN SYS addr (ignored on modern interpreters)
            pass
        elif top == 0x1000:  # JP addr
            self.pc = nnn
        elif top == 0x2000:  # CALL addr
            self._call(nnn)
        elif top == 0x3000:  # SE Vx, byte
            if self.V[x] == nn:
                self.pc = (self.pc + 2) & 0x0FFF
        elif top == 0x4000:  # SNE Vx, byte
            if self.V[x] != nn:
                self.pc = (self.pc + 2) & 0x0FFF
        elif top == 0x5000:  # SE Vx, Vy
            if n == 0 and self.V[x] == self.V[y]:
                self.pc = (self.pc + 2) & 0x0FFF
        elif top == 0x6000:  # LD Vx, byte
            self.V[x] = nn
        elif top == 0x7000:  # ADD Vx, byte
            self.V[x] = (self.V[x] + nn) & 0xFF
        elif top == 0x8000:
            self._op_8xy_(x, y, n)
        elif top == 0x9000:  # SNE Vx, Vy
            if n == 0 and self.V[x] != self.V[y]:
                self.pc = (self.pc + 2) & 0x0FFF
        elif top == 0xA000:  # LD I, addr
            self.I = nnn
        elif top == 0xB000:  # JP V0, addr
            self.pc = (nnn + self.V[0]) & 0x0FFF
        elif top == 0xC000:  # RND Vx, byte
            self.V[x] = random.randint(0, 255) & nn
        elif top == 0xD000:  # DRW Vx, Vy, nibble
            self._draw(self.V[x], self.V[y], n)
        elif top == 0xE000:
            self._op_ex__(x, nn)
        elif top == 0xF000:
            self._op_fx__(x, nn)
        else:
            # Unknown opcode: ignore (could also raise)
            pass

    def _op_8xy_(self, x: int, y: int, n: int) -> None:
        if n == 0x0:      # LD Vx, Vy
            self.V[x] = self.V[y]
        elif n == 0x1:    # OR
            self.V[x] |= self.V[y]
        elif n == 0x2:    # AND
            self.V[x] &= self.V[y]
        elif n == 0x3:    # XOR
            self.V[x] ^= self.V[y]
        elif n == 0x4:    # ADD with carry
            s = self.V[x] + self.V[y]
            self.V[0xF] = 1 if s > 0xFF else 0
            self.V[x] = s & 0xFF
        elif n == 0x5:    # SUB Vx -= Vy
            self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
        elif n == 0x6:    # SHR
            src = self.V[y] if self.shift_uses_vy else self.V[x]
            self.V[0xF] = src & 0x1
            self.V[x] = (src >> 1) & 0xFF
        elif n == 0x7:    # SUBN Vx = Vy - Vx
            self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
        elif n == 0xE:    # SHL
            src = self.V[y] if self.shift_uses_vy else self.V[x]
            self.V[0xF] = (src >> 7) & 0x1
            self.V[x] = (src << 1) & 0xFF

    def _op_ex__(self, x: int, nn: int) -> None:
        key = self.V[x] & 0xF
        if nn == 0x9E:  # SKP
            if self.keys[key]:
                self.pc = (self.pc + 2) & 0x0FFF
        elif nn == 0xA1:  # SKNP
            if not self.keys[key]:
                self.pc = (self.pc + 2) & 0x0FFF

    def _op_fx__(self, x: int, nn: int) -> None:
        if nn == 0x07:  # LD Vx, DT
            self.V[x] = self.delay_timer
        elif nn == 0x0A:  # LD Vx, K
            # Stall until a key is pressed; PC was already advanced, so rewind it.
            self.waiting_for_key = True
            self.wait_reg = x
            self.pc = (self.pc - 2) & 0x0FFF
        elif nn == 0x15:  # LD DT, Vx
            self.delay_timer = self.V[x]
        elif nn == 0x18:  # LD ST, Vx
            self.sound_timer = self.V[x]
        elif nn == 0x1E:  # ADD I, Vx
            self.I = (self.I + self.V[x]) & 0x0FFF
        elif nn == 0x29:  # LD F, Vx
            digit = self.V[x] & 0xF
            self.I = self.FONT_START + (digit * 5)
        elif nn == 0x33:  # LD B, Vx
            v = self.V[x]
            self.memory[self.I] = v // 100
            self.memory[(self.I + 1) & 0x0FFF] = (v // 10) % 10
            self.memory[(self.I + 2) & 0x0FFF] = v % 10
        elif nn == 0x55:  # LD [I], V0..Vx
            for i in range(x + 1):
                self.memory[(self.I + i) & 0x0FFF] = self.V[i]
            if self.fx55_fx65_increment_i:
                self.I = (self.I + x + 1) & 0x0FFF
        elif nn == 0x65:  # LD V0..Vx, [I]
            for i in range(x + 1):
                self.V[i] = self.memory[(self.I + i) & 0x0FFF]
            if self.fx55_fx65_increment_i:
                self.I = (self.I + x + 1) & 0x0FFF

    # ----------------------- Helpers: stack/display ----------------------

    def _call(self, addr: int) -> None:
        if self.sp >= 16:
            return  # stack overflow -> ignore
        self.stack[self.sp] = self.pc
        self.sp += 1
        self.pc = addr

    def _ret(self) -> None:
        if self.sp <= 0:
            return  # stack underflow -> ignore
        self.sp -= 1
        self.pc = self.stack[self.sp] & 0x0FFF

    def _cls(self) -> None:
        # Clear display buffer
        if any(self.gfx):
            self.gfx = [0] * (self.W * self.H)
        self.dirty = set(range(self.W * self.H))

    def _draw(self, vx: int, vy: int, n: int) -> None:
        x0 = vx % self.W
        y0 = vy % self.H

        self.V[0xF] = 0
        for row in range(n):
            sprite = self.memory[(self.I + row) & 0x0FFF]
            y = (y0 + row) % self.H
            for bit in range(8):
                if (sprite & (0x80 >> bit)) == 0:
                    continue
                x = (x0 + bit) % self.W
                idx = x + y * self.W
                if self.gfx[idx] == 1:
                    self.V[0xF] = 1
                self.gfx[idx] ^= 1
                self.dirty.add(idx)

    # ----------------------- Rendering ----------------------------------

    def _render_full_clear(self) -> None:
        # Force a full redraw to black (used on reset/load)
        self.gfx = [0] * (self.W * self.H)
        self.dirty = set(range(self.W * self.H))
        self._render_dirty()

    def _render_dirty(self) -> None:
        # Update only changed pixels
        for idx in self.dirty:
            rid = self._pixel_ids[idx]
            color = self.on_color if self.gfx[idx] else self.off_color
            self.canvas.itemconfig(rid, fill=color, outline=color)
        self.dirty.clear()

    # ----------------------- Status / UI glue ----------------------------

    def _update_status(self, force: bool = False) -> None:
        if self.paused:
            self.status_var.set("Paused")
        else:
            # FPS = 60Hz tick loop rate estimate; IPS = FPS * 9
            self.status_var.set(f"FPS: {self._fps:5.1f} | IPS: {self._fps * self._ips_per_tick:6.0f}")
        if force:
            self._status_last_t = time.perf_counter()

    def on_key_press(self, event: tk.Event) -> None:
        ks = (event.keysym or "").lower()
        if ks == "space":
            self.toggle_pause()
            return

        ch = (event.char or "").lower()
        if ch in self.KEYMAP:
            key = self.KEYMAP[ch]
            self.keys[key] = 1

            # If we're blocked on Fx0A, consume this keypress.
            if self.waiting_for_key:
                self.V[self.wait_reg] = key
                self.waiting_for_key = False
                # Advance PC past the waiting instruction (we rewound it)
                self.pc = (self.pc + 2) & 0x0FFF

    def on_key_release(self, event: tk.Event) -> None:
        ch = (event.char or "").lower()
        if ch in self.KEYMAP:
            self.keys[self.KEYMAP[ch]] = 0


def main():
    WIN_W, WIN_H = 600, 400
    TOP_H = 40
    CANVAS_H = WIN_H - TOP_H

    root = tk.Tk()
    root.title("CHIP-8 (Tkinter) — 600×400")
    root.geometry(f"{WIN_W}x{WIN_H}")
    root.minsize(WIN_W, WIN_H)
    root.maxsize(WIN_W, WIN_H)
    root.resizable(False, False)
    root.configure(bg="black")

    # Top bar
    top = tk.Frame(root, bg="black", height=TOP_H)
    top.pack(side="top", fill="x")
    top.pack_propagate(False)

    # Display canvas (black background)
    canvas = tk.Canvas(root, width=WIN_W, height=CANVAS_H, bg="black", highlightthickness=0)
    canvas.pack(side="top", fill="both", expand=False)

    status_var = tk.StringVar(value="Paused")

    # Instantiate emulator
    emu = Chip8(root, canvas, status_var, display_scale=9)

    # Top bar widgets
    load_btn = tk.Button(
        top,
        text="Load ROM",
        command=emu.load_rom_via_dialog,
        bg="#202020",
        fg="#00ff00",
        activebackground="#303030",
        activeforeground="#00ff00",
        relief="flat",
        padx=12,
        pady=4,
    )
    load_btn.pack(side="left", padx=10, pady=6)

    status_lbl = tk.Label(
        top,
        textvariable=status_var,
        bg="black",
        fg="#00ff00",
        anchor="w",
        font=("TkFixedFont", 11),
    )
    status_lbl.pack(side="left", padx=10)

    # Input bindings
    root.bind("<KeyPress>", emu.on_key_press)
    root.bind("<KeyRelease>", emu.on_key_release)

    # Graceful close
    def on_close():
        emu.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Start ticking
    emu.start()

    root.mainloop()


if __name__ == "__main__":
    main()
