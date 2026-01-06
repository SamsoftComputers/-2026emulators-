import tkinter as tk
from tkinter import filedialog
import time

# --- BACKEND ENGINES ---

class GBMMU:
    """Memory Management Unit: Handles reading/writing to specific memory addresses."""
    def __init__(self):
        self.rom = bytearray([0] * 0x8000)  # 32k ROM placeholder
        self.vram = bytearray([0] * 0x2000) # 8k Video RAM
        self.wram = bytearray([0] * 0x2000) # 8k Working RAM
        self.hram = bytearray([0] * 0x80)   # High RAM (Zero Page)
        self.boot_rom_finished = True       # Skip boot ROM for now

    def load_rom(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                # Load ROM into memory (max 32k for this simple implementation)
                self.rom[:len(data)] = data
                return True
        except Exception as e:
            print(f"Error loading ROM: {e}")
            return False

    def read(self, address):
        # Memory Map of the Gameboy
        if 0x0000 <= address <= 0x7FFF: # ROM Bank 0 & Switchable
            return self.rom[address]
        elif 0x8000 <= address <= 0x9FFF: # VRAM
            return self.vram[address - 0x8000]
        elif 0xA000 <= address <= 0xBFFF: # External RAM
            return 0xFF # Not implemented
        elif 0xC000 <= address <= 0xDFFF: # Work RAM
            return self.wram[address - 0xC000]
        elif 0xFF80 <= address <= 0xFFFE: # HRAM
            return self.hram[address - 0xFF80]
        else:
            return 0x00 # Unmapped/IO ignored for now

    def write(self, address, value):
        # Prevent writing to ROM (0x0000 - 0x7FFF)
        if 0x8000 <= address <= 0x9FFF:
            self.vram[address - 0x8000] = value
        elif 0xC000 <= address <= 0xDFFF:
            self.wram[address - 0xC000] = value
        elif 0xFF80 <= address <= 0xFFFE:
            self.hram[address - 0xFF80] = value
        # Note: IO Registers (0xFF00) and Interrupts need to be handled here

class GBCPU:
    """The LR35902 CPU (Z80-ish)"""
    def __init__(self, mmu):
        self.mmu = mmu
        
        # Registers: 8-bit
        self.a = 0
        self.f = 0 # Flags: Z N H C
        self.b = 0
        self.c = 0
        self.d = 0
        self.e = 0
        self.h = 0
        self.l = 0
        
        # 16-bit Registers
        self.sp = 0xFFFE # Stack Pointer
        self.pc = 0x0100 # Program Counter (Entry point for cartridges)

        # Helper to combine 8-bit regs into 16-bit
        self.flags = {'Z': 0x80, 'N': 0x40, 'H': 0x20, 'C': 0x10}

    def step(self):
        """Execute one instruction"""
        # 1. FETCH
        opcode = self.mmu.read(self.pc)
        self.pc += 1
        self.pc &= 0xFFFF # Keep it 16-bit

        # 2. DECODE & EXECUTE
        # In a real emulator, this is a massive table of 256 opcodes.
        # Here are a few examples to prove the engine works.
        
        if opcode == 0x00: # NOP (No Operation)
            return 4 # Cycles

        elif opcode == 0xC3: # JP a16 (Jump to address)
            low = self.mmu.read(self.pc)
            high = self.mmu.read(self.pc + 1)
            self.pc = (high << 8) | low
            return 16 # Cycles
            
        elif opcode == 0x3E: # LD A, d8 (Load immediate 8-bit into A)
            val = self.mmu.read(self.pc)
            self.a = val
            self.pc += 1
            return 8

        else:
            # print(f"Unknown Opcode: {hex(opcode)} at {hex(self.pc-1)}")
            return 4 # Pretend we did something

# --- FRONTEND UI ---

class GameboyEmulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Cat's Emulator")
        self.root.geometry("600x500") # Increased height slightly
        self.root.configure(bg="#2c3e50")
        self.root.resizable(False, False)

        # Initialize Backend
        self.mmu = GBMMU()
        self.cpu = GBCPU(self.mmu)

        # Emulator State
        self.rom_loaded = False
        self.running = False
        self.paused = False
        
        # Screen Scaling
        self.scale_factor = 2
        self.screen_width = 160 * self.scale_factor
        self.screen_height = 144 * self.scale_factor

        self.setup_ui()
        self.setup_menu()
        
        # Start the emulation loop
        self.root.after(16, self.emulation_loop)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Screen
        screen_frame = tk.Frame(main_frame, bg="#34495e", bd=5, relief="ridge")
        screen_frame.pack(side="top", pady=(0, 20))

        self.canvas = tk.Canvas(
            screen_frame, 
            width=self.screen_width, 
            height=self.screen_height, 
            bg="#9bbc0f",
            highlightthickness=0
        )
        self.canvas.pack()
        
        self.status_text = self.canvas.create_text(
            self.screen_width//2, 
            self.screen_height//2, 
            text="NO ROM LOADED", 
            fill="#0f380f", 
            font=("Courier", 14, "bold")
        )

        # Debug Info Panel (New!)
        self.debug_label = tk.Label(main_frame, text="PC: 0x0000 | OP: 0x00", bg="#2c3e50", fg="#ecf0f1", font=("Courier", 10))
        self.debug_label.pack(side="top", pady=5)

        # Controls
        controls_frame = tk.Frame(main_frame, bg="#2c3e50")
        controls_frame.pack(side="bottom", fill="x")

        # D-Pad
        dpad_frame = tk.Frame(controls_frame, bg="#2c3e50")
        dpad_frame.pack(side="left", padx=30)
        self.create_dpad(dpad_frame)

        # Start/Select
        options_frame = tk.Frame(controls_frame, bg="#2c3e50")
        options_frame.pack(side="left", padx=20, pady=(20, 0))
        self.create_button(options_frame, "SELECT", "Select", "#7f8c8d", 8, 2)
        self.create_button(options_frame, "START", "Start", "#7f8c8d", 8, 2)

        # A/B
        action_frame = tk.Frame(controls_frame, bg="#2c3e50")
        action_frame.pack(side="right", padx=30)
        self.create_button(action_frame, "B", "B", "#c0392b", 40, 40, shape="oval")
        tk.Label(action_frame, bg="#2c3e50").pack(side="left", padx=5)
        self.create_button(action_frame, "A", "A", "#c0392b", 40, 40, shape="oval")

    def create_dpad(self, parent):
        btn_color = "#34495e"
        arrow_color = "#ecf0f1"
        
        tk.Button(parent, text="▲", bg=btn_color, fg=arrow_color, width=3, command=lambda: self.handle_input("UP")).grid(row=0, column=1)
        tk.Button(parent, text="◀", bg=btn_color, fg=arrow_color, width=3, command=lambda: self.handle_input("LEFT")).grid(row=1, column=0)
        tk.Frame(parent, width=20, height=20, bg="#2c3e50").grid(row=1, column=1)
        tk.Button(parent, text="▶", bg=btn_color, fg=arrow_color, width=3, command=lambda: self.handle_input("RIGHT")).grid(row=1, column=2)
        tk.Button(parent, text="▼", bg=btn_color, fg=arrow_color, width=3, command=lambda: self.handle_input("DOWN")).grid(row=2, column=1)

        self.root.bind('<Up>', lambda e: self.handle_input("UP"))
        self.root.bind('<Down>', lambda e: self.handle_input("DOWN"))
        self.root.bind('<Left>', lambda e: self.handle_input("LEFT"))
        self.root.bind('<Right>', lambda e: self.handle_input("RIGHT"))

    def create_button(self, parent, text, key_map, color, w, h, shape="rect"):
        if shape == "oval":
            btn = tk.Canvas(parent, width=w, height=h, bg="#2c3e50", highlightthickness=0)
            btn.create_oval(2, 2, w-2, h-2, fill=color, outline="#2c3e50")
            btn.create_text(w//2, h//2, text=text, fill="white", font=("Arial", 10, "bold"))
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e: self.handle_input(key_map))
        else:
            btn = tk.Button(parent, text=text, bg=color, fg="white", width=w, height=1, font=("Arial", 8), command=lambda: self.handle_input(key_map))
            btn.pack(side="left", padx=5)

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load ROM", command=self.load_rom)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        emulation_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Emulation", menu=emulation_menu)
        emulation_menu.add_command(label="Pause/Resume", command=self.toggle_pause)
        emulation_menu.add_command(label="Reset", command=self.reset_emulator)

    def get_rom_title(self):
        """Extracts the game title from the ROM header (0x0134-0x0143)"""
        title_bytes = self.mmu.rom[0x0134:0x0143]
        try:
            return title_bytes.decode("utf-8").strip()
        except:
            return "UNKNOWN"

    def load_rom(self):
        file_path = filedialog.askopenfilename(filetypes=[("Gameboy ROM", "*.gb"), ("All Files", "*.*")])
        if file_path:
            success = self.mmu.load_rom(file_path)
            if success:
                self.rom_loaded = True
                self.running = True
                self.cpu.pc = 0x0100 # Reset PC to start of ROM
                
                # UI Updates
                self.canvas.delete(self.status_text)
                self.canvas.configure(bg="#000000") 
                
                title = self.get_rom_title()
                self.root.title(f"Cat's Emulator - Playing: {title}")
                print(f"Loaded ROM: {title}")
            
    def toggle_pause(self):
        self.paused = not self.paused
        print("PAUSED" if self.paused else "RESUMED")

    def reset_emulator(self):
        self.running = False
        self.rom_loaded = False
        self.canvas.delete("all")
        self.canvas.configure(bg="#9bbc0f")
        self.status_text = self.canvas.create_text(
            self.screen_width//2, self.screen_height//2, 
            text="NO ROM LOADED", fill="#0f380f", font=("Courier", 14, "bold")
        )
        self.cpu.pc = 0x0100
        self.root.title("Cat's Emulator")

    def handle_input(self, key):
        # In a real emulator, this writes to 0xFF00 (Joypad Register)
        print(f"Input: {key}")

    def emulation_loop(self):
        if self.running and not self.paused:
            # Gameboy runs at 4.19 MHz. 
            # 60 FPS means ~70,224 cycles per frame.
            # Python is slow, so let's try to run a smaller batch per UI update.
            
            cycles_this_frame = 0
            MAX_CYCLES = 1000 # Increase this as you optimize
            
            try:
                while cycles_this_frame < MAX_CYCLES:
                    cycles = self.cpu.step()
                    cycles_this_frame += cycles
            except Exception as e:
                print(f"Crash at PC:{hex(self.cpu.pc)} - {e}")
                self.paused = True

            # Update Debug Text
            self.debug_label.config(text=f"PC: {hex(self.cpu.pc)} | Reg A: {hex(self.cpu.a)}")

        self.root.after(16, self.emulation_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameboyEmulator(root)
    root.mainloop()