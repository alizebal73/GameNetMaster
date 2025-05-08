#!/usr/bin/env python
"""
GameNetMaster Client Installer
-----------------------------
This script installs the GameNetMaster client agent on Windows client machines.
It sets up auto-start, creates desktop shortcuts, and configures the agent.
"""

import os
import sys
import shutil
import logging
import argparse
import subprocess
import winreg
import ctypes
import json
from pathlib import Path
import urllib.request
from zipfile import ZipFile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gamenet_install.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Install")

# Constants
INSTALL_DIR = os.path.join(os.getenv('PROGRAMFILES'), 'GameNetMaster')
DATA_DIR = os.path.join(os.getenv('PROGRAMDATA'), 'GameNetMaster')
AUTOSTART_NAME = "GameNetMaster Client"


def check_admin():
    """Check if script is running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def create_directories():
    """Create the installation directories"""
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info(f"Created installation directories: {INSTALL_DIR} and {DATA_DIR}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
        return False


def copy_files():
    """Copy the client agent files to the installation directory"""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Copy the client application files
        files_to_copy = [
            'client_app.py',
            'auto_login.py',
        ]
        
        for file in files_to_copy:
            source = os.path.join(script_dir, file)
            dest = os.path.join(INSTALL_DIR, file)
            shutil.copy2(source, dest)
            logger.info(f"Copied {file} to {dest}")
        
        # Create a launcher batch file
        with open(os.path.join(INSTALL_DIR, 'start_client.bat'), 'w') as f:
            f.write('@echo off\n')
            f.write('cd /d "%~dp0"\n')
            f.write('pythonw.exe client_app.py\n')
        
        logger.info("Created start_client.bat launcher")
        return True
    except Exception as e:
        logger.error(f"Failed to copy files: {e}")
        return False


def add_to_startup():
    """Add the client agent to Windows startup"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        
        launcher_path = os.path.join(INSTALL_DIR, 'start_client.bat')
        winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, launcher_path)
        winreg.CloseKey(key)
        
        logger.info(f"Added {AUTOSTART_NAME} to startup")
        return True
    except Exception as e:
        logger.error(f"Failed to add to startup: {e}")
        return False


def create_desktop_shortcut():
    """Create a desktop shortcut to the client agent"""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, f"{AUTOSTART_NAME}.lnk")
        
        # Use PowerShell to create the shortcut
        ps_command = f'''
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{os.path.join(INSTALL_DIR, 'start_client.bat')}"
        $Shortcut.WorkingDirectory = "{INSTALL_DIR}"
        $Shortcut.Description = "GameNetMaster Client Agent"
        $Shortcut.IconLocation = "%SystemRoot%\\System32\\SHELL32.dll,6"
        $Shortcut.Save()
        '''
        
        # Execute PowerShell command
        subprocess.run(["powershell", "-Command", ps_command], 
                      capture_output=True, text=True, check=True)
        
        logger.info(f"Created desktop shortcut at {shortcut_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create desktop shortcut: {e}")
        return False


def create_config(server_url):
    """Create the client configuration file"""
    try:
        config = {
            'server_url': server_url,
            'auto_login': True,
            'monitoring_interval': 10,  # seconds
            'heartbeat_interval': 30,   # seconds
        }
        
        config_path = os.path.join(DATA_DIR, 'client_config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        logger.info(f"Created configuration at {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create configuration: {e}")
        return False


def check_python():
    """Check if Python is installed and install if not"""
    try:
        # Try to run Python
        result = subprocess.run(
            ["python", "--version"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Python is installed: {result.stdout.strip()}")
            return True
            
        # Python not installed, download and install it
        logger.info("Python not found, downloading...")
        
        # Download Python installer
        python_url = "https://www.python.org/ftp/python/3.10.8/python-3.10.8-amd64.exe"
        installer_path = os.path.join(os.getenv('TEMP'), "python_installer.exe")
        
        urllib.request.urlretrieve(python_url, installer_path)
        logger.info(f"Downloaded Python installer to {installer_path}")
        
        # Install Python silently
        logger.info("Installing Python...")
        subprocess.run([
            installer_path,
            "/quiet",
            "InstallAllUsers=1",
            "PrependPath=1",
            "Include_test=0"
        ], check=True)
        
        logger.info("Python installed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to check/install Python: {e}")
        return False


def install_requirements():
    """Install required Python packages"""
    try:
        requirements = [
            'psutil',
            'requests',
        ]
        
        for package in requirements:
            logger.info(f"Installing {package}...")
            result = subprocess.run(
                ["pip", "install", package],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install {package}: {result.stderr}")
                return False
                
        logger.info("Required packages installed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to install requirements: {e}")
        return False


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="GameNetMaster Client Installer")
    parser.add_argument("--server", required=True, help="Server URL (e.g., http://192.168.1.10:5000)")
    args = parser.parse_args()
    
    print("GameNetMaster Client Installer")
    print("==============================")
    print()
    
    # Check for admin privileges
    if not check_admin():
        print("Error: This installer must be run with administrator privileges")
        print("Please right-click the installer and select 'Run as administrator'")
        return 1
    
    # Installation steps
    steps = [
        ("Checking Python installation", check_python),
        ("Creating directories", create_directories),
        ("Copying files", copy_files),
        ("Installing requirements", install_requirements),
        ("Creating configuration", lambda: create_config(args.server)),
        ("Adding to startup", add_to_startup),
        ("Creating desktop shortcut", create_desktop_shortcut),
    ]
    
    # Execute installation steps
    success = True
    for step_name, step_func in steps:
        print(f"- {step_name}...")
        if step_func():
            print("  Success!")
        else:
            print("  Failed.")
            success = False
            break
    
    if success:
        print("\nInstallation completed successfully!")
        print(f"GameNetMaster client has been installed to: {INSTALL_DIR}")
        print("The client will start automatically when you restart your computer.")
        print("You can also start it manually using the desktop shortcut.")
    else:
        print("\nInstallation failed. Please check the log file for details.")
        print("Log file: gamenet_install.log")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())