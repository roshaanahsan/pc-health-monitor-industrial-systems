import subprocess
import ctypes
import serial
import time
from serial.tools import list_ports
import psutil
import os
import threading
from pystray import Icon, MenuItem, Menu
from PIL import Image
import logging
from pathlib import Path
import winshell
import pythoncom
from win32com.client import Dispatch
import pygetwindow as gw
import sys

def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception as e:
        logging.error(f"Error hiding console: {e}")

# Logging setup
logging.basicConfig(filename="system_stats.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Clear the content of the log files
def clear_log_files():
    try:
        # Clear the system_stats.log file
        if os.path.exists("system_stats.log"):
            with open("system_stats.log", "w") as log_file:
                log_file.truncate(0)
                logging.info("Cleared system_stats.log")
        
        # Clear the gpu_log.txt file
        if os.path.exists("gpu_log.txt"):
            with open("gpu_log.txt", "w") as gpu_file:
                gpu_file.truncate(0)
                logging.info("Cleared gpu_log.txt")
    
    except Exception as e:
        logging.error(f"Error clearing log files: {e}")

# Check and terminate processes function
def check_and_terminate_processes():
    current_pid = os.getpid()
    processes_to_check = ["PCHealthMonitor.exe", "GPU-Z.exe"]
    
    for process_name in processes_to_check:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                if proc.info['name'] == process_name:
                    logging.info(f"Terminating {process_name} (PID: {proc.info['pid']})...")
                    proc.terminate()
                    proc.wait()
                    logging.info(f"{process_name} terminated successfully.")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

# Main program logic
if __name__ == "__main__":
    clear_log_files()  # Clear the log files before proceeding
    check_and_terminate_processes()  # Check and terminate if running
    hide_console()  # Hide console window

def add_to_startup():
    try:
        # Get the path to the Startup folder
        startup_folder = winshell.startup()
        
        # Path to the current executable
        current_executable = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        
        # Define the shortcut path in the Startup folder
        shortcut_path = os.path.join(startup_folder, "PCHealthMonitor.lnk")
        
        # Check if the shortcut already exists
        if not Path(shortcut_path).exists():
            logging.info("Adding the application to Windows Startup...")
            pythoncom.CoInitialize()  # Ensure COM library is initialized
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(shortcut_path)
            shortcut.TargetPath = current_executable  # Path to the executable
            shortcut.WorkingDirectory = os.path.dirname(current_executable)  # Set the working directory
            shortcut.IconLocation = current_executable  # Use the executable's icon
            shortcut.Save()
            logging.info("Successfully added to Startup.")
        else:
            logging.info("The application is already in the Windows Startup folder.")
    except Exception as e:
        logging.error(f"Error adding to Startup: {e}")

if __name__ == "__main__":
    # Call the add_to_startup function at the beginning
    add_to_startup()

# Hide console window on Windows
def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception as e:
        logging.error(f"Error hiding console: {e}")

# Setup logging to a file
logging.basicConfig(filename="system_stats.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Automatically detect the Arduino's serial port
def find_arduino():
    ports = list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'CH340' in port.description:
            return port.device
    return None

# Get the correct path to the current executable directory
def get_current_dir_path(file_name):
    """Get the absolute path to a file in the same directory as the executable."""
    return os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)), file_name)

# Start GPU-Z and ensure it logs to the correct directory
def start_gpuz():
    gpuz_path = get_current_dir_path("GPU-Z.exe")  # GPU-Z in the same directory as the executable

    try:
        logging.info("Launching GPU-Z...")
        subprocess.Popen([gpuz_path], cwd=os.path.dirname(gpuz_path))

        time.sleep(2)

        window_title = "GPU-Z"
        for _ in range(20):  # Retry up to 20 times
            for win in gw.getAllWindows():
                if window_title.lower() in win.title.lower():
                    win.minimize()
                    logging.info("Minimized GPU-Z to system tray.")
                    return
            logging.info("GPU-Z window not found yet. Retrying...")
            time.sleep(0.5)

        logging.warning("GPU-Z window not found after retries. Could not minimize.")
    except Exception as e:
        logging.error(f"Error launching GPU-Z: {e}")

# Check if the GPU-Z log file is ready
def is_log_file_ready(log_file_path):
    try:
        logging.info(f"Checking log file at: {log_file_path}")
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r') as f:
                lines = f.readlines()
                if lines and len(lines[-1].split(",")) > 4:
                    return True
        return False
    except Exception as e:
        logging.error(f"Error checking log file: {e}")
        return False

# Get GPU metrics (gTEMP, GPU, gPWR, cTEMP)
def get_gpu_metrics_from_log(log_file_path):
    try:
        with open(log_file_path, 'r') as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1]
                parts = last_line.split(",")
                if len(parts) > 4:
                    gpu_temp = min(round(float(parts[1].strip())), 99)
                    gpu_load = min(round(float(parts[2].strip())), 99)
                    gpu_power = min(round(float(parts[3].strip())), 999)
                    cpu_temp = min(round(float(parts[4].strip())), 99)
                    return (f"gTEMP:{gpu_temp} GPU:{gpu_load}% "
                            f"gPWR:{gpu_power}W cTEMP:{cpu_temp}")
            return "gTEMP:N/A GPU:N/A gPWR:N/A cTEMP:N/A"
    except Exception as e:
        logging.error(f"Error reading GPU log: {e}")
        return "gTEMP:Error GPU:Error gPWR:Error cTEMP:Error"

# Calculate disk utilization (I/O activity percentage)
def calculate_disk_io_utilization(interval=1.0):
    try:
        io_counters_start = psutil.disk_io_counters()
        time.sleep(interval)
        io_counters_end = psutil.disk_io_counters()
        read_ops = io_counters_end.read_count - io_counters_start.read_count
        write_ops = io_counters_end.write_count - io_counters_start.write_count
        ops_total = read_ops + write_ops
        utilization = min(99, max(0, round((ops_total / (interval * 100)) * 100)))
        return utilization
    except Exception as e:
        logging.error(f"Error calculating disk I/O utilization: {e}")
        return 0

# Get dynamic system stats (CPU, RAM, Disk)
def get_dynamic_system_stats():
    try:
        cpu_usage = min(round(psutil.cpu_percent()), 99)
        ram_usage = min(round(psutil.virtual_memory().percent), 99)
        disk_usage = calculate_disk_io_utilization()
        return cpu_usage, ram_usage, disk_usage
    except Exception as e:
        logging.error(f"Error fetching dynamic system stats: {e}")
        return 0, 0, 0

# Get combined system stats (CPU, RAM, DISK, GPU)
def get_system_stats(log_file_path):
    try:
        cpu_usage, ram_usage, disk_usage = get_dynamic_system_stats()
        gpu_metrics = get_gpu_metrics_from_log(log_file_path)
        return f"CPU:{cpu_usage}% RAM:{ram_usage}% DISK:{disk_usage}% {gpu_metrics}"
    except Exception as e:
        logging.error(f"Error fetching system stats: {e}")
        return "CPU:0% RAM:0% DISK:0% GPU:Error"

# Main function for serial communication with Arduino
def run_main_logic():
    try:
        start_gpuz()
        log_file_path = get_current_dir_path("gpu_log.txt")  # Log file in the same directory as the executable
        logging.info("Waiting for GPU-Z to initialize and start updating the log file...")
        time.sleep(5)  # Wait 5 seconds for GPU-Z to start
        while not is_log_file_ready(log_file_path):
            logging.info("Still waiting for the log file to be ready...")
            time.sleep(1)
        logging.info("GPU-Z is ready. Starting to fetch system stats.")
        port = find_arduino()
        if not port:
            logging.error("Arduino not detected. Exiting.")
            return
        baud_rate = 9600
        with serial.Serial(port, baud_rate, timeout=1) as ser:
            logging.info(f"Connected to Arduino on {port}")
            while True:
                stats = get_system_stats(log_file_path)
                logging.info(f"Sending stats: {stats}")
                ser.write((stats + '\n').encode('utf-8'))
                time.sleep(1)
    except Exception as e:
        logging.error(f"Error in main loop: {e}")

# Create system tray icon
def create_icon():
    icon_path = get_current_dir_path("usbicon.ico")
    try:
        icon_image = Image.open(icon_path)

        def on_exit(icon, _):
            logging.info("Exiting...")
            icon.stop()

        menu = Menu(MenuItem("Exit", on_exit))
        icon = Icon("System Stats", icon_image, "System Stats Monitor", menu)
        icon.run()
    except Exception as e:
        logging.error(f"Error setting system tray icon: {e}")

if __name__ == "__main__":
    hide_console()
    threading.Thread(target=run_main_logic, daemon=True).start()
    create_icon()
