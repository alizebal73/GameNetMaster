#!/usr/bin/env python
"""
GameNetMaster Server Installer
-----------------------------
This script installs the GameNetMaster server components on Linux or Windows.
It sets up directories, installs dependencies, and configures the server.
"""

import os
import sys
import shutil
import subprocess
import argparse
import platform
import logging
from pathlib import Path
import json
import random
import string
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_install.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ServerInstall")

# Constants
if platform.system() == 'Windows':
    INSTALL_DIR = os.path.join(os.getenv('PROGRAMFILES'), 'GameNetMaster')
    DATA_DIR = os.path.join(os.getenv('PROGRAMDATA'), 'GameNetMaster')
    VHD_DIR = os.path.join(DATA_DIR, 'vhd')
    TFTP_DIR = os.path.join(DATA_DIR, 'tftp')
else:  # Linux
    INSTALL_DIR = '/opt/gamenetmaster'
    DATA_DIR = '/var/lib/gamenetmaster'
    VHD_DIR = '/var/lib/gamenetmaster/vhd'
    TFTP_DIR = '/var/lib/gamenetmaster/tftp'

REQUIRED_PACKAGES = [
    'flask',
    'flask_login',
    'flask_sqlalchemy',
    'werkzeug',
    'psutil',
    'netifaces',
    'gunicorn',
    'email-validator',
]


def is_admin():
    """Check if script is running with admin/root privileges"""
    if platform.system() == 'Windows':
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:  # Linux/Unix
        return os.geteuid() == 0


def create_directories():
    """Create the installation directories"""
    try:
        directories = [INSTALL_DIR, DATA_DIR, VHD_DIR, TFTP_DIR]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
        return False


def copy_files():
    """Copy the server files to the installation directory"""
    try:
        # Get source directory (current directory)
        source_dir = os.getcwd()
        
        # Files to copy
        files_to_copy = [
            'app.py',
            'main.py',
            'models.py',
            'routes.py',
            'routes_api.py',
            'translations.py',
            'language_utils.py',
            'network_manager.py',
            'pxe_server.py',
            'vhd_manager.py',
        ]
        
        # Copy files
        for file in files_to_copy:
            source = os.path.join(source_dir, file)
            dest = os.path.join(INSTALL_DIR, file)
            if os.path.exists(source):
                shutil.copy2(source, dest)
                logger.info(f"Copied {file} to {dest}")
            else:
                logger.warning(f"Source file not found: {source}")
        
        # Create empty __init__.py file
        with open(os.path.join(INSTALL_DIR, '__init__.py'), 'w') as f:
            f.write('# GameNetMaster Package\n')
        
        # Copy static and templates directories
        for directory in ['static', 'templates']:
            source_dir_path = os.path.join(source_dir, directory)
            dest_dir_path = os.path.join(INSTALL_DIR, directory)
            
            if os.path.exists(source_dir_path):
                if os.path.exists(dest_dir_path):
                    shutil.rmtree(dest_dir_path)
                shutil.copytree(source_dir_path, dest_dir_path)
                logger.info(f"Copied directory {directory} to {dest_dir_path}")
            else:
                logger.warning(f"Source directory not found: {source_dir_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to copy files: {e}")
        return False


def install_dependencies():
    """Install required Python packages"""
    try:
        for package in REQUIRED_PACKAGES:
            logger.info(f"Installing {package}...")
            
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ["pip", "install", package],
                    capture_output=True,
                    text=True
                )
            else:  # Linux
                result = subprocess.run(
                    ["pip3", "install", package],
                    capture_output=True,
                    text=True
                )
            
            if result.returncode != 0:
                logger.error(f"Failed to install {package}: {result.stderr}")
                return False
        
        logger.info("All dependencies installed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to install dependencies: {e}")
        return False


def generate_secret_key():
    """Generate a random secret key for Flask"""
    chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-='
    return ''.join(random.choice(chars) for _ in range(32))


def configure_server(ip_address, port):
    """Configure the server settings"""
    try:
        # Create environment file
        env_path = os.path.join(INSTALL_DIR, '.env')
        with open(env_path, 'w') as f:
            f.write(f"# GameNetMaster Environment Configuration\n")
            f.write(f"# Created on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"# Flask Configuration\n")
            f.write(f"SESSION_SECRET={generate_secret_key()}\n")
            f.write(f"DATABASE_URL=sqlite:///{os.path.join(DATA_DIR, 'gamemaster.db')}\n")
            f.write(f"FLASK_ENV=production\n")
            f.write(f"\n# Server Configuration\n")
            f.write(f"SERVER_IP={ip_address}\n")
            f.write(f"SERVER_PORT={port}\n")
            f.write(f"\n# Paths\n")
            f.write(f"VHD_STORAGE_DIR={VHD_DIR}\n")
            f.write(f"TFTP_ROOT_DIR={TFTP_DIR}\n")
        
        logger.info(f"Created environment configuration at {env_path}")
        
        # Create network settings file
        network_config = {
            "network_interface": "eth0",
            "subnet": "192.168.1.0/24",
            "gateway": "192.168.1.1",
            "dns_server": "8.8.8.8",
            "tftp_root_dir": TFTP_DIR,
            "vhd_storage_dir": VHD_DIR,
        }
        
        network_config_path = os.path.join(DATA_DIR, 'network_config.json')
        with open(network_config_path, 'w') as f:
            json.dump(network_config, f, indent=2)
        
        logger.info(f"Created network configuration at {network_config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to configure server: {e}")
        return False


def create_service_file():
    """Create a systemd service file for Linux"""
    if platform.system() != 'Linux':
        logger.info("Skipping service file creation on non-Linux system")
        return True
    
    try:
        service_content = """[Unit]
Description=GameNetMaster Server
After=network.target

[Service]
User=root
WorkingDirectory={install_dir}
ExecStart=/usr/bin/gunicorn --bind 0.0.0.0:5000 --workers 3 main:app
Restart=always
RestartSec=5
Environment="PATH=/usr/bin:/usr/local/bin"

[Install]
WantedBy=multi-user.target
""".format(install_dir=INSTALL_DIR)
        
        service_path = '/etc/systemd/system/gamenetmaster.service'
        with open(service_path, 'w') as f:
            f.write(service_content)
        
        logger.info(f"Created systemd service file at {service_path}")
        
        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"])
        logger.info("Reloaded systemd")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create service file: {e}")
        return False


def create_windows_service():
    """Create a Windows service using nssm"""
    if platform.system() != 'Windows':
        logger.info("Skipping Windows service creation on non-Windows system")
        return True
    
    try:
        # Download NSSM if not already present
        nssm_path = os.path.join(INSTALL_DIR, 'nssm.exe')
        if not os.path.exists(nssm_path):
            import urllib.request
            nssm_url = "https://nssm.cc/release/nssm-2.24.zip"
            zip_path = os.path.join(os.getenv('TEMP'), "nssm.zip")
            
            logger.info(f"Downloading NSSM from {nssm_url}")
            urllib.request.urlretrieve(nssm_url, zip_path)
            
            # Extract nssm.exe
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if file.endswith('nssm.exe') and '\\win64\\' in file:
                        with open(nssm_path, 'wb') as f:
                            f.write(zip_ref.read(file))
                        break
            
            logger.info(f"Extracted NSSM to {nssm_path}")
        
        # Create batch file for starting the server
        batch_path = os.path.join(INSTALL_DIR, 'start_server.bat')
        with open(batch_path, 'w') as f:
            f.write('@echo off\n')
            f.write(f'cd /d "{INSTALL_DIR}"\n')
            f.write(f'set FLASK_APP=main.py\n')
            f.write(f'python -m flask run --host=0.0.0.0 --port=5000\n')
        
        logger.info(f"Created start batch file at {batch_path}")
        
        # Install service
        subprocess.run([
            nssm_path, "install", "GameNetMaster", batch_path
        ])
        
        subprocess.run([
            nssm_path, "set", "GameNetMaster", "DisplayName", "GameNetMaster Server"
        ])
        
        subprocess.run([
            nssm_path, "set", "GameNetMaster", "Description", 
            "GameNetMaster VHD and PXE management server"
        ])
        
        logger.info("Installed Windows service 'GameNetMaster'")
        return True
    except Exception as e:
        logger.error(f"Failed to create Windows service: {e}")
        return False


def create_launcher():
    """Create a launcher script/shortcut"""
    try:
        if platform.system() == 'Windows':
            # Create a desktop shortcut
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "GameNetMaster Server.lnk")
            
            # Use PowerShell to create the shortcut
            ps_command = f'''
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "http://localhost:5000"
            $Shortcut.Description = "GameNetMaster Server Dashboard"
            $Shortcut.IconLocation = "%SystemRoot%\\System32\\SHELL32.dll,13"
            $Shortcut.Save()
            '''
            
            # Execute PowerShell command
            subprocess.run(["powershell", "-Command", ps_command], 
                          capture_output=True, text=True, check=True)
            
            logger.info(f"Created desktop shortcut at {shortcut_path}")
        else:
            # Create a launcher script
            launcher_path = '/usr/local/bin/gamenetmaster'
            with open(launcher_path, 'w') as f:
                f.write('#!/bin/bash\n')
                f.write('# GameNetMaster launcher\n')
                f.write(f'cd {INSTALL_DIR}\n')
                f.write('python3 -m gunicorn --bind 0.0.0.0:5000 main:app\n')
            
            # Make executable
            os.chmod(launcher_path, 0o755)
            logger.info(f"Created launcher script at {launcher_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to create launcher: {e}")
        return False


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="GameNetMaster Server Installer")
    parser.add_argument("--ip", default="0.0.0.0", help="IP address to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", default=5000, type=int, help="Port to listen on (default: 5000)")
    parser.add_argument("--no-service", action="store_true", help="Don't create a system service")
    args = parser.parse_args()
    
    print("GameNetMaster Server Installer")
    print("==============================")
    print()
    
    # Check for admin/root privileges
    if not is_admin():
        print("Error: This installer must be run with administrator/root privileges")
        if platform.system() == 'Windows':
            print("Please right-click the installer and select 'Run as administrator'")
        else:
            print("Please run with sudo")
        return 1
    
    # Installation steps
    steps = [
        ("Creating directories", create_directories),
        ("Copying files", copy_files),
        ("Installing dependencies", install_dependencies),
        ("Configuring server", lambda: configure_server(args.ip, args.port)),
        ("Creating launcher", create_launcher),
    ]
    
    # Add service creation step if not disabled
    if not args.no_service:
        if platform.system() == 'Windows':
            steps.append(("Creating Windows service", create_windows_service))
        else:
            steps.append(("Creating systemd service", create_service_file))
    
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
        print(f"GameNetMaster server has been installed to: {INSTALL_DIR}")
        print(f"Data directory: {DATA_DIR}")
        print()
        print("To start the server:")
        if platform.system() == 'Windows':
            print("- The server is installed as a Windows service and will start automatically")
            print("- You can also start it manually from the Services control panel")
            print("- A shortcut has been created on your desktop to access the web interface")
        else:
            print("- Start the service: sudo systemctl start gamenetmaster")
            print("- Enable service on boot: sudo systemctl enable gamenetmaster")
            print("- Access the web interface at: http://localhost:5000")
        print()
        print("Default login credentials:")
        print("- Username: admin")
        print("- Password: admin")
    else:
        print("\nInstallation failed. Please check the log file for details.")
        print("Log file: server_install.log")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())