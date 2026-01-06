import time
import random
import tkinter as tk
from tkinter import filedialog, messagebox
import sys

# Constants
SCALE = 10  # 64*10=640 wide
SCR_W, SCR_H = 64, 32
WIN_W, WIN_H = SCR_W * SCALE, SCR_H * SCALE
TIMER_HZ = 60

# Key mapping for a standard QWERTY keyboard to CHIP-8 hex keypad
KEYMAP = {
    '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
    'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
    'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
    'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
}

# Standard CHIP-8 Fontset
FONTSET = [
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
    0xF0, 0x80, 0xF0, 0x80, 0x80   # F
]

class Chip8:
    def __init__(self):
        self.mem = [0] * 4096
        # Load fontset into memory
        for i, b in enumerate(FONTSET):
            self.mem[i] = b
            
        self.V = [0] * 16
        self.I = 0
        self.pc = 0x200
        self.sp = 0
        self.stack = [0] * 16
        self.delay = 0
        self.sound = 0
        self.draw_flag = False
        self.gfx = [0] * (SCR_W * SCR_H)
        self.keys = [0] * 16
        self.rng = random.Random()

    def load_rom(self, data: bytes):
        # Clear memory > 0x200 just in case
        for i in range(0x200, 4096):
            self.mem[i] = 0
            
        for i, b in enumerate(data):
            if 0x200 + i < 4096:
                self.mem[0x200 + i] = b

    def cycle(self):
        # Fetch
        opcode = (self.mem[self.pc] << 8) | self.mem[self.pc + 1]
        self.pc += 2
        
        # Decode
        nnn = opcode & 0x0FFF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0xF
        y = (opcode >> 4) & 0xF
        kk = opcode & 0x00FF

        # Execute
        if opcode == 0x00E0:  # CLS
            self.gfx = [0] * (SCR_W * SCR_H)
            self.draw_flag = True
        elif opcode == 0x00EE:  # RET
            self.sp -= 1
            self.pc = self.stack[self.sp]
        elif opcode & 0xF000 == 0x1000:  # JP addr
            self.pc = nnn
        elif opcode & 0xF000 == 0x2000:  # CALL addr
            self.stack[self.sp] = self.pc
            self.sp += 1
            self.pc = nnn
        elif opcode & 0xF000 == 0x3000:  # SE Vx, byte
            if self.V[x] == kk:
                self.pc += 2
        elif opcode & 0xF000 == 0x4000:  # SNE Vx, byte
            if self.V[x] != kk:
                self.pc += 2
        elif opcode & 0xF00F == 0x5000:  # SE Vx, Vy
            if self.V[x] == self.V[y]:
                self.pc += 2
        elif opcode & 0xF000 == 0x6000:  # LD Vx, byte
            self.V[x] = kk
        elif opcode & 0xF000 == 0x7000:  # ADD Vx, byte
            self.V[x] = (self.V[x] + kk) & 0xFF
        elif opcode & 0xF00F == 0x8000:  # LD Vx, Vy
            self.V[x] = self.V[y]
        elif opcode & 0xF00F == 0x8001:  # OR
            self.V[x] |= self.V[y]
        elif opcode & 0xF00F == 0x8002:  # AND
            self.V[x] &= self.V[y]
        elif opcode & 0xF00F == 0x8003:  # XOR
            self.V[x] ^= self.V[y]
        elif opcode & 0xF00F == 0x8004:  # ADD (carry)
            s = self.V[x] + self.V[y]
            self.V[0xF] = 1 if s > 0xFF else 0
            self.V[x] = s & 0xFF
        elif opcode & 0xF00F == 0x8005:  # SUB
            self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
        elif opcode & 0xF00F == 0x8006:  # SHR
            self.V[0xF] = self.V[x] & 1
            self.V[x] = (self.V[x] >> 1) & 0xFF
        elif opcode & 0xF00F == 0x8007:  # SUBN
            self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
        elif opcode & 0xF00F == 0x800E:  # SHL
            self.V[0xF] = (self.V[x] >> 7) & 1
            self.V[x] = (self.V[x] << 1) & 0xFF
        elif opcode & 0xF00F == 0x9000:  # SNE Vx, Vy
            if self.V[x] != self.V[y]:
                self.pc += 2
        elif opcode & 0xF000 == 0xA000:  # LD I, addr
            self.I = nnn
        elif opcode & 0xF000 == 0xB000:  # JP V0, addr
            self.pc = nnn + self.V[0]
        elif opcode & 0xF000 == 0xC000:  # RND Vx, byte
            self.V[x] = self.rng.randrange(256) & kk
        elif opcode & 0xF000 == 0xD000:  # DRW Vx, Vy, nibble
            vx = self.V[x]
            vy = self.V[y]
            self.V[0xF] = 0
            for row in range(n):
                sprite_byte = self.mem[self.I + row]
                for col in range(8):
                    if (sprite_byte & (0x80 >> col)) != 0:
                        X = (vx + col) % SCR_W
                        Y = (vy + row) % SCR_H
                        idx = Y * SCR_W + X
                        if self.gfx[idx] == 1:
                            self.V[0xF] = 1
                        self.gfx[idx] ^= 1
            self.draw_flag = True
        elif opcode & 0xF0FF == 0xE09E:  # SKP Vx
            if self.keys[self.V[x] & 0xF]:
                self.pc += 2
        elif opcode & 0xF0FF == 0xE0A1:  # SKNP Vx
            if not self.keys[self.V[x] & 0xF]:
                self.pc += 2
        elif opcode & 0xF0FF == 0xF007:  # LD Vx, DT
            self.V[x] = self.delay
        elif opcode & 0xF0FF == 0xF00A:  # LD Vx, K (wait for key)
            pressed = next((i for i, v in enumerate(self.keys) if v), None)
            if pressed is None:
                self.pc -= 2  # Repeat instruction until key press
            else:
                self.V[x] = pressed
        elif opcode & 0xF0FF == 0xF015:  # LD DT, Vx
            self.delay = self.V[x]
        elif opcode & 0xF0FF == 0xF018:  # LD ST, Vx
            self.sound = self.V[x]
        elif opcode & 0xF0FF == 0xF01E:  # ADD I, Vx
            self.I = (self.I + self.V[x]) & 0xFFF
        elif opcode & 0xF0FF == 0xF029:  # LD F, Vx
            self.I = (self.V[x] & 0xF) * 5
        elif opcode & 0xF0FF == 0xF033:  # BCD
            v = self.V[x]
            self.mem[self.I] = v // 100
            self.mem[self.I + 1] = (v // 10) % 10
            self.mem[self.I + 2] = v % 10
        elif opcode & 0xF0FF == 0xF055:  # LD [I], V0..Vx
            for i in range(x + 1):
                self.mem[self.I + i] = self.V[i]
        elif opcode & 0xF0FF == 0xF065:  # LD V0..Vx, [I]
            for i in range(x + 1):
                self.V[i] = self.mem[self.I + i]
        else:
            print(f"Unknown opcode: {hex(opcode)}")

    def tick_timers(self):
        if self.delay > 0:
            self.delay -= 1
        if self.sound > 0:
            self.sound -= 1


class App:
    def __init__(self):
        self.vm = Chip8()
        self.root = tk.Tk()
        self.root.title("Project64 - Version 1.6")
        
        # Classic Windows 9x/2000 gray background
        self.bg_color = "#d4d0c8"
        self.root.configure(bg=self.bg_color)
        self.root.geometry(f"{WIN_W + 20}x{WIN_H + 60}")
        self.root.resizable(False, False)

        # --- Menu Bar ---
        menubar = tk.Menu(self.root)
        
        # File Menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open ROM...", command=self.load_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="End Emulation", command=self.reset_vm)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        
        # System Menu
        sysmenu = tk.Menu(menubar, tearoff=0)
        sysmenu.add_command(label="Reset", command=self.reset_vm)
        sysmenu.add_command(label="Pause", command=self.toggle_pause)
        sysmenu.add_command(label="Save State", state="disabled")
        sysmenu.add_command(label="Load State", state="disabled")
        menubar.add_cascade(label="System", menu=sysmenu)
        
        # Options Menu
        optmenu = tk.Menu(menubar, tearoff=0)
        optmenu.add_command(label="Configure Graphics Plugin...", state="disabled")
        optmenu.add_command(label="Configure Audio Plugin...", state="disabled")
        optmenu.add_command(label="Configure Controller Plugin...", state="disabled")
        menubar.add_cascade(label="Options", menu=optmenu)
        
        # Help Menu
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About Project64...", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

        # --- Main View ---
        # Frame to hold the canvas with a sunken border
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, bd=2, relief=tk.GROOVE)
        self.main_frame.pack(padx=5, pady=5)

        self.canvas = tk.Canvas(
            self.main_frame, 
            width=WIN_W, 
            height=WIN_H, 
            bg="black", 
            highlightthickness=0
        )
        self.canvas.pack()

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_var.set("Emulation stopped")
        
        self.statusbar = tk.Label(
            self.root, 
            textvariable=self.status_var, 
            bd=1, 
            relief=tk.SUNKEN, 
            anchor=tk.W, 
            bg=self.bg_color,
            font=("MS Sans Serif", 8)
        )
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Pre-create pixel rectangles
        self.pixels = []
        for y in range(SCR_H):
            for x in range(SCR_W):
                x1 = x * SCALE
                y1 = y * SCALE
                x2 = x1 + SCALE
                y2 = y1 + SCALE
                rect = self.canvas.create_rectangle(
                    x1, y1, x2, y2, 
                    outline="", 
                    fill="#000000"
                )
                self.pixels.append(rect)

        self.root.bind("<KeyPress>", self.on_key)
        self.root.bind("<KeyRelease>", self.on_keyup)
        
        self.last_timer = time.time()
        self.running = False
        self.paused = False
        self.fps_counter = 0
        self.last_fps_time = time.time()

    def show_about(self):
        messagebox.showinfo("About Project64", "Project64 Version 1.6\n(CHIP-8 Edition)")

    def toggle_pause(self):
        self.paused = not self.paused
        status = "Paused" if self.paused else "Running"
        self.status_var.set(f"Emulation {status}")

    def reset_vm(self):
        self.vm = Chip8()
        self.running = False
        self.status_var.set("Emulation stopped")
        self.draw_clear()

    def draw_clear(self):
        for px in self.pixels:
            self.canvas.itemconfig(px, fill="#000000")

    def load_dialog(self):
        path = filedialog.askopenfilename(
            title="Open ROM", 
            filetypes=[("CHIP-8 ROMs", "*.ch8"), ("All Files", "*.*")]
        )
        if path:
            try:
                with open(path, "rb") as f:
                    data = f.read()
                    self.vm = Chip8() # Reset VM
                    self.vm.load_rom(data)
                    self.running = True
                    self.paused = False
                    self.status_var.set("Emulation started")
                    if self.running: 
                        pass 
            except Exception as e:
                print(f"Error loading ROM: {e}")
                messagebox.showerror("Error", "Failed to load ROM")

    def on_key(self, e):
        k = KEYMAP.get(e.keysym.lower())
        if k is not None:
            self.vm.keys[k] = 1
        if e.keysym == 'Escape':
            self.root.quit()

    def on_keyup(self, e):
        k = KEYMAP.get(e.keysym.lower())
        if k is not None:
            self.vm.keys[k] = 0

    def draw(self):
        if not self.vm.draw_flag:
            return
        self.vm.draw_flag = False
        for idx, bit in enumerate(self.vm.gfx):
            color = "#00FF00" if bit else "#000000"
            self.canvas.itemconfig(self.pixels[idx], fill=color)

    def loop(self):
        if self.running and not self.paused:
            # Emulate cycles
            for _ in range(10):
                self.vm.cycle()

            now = time.time()
            if now - self.last_timer >= 1.0 / TIMER_HZ:
                self.vm.tick_timers()
                self.last_timer = now
            
            self.draw()

            # FPS Calculation for status bar
            self.fps_counter += 1
            if now - self.last_fps_time >= 1.0:
                fps = self.fps_counter
                self.status_var.set(f"Emulation Running  |  FPS: {fps:.2f}")
                self.fps_counter = 0
                self.last_fps_time = now
            
        self.root.after(16, self.loop)

if __name__ == "__main__":
    app = App()
    app.loop()
    app.root.mainloop()