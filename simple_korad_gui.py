#!/usr/bin/env python3
"""
Simple GUI for Korad KD3005P Power Supply
Continuously reads voltage and current, provides all control functionality
"""
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
import threading
import time

class KoradGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Korad Power Supply Control")
        self.root.geometry("600x500")

        self.port = None
        self.running = False
        self.monitor_thread = None

        # Create GUI
        self.create_widgets()

        # Start port selection
        self.select_port()

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Display area for continuous readings
        display_frame = ttk.LabelFrame(main_frame, text="Current Readings", padding="10")
        display_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        self.voltage_display = tk.StringVar(value="Voltage: ---.-- V")
        self.current_display = tk.StringVar(value="Current: -.--- A")
        self.status_display = tk.StringVar(value="Status: Not Connected")

        # Power indicator canvas
        self.power_canvas = tk.Canvas(display_frame, width=70, height=70, bg="white", highlightthickness=0)
        self.power_canvas.grid(row=0, column=1, rowspan=2, padx=20)
        # Create initial safety indicator (checkmark)
        self.power_shapes = []
        self.draw_safety_indicator()

        ttk.Label(display_frame, textvariable=self.voltage_display, font=("Arial", 16, "bold")).grid(row=0, column=0, pady=5, sticky=tk.W)
        ttk.Label(display_frame, textvariable=self.current_display, font=("Arial", 16, "bold")).grid(row=1, column=0, pady=5, sticky=tk.W)
        ttk.Label(display_frame, textvariable=self.status_display, font=("Arial", 10)).grid(row=2, column=0, columnspan=2, pady=5)

        # Voltage control
        voltage_frame = ttk.LabelFrame(main_frame, text="Voltage Control", padding="10")
        voltage_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Label(voltage_frame, text="Set Voltage (V):").grid(row=0, column=0, sticky=tk.W)
        self.voltage_entry = ttk.Entry(voltage_frame, width=10)
        self.voltage_entry.grid(row=0, column=1, padx=5)
        ttk.Button(voltage_frame, text="Set", command=self.set_voltage).grid(row=0, column=2, padx=5)

        # Current control
        current_frame = ttk.LabelFrame(main_frame, text="Current Control", padding="10")
        current_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        ttk.Label(current_frame, text="Set Current (A):").grid(row=0, column=0, sticky=tk.W)
        self.current_entry = ttk.Entry(current_frame, width=10)
        self.current_entry.grid(row=0, column=1, padx=5)
        ttk.Button(current_frame, text="Set", command=self.set_current).grid(row=0, column=2, padx=5)

        # Output control
        output_frame = ttk.LabelFrame(main_frame, text="Output Control", padding="10")
        output_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(output_frame, text="Output ON", command=self.output_on).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(output_frame, text="Output OFF", command=self.output_off).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(output_frame, text="OCP ON", command=self.ocp_on).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(output_frame, text="OCP OFF", command=self.ocp_off).grid(row=0, column=3, padx=5, pady=5)

        # Memory presets
        memory_frame = ttk.LabelFrame(main_frame, text="Memory Presets", padding="10")
        memory_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(memory_frame, text="Save:").grid(row=0, column=0, padx=5)
        for i in range(1, 6):
            ttk.Button(memory_frame, text=f"M{i}", width=4, command=lambda m=i: self.save_preset(m)).grid(row=0, column=i, padx=2)

        ttk.Label(memory_frame, text="Recall:").grid(row=1, column=0, padx=5)
        for i in range(1, 6):
            ttk.Button(memory_frame, text=f"M{i}", width=4, command=lambda m=i: self.recall_preset(m)).grid(row=1, column=i, padx=2)

        # Connection controls
        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(control_frame, text="Reconnect", command=self.reconnect).grid(row=0, column=0, padx=5)
        ttk.Button(control_frame, text="Quit", command=self.quit_app).grid(row=0, column=1, padx=5)

    def select_port(self):
        """Show dialog to select COM port"""
        ports = serial.tools.list_ports.comports()
        if not ports:
            self.status_display.set("Status: No serial ports found!")
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select COM Port")
        dialog.geometry("400x200")

        ttk.Label(dialog, text="Select COM Port:", font=("Arial", 12)).pack(pady=10)

        port_var = tk.StringVar()
        port_list = ttk.Combobox(dialog, textvariable=port_var, width=40)
        port_list['values'] = [f"{p.device} - {p.description}" for p in ports]
        port_list.pack(pady=10)

        if ports:
            port_list.current(0)

        def connect():
            selection = port_var.get()
            if selection:
                port_name = selection.split(' - ')[0]
                dialog.destroy()
                self.connect_port(port_name)

        ttk.Button(dialog, text="Connect", command=connect).pack(pady=10)

        # Make dialog modal
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)

    def connect_port(self, port_name):
        """Connect to the selected port"""
        try:
            self.port = serial.Serial(
                port=port_name,
                baudrate=4800,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )

            # Enable DTR and RTS
            self.port.dtr = True
            self.port.rts = True
            time.sleep(0.1)

            # Flush buffers
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()

            self.status_display.set(f"Status: Connected to {port_name}")

            # Start monitoring thread
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

        except Exception as e:
            self.status_display.set(f"Status: Connection Error - {e}")

    def send_command(self, command, response_length=0):
        """Send command and optionally read response"""
        if not self.port or not self.port.is_open:
            return None

        try:
            # Clear buffers
            self.port.reset_input_buffer()

            # Send command with CR+LF
            full_command = command.encode('UTF-8') + b'\r\n'
            self.port.write(full_command)
            self.port.flush()

            if response_length > 0:
                # Wait a bit for response
                time.sleep(0.1)

                # Read response
                response = self.port.read(response_length)
                return response.decode('UTF-8', errors='ignore').strip()

            return True

        except Exception as e:
            print(f"Command error: {e}")
            return None

    def draw_safety_indicator(self):
        """Draw green checkmark for safety (power off)"""
        # Clear existing shapes
        for shape in self.power_shapes:
            self.power_canvas.delete(shape)
        self.power_shapes = []

        # Draw green circle background
        circle = self.power_canvas.create_oval(10, 10, 60, 60, fill="green", outline="darkgreen", width=3)
        self.power_shapes.append(circle)

        # Draw checkmark
        check1 = self.power_canvas.create_line(22, 35, 30, 43, fill="white", width=5, capstyle=tk.ROUND)
        check2 = self.power_canvas.create_line(30, 43, 48, 22, fill="white", width=5, capstyle=tk.ROUND)
        self.power_shapes.extend([check1, check2])

    def draw_danger_indicator(self):
        """Draw red warning triangle for danger (power on)"""
        # Clear existing shapes
        for shape in self.power_shapes:
            self.power_canvas.delete(shape)
        self.power_shapes = []

        # Draw red warning triangle
        triangle = self.power_canvas.create_polygon(
            35, 10,  # top
            60, 55,  # bottom right
            10, 55,  # bottom left
            fill="red", outline="darkred", width=3
        )
        self.power_shapes.append(triangle)

        # Draw exclamation mark
        exclaim_line = self.power_canvas.create_line(35, 22, 35, 40, fill="white", width=4, capstyle=tk.ROUND)
        exclaim_dot = self.power_canvas.create_oval(33, 45, 37, 49, fill="white", outline="white")
        self.power_shapes.extend([exclaim_line, exclaim_dot])

    def update_power_indicator(self, is_on):
        """Update power indicator to show danger or safety"""
        if is_on:
            self.draw_danger_indicator()
        else:
            self.draw_safety_indicator()

    def monitor_loop(self):
        """Continuous monitoring loop running in separate thread"""
        while self.running:
            try:
                # Read output voltage
                voltage = self.send_command('VOUT1?', 6)
                if voltage:
                    self.voltage_display.set(f"Voltage: {voltage} V")

                # Read output current
                current = self.send_command('IOUT1?', 6)
                if current:
                    self.current_display.set(f"Current: {current} A")

                # Check output status
                status = self.send_command('STATUS?', 1)
                if status:
                    # Bit 6 (0x40) indicates output is on
                    status_byte = ord(status[0]) if len(status) > 0 else 0
                    is_output_on = bool(status_byte & 0x40)
                    self.update_power_indicator(is_output_on)

                # Small delay between readings
                time.sleep(0.5)

            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1)

    def set_voltage(self):
        """Set voltage"""
        try:
            voltage = float(self.voltage_entry.get())
            if voltage < 0 or voltage > 30:
                self.status_display.set("Status: Voltage must be between 0 and 30V")
                return

            command = f"VSET1:{voltage:05.2f}"
            self.send_command(command)

        except ValueError:
            self.status_display.set("Status: Invalid voltage value")

    def set_current(self):
        """Set current"""
        try:
            current = float(self.current_entry.get())
            if current < 0 or current > 5:
                self.status_display.set("Status: Current must be between 0 and 5A")
                return

            command = f"ISET1:{current:05.3f}"
            self.send_command(command)

        except ValueError:
            self.status_display.set("Status: Invalid current value")

    def output_on(self):
        """Turn output on"""
        self.send_command('OUT1')

    def output_off(self):
        """Turn output off"""
        self.send_command('OUT0')

    def ocp_on(self):
        """Turn OCP on"""
        self.send_command('OCP1')

    def ocp_off(self):
        """Turn OCP off"""
        self.send_command('OCP0')

    def save_preset(self, preset):
        """Save current settings to memory preset"""
        command = f"SAV{preset}"
        self.send_command(command)

    def recall_preset(self, preset):
        """Recall settings from memory preset"""
        command = f"RCL{preset}"
        self.send_command(command)

    def reconnect(self):
        """Reconnect to port"""
        self.running = False
        if self.port and self.port.is_open:
            self.port.close()
        time.sleep(0.5)
        self.select_port()

    def quit_app(self):
        """Quit application"""
        self.running = False
        if self.port and self.port.is_open:
            self.port.close()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = KoradGUI(root)
    root.mainloop()
