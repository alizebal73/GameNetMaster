#!/usr/bin/env python
"""
GameNetMaster Auto Login Module
-------------------------------
This module provides functions to enable automatic login to Windows
on client computers managed by GameNetMaster.
"""

import os
import sys
import logging
import winreg
import ctypes
from ctypes import wintypes

# Setup logging
logger = logging.getLogger("GameNetClient.AutoLogin")

# Define required Win32 constants
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002
SMTO_NORMAL = 0x0000

# Load required DLLs
user32 = ctypes.WinDLL('user32', use_last_error=True)
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)

# Define function prototypes
SendMessageTimeoutW = user32.SendMessageTimeoutW
SendMessageTimeoutW.restype = wintypes.LRESULT
SendMessageTimeoutW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPCWSTR,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(wintypes.DWORD)
]

# Registry paths
WINLOGON_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
AUTOLOGON_KEY = WINLOGON_KEY


def set_auto_logon(username, password, domain=""):
    """
    Configure Windows to automatically log in with the specified credentials.
    
    Args:
        username (str): The Windows username to auto-login with
        password (str): The password for the specified user
        domain (str, optional): The domain if applicable, defaults to empty string
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Open the WinLogon key
        key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, 
            WINLOGON_KEY, 
            0, 
            winreg.KEY_SET_VALUE | winreg.KEY_WRITE
        )
        
        # Set the auto logon settings
        winreg.SetValueEx(key, "AutoAdminLogon", 0, winreg.REG_SZ, "1")
        winreg.SetValueEx(key, "DefaultUsername", 0, winreg.REG_SZ, username)
        winreg.SetValueEx(key, "DefaultPassword", 0, winreg.REG_SZ, password)
        winreg.SetValueEx(key, "DefaultDomainName", 0, winreg.REG_SZ, domain)
        
        # Disable legal notice
        winreg.SetValueEx(key, "LegalNoticeCaption", 0, winreg.REG_SZ, "")
        winreg.SetValueEx(key, "LegalNoticeText", 0, winreg.REG_SZ, "")
        
        # Close the key
        winreg.CloseKey(key)
        
        # Notify the system of the changes
        result = ctypes.c_long()
        SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_NORMAL | SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result)
        )
        
        logger.info(f"Auto logon configured for user: {username}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting auto logon: {e}")
        return False


def disable_auto_logon():
    """
    Disable automatic logon that was previously configured.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Open the WinLogon key
        key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, 
            WINLOGON_KEY, 
            0, 
            winreg.KEY_SET_VALUE | winreg.KEY_WRITE
        )
        
        # Set auto logon to 0 (disabled)
        winreg.SetValueEx(key, "AutoAdminLogon", 0, winreg.REG_SZ, "0")
        
        # Remove sensitive information
        try:
            winreg.DeleteValue(key, "DefaultPassword")
        except FileNotFoundError:
            pass  # Key doesn't exist, continue
            
        # Close the key
        winreg.CloseKey(key)
        
        # Notify the system of the changes
        result = ctypes.c_long()
        SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_NORMAL | SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result)
        )
        
        logger.info("Auto logon disabled")
        return True
        
    except Exception as e:
        logger.error(f"Error disabling auto logon: {e}")
        return False


def is_auto_logon_enabled():
    """
    Check if auto logon is currently enabled.
    
    Returns:
        bool: True if enabled, False otherwise
    """
    try:
        # Open the WinLogon key
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            WINLOGON_KEY, 
            0, 
            winreg.KEY_READ
        )
        
        # Read the AutoAdminLogon value
        value, _ = winreg.QueryValueEx(key, "AutoAdminLogon")
        
        # Close the key
        winreg.CloseKey(key)
        
        return value == "1"
        
    except Exception as e:
        logger.error(f"Error checking auto logon status: {e}")
        return False


def get_current_auto_logon_user():
    """
    Get the username configured for auto logon.
    
    Returns:
        str: Username configured for auto logon, or None if not configured
    """
    try:
        # Open the WinLogon key
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            WINLOGON_KEY, 
            0, 
            winreg.KEY_READ
        )
        
        # Check if auto logon is enabled
        value, _ = winreg.QueryValueEx(key, "AutoAdminLogon")
        if value != "1":
            winreg.CloseKey(key)
            return None
            
        # Get the username
        username, _ = winreg.QueryValueEx(key, "DefaultUsername")
        
        # Close the key
        winreg.CloseKey(key)
        
        return username
        
    except Exception as e:
        logger.error(f"Error getting auto logon username: {e}")
        return None


def is_admin():
    """
    Check if the current process has admin privileges.
    
    Returns:
        bool: True if admin, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def main():
    """
    Main function for testing
    """
    if not is_admin():
        print("Error: This script requires administrator privileges")
        print("Please run as administrator")
        return 1
        
    print("GameNetMaster Auto Login Tool")
    print("=============================")
    
    if is_auto_logon_enabled():
        username = get_current_auto_logon_user()
        print(f"Auto logon is currently ENABLED for user: {username}")
        
        disable = input("Do you want to disable auto logon? (y/n): ")
        if disable.lower() == 'y':
            if disable_auto_logon():
                print("Auto logon disabled successfully")
            else:
                print("Failed to disable auto logon")
    else:
        print("Auto logon is currently DISABLED")
        
        enable = input("Do you want to enable auto logon? (y/n): ")
        if enable.lower() == 'y':
            username = input("Enter username: ")
            password = input("Enter password: ")
            domain = input("Enter domain (leave blank for local accounts): ")
            
            if set_auto_logon(username, password, domain):
                print("Auto logon configured successfully")
            else:
                print("Failed to configure auto logon")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())