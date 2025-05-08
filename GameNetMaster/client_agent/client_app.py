#!/usr/bin/env python
"""
GameNetMaster Client Agent
--------------------------
This lightweight agent runs on Windows clients and communicates with the GameNetMaster server.
It reports status, manages client configuration, and controls game/application launching.

Features:
- Automatic login to Windows
- System monitoring (CPU, RAM, network)
- Status reporting to server
- Game/application launching
- Session tracking
"""

import os
import sys
import time
import json
import logging
import platform
import socket
import uuid
import psutil
import requests
import threading
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.getenv('TEMP', '.'), 'gamenet_client.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GameNetClient")

class GameNetClient:
    """
    Main client application for GameNetMaster
    """
    def __init__(self):
        self.client_id = None
        self.server_url = None
        self.mac_address = self._get_mac_address()
        self.hostname = socket.gethostname()
        self.ip_address = socket.gethostbyname(self.hostname)
        self.is_running = False
        self.auth_token = None
        self.config = {}
        self.stats_thread = None
        self.heartbeat_thread = None
        
        self._load_config()
        logger.info(f"Client initialized: {self.hostname} ({self.ip_address})")

    def _get_mac_address(self):
        """Get the MAC address of the primary network interface"""
        try:
            # Get the MAC address of the first network interface
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                            for elements in range(0, 48, 8)][::-1])
            return mac
        except Exception as e:
            logger.error(f"Error getting MAC address: {e}")
            return "00:00:00:00:00:00"

    def _load_config(self):
        """Load configuration from file or create default if not exists"""
        config_file = os.path.join(os.getenv('PROGRAMDATA', '.'), 'GameNetMaster', 'client_config.json')
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
                    self.server_url = self.config.get('server_url', 'http://localhost:5000')
                    logger.info(f"Loaded configuration from {config_file}")
            else:
                # Create default configuration
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                self.config = {
                    'server_url': 'http://localhost:5000',
                    'auto_login': True,
                    'monitoring_interval': 10,  # seconds
                    'heartbeat_interval': 30,   # seconds
                }
                self.server_url = self.config['server_url']
                
                with open(config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                logger.info(f"Created default configuration at {config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = {
                'server_url': 'http://localhost:5000',
                'auto_login': True,
                'monitoring_interval': 10,
                'heartbeat_interval': 30,
            }
            self.server_url = self.config['server_url']

    def _save_config(self):
        """Save configuration to file"""
        config_file = os.path.join(os.getenv('PROGRAMDATA', '.'), 'GameNetMaster', 'client_config.json')
        try:
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved configuration to {config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def register_with_server(self):
        """Register client with the server"""
        try:
            url = f"{self.server_url}/api/client/register"
            data = {
                'hostname': self.hostname,
                'mac_address': self.mac_address,
                'ip_address': self.ip_address,
                'platform': platform.platform(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'architecture': platform.machine()
            }
            
            logger.info(f"Registering with server: {url}")
            response = requests.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.client_id = result.get('client_id')
                self.auth_token = result.get('auth_token')
                
                # Update config with server-provided settings
                server_config = result.get('config', {})
                self.config.update(server_config)
                self._save_config()
                
                logger.info(f"Successfully registered with server, client_id: {self.client_id}")
                return True
            else:
                logger.error(f"Failed to register with server: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering with server: {e}")
            return False

    def send_heartbeat(self):
        """Send heartbeat to server to indicate client is alive"""
        if not self.auth_token or not self.client_id:
            logger.warning("No auth token or client ID, cannot send heartbeat")
            return False
            
        try:
            url = f"{self.server_url}/api/client/heartbeat"
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            data = {
                'client_id': self.client_id,
                'mac_address': self.mac_address,
                'ip_address': self.ip_address,
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                logger.debug("Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"Failed to send heartbeat: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False

    def collect_and_send_stats(self):
        """Collect system stats and send to server"""
        if not self.auth_token or not self.client_id:
            logger.warning("No auth token or client ID, cannot send stats")
            return False
            
        try:
            # Collect system stats
            cpu_usage = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            memory_usage_mb = memory.used / (1024 * 1024)
            
            # Network stats
            net_io = psutil.net_io_counters()
            network_rx_mbps = net_io.bytes_recv / (1024 * 1024)  # MB
            network_tx_mbps = net_io.bytes_sent / (1024 * 1024)  # MB
            
            # Prepare data
            url = f"{self.server_url}/api/client/stats"
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            data = {
                'client_id': self.client_id,
                'mac_address': self.mac_address,
                'timestamp': datetime.now().isoformat(),
                'cpu_usage': cpu_usage,
                'memory_usage_mb': memory_usage_mb,
                'network_rx_mbps': network_rx_mbps,
                'network_tx_mbps': network_tx_mbps
            }
            
            # Send to server
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                logger.debug("Stats sent successfully")
                return True
            else:
                logger.warning(f"Failed to send stats: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error collecting and sending stats: {e}")
            return False

    def heartbeat_loop(self):
        """Background thread to send periodic heartbeats"""
        logger.info("Starting heartbeat thread")
        while self.is_running:
            try:
                self.send_heartbeat()
                time.sleep(self.config.get('heartbeat_interval', 30))
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(5)  # Short delay on error

    def stats_loop(self):
        """Background thread to collect and send system stats"""
        logger.info("Starting stats collection thread")
        while self.is_running:
            try:
                self.collect_and_send_stats()
                time.sleep(self.config.get('monitoring_interval', 10))
            except Exception as e:
                logger.error(f"Error in stats loop: {e}")
                time.sleep(5)  # Short delay on error

    def handle_commands(self):
        """Process commands received from the server"""
        if not self.auth_token or not self.client_id:
            logger.warning("No auth token or client ID, cannot get commands")
            return
            
        try:
            url = f"{self.server_url}/api/client/commands"
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            params = {'client_id': self.client_id}
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                commands = response.json().get('commands', [])
                
                for cmd in commands:
                    cmd_type = cmd.get('type')
                    cmd_data = cmd.get('data', {})
                    
                    logger.info(f"Received command: {cmd_type}")
                    
                    if cmd_type == 'reboot':
                        # Execute reboot
                        os.system('shutdown /r /t 5 /c "GameNetMaster reboot command received"')
                        
                    elif cmd_type == 'shutdown':
                        # Execute shutdown
                        os.system('shutdown /s /t 5 /c "GameNetMaster shutdown command received"')
                        
                    elif cmd_type == 'launch_app':
                        # Launch application
                        app_path = cmd_data.get('app_path')
                        if app_path and os.path.exists(app_path):
                            os.startfile(app_path)
                        else:
                            logger.error(f"Application not found: {app_path}")
                    
                    elif cmd_type == 'update_config':
                        # Update configuration
                        self.config.update(cmd_data)
                        self._save_config()
                        
                    # Acknowledge command processing
                    self._acknowledge_command(cmd.get('id'))
            
        except Exception as e:
            logger.error(f"Error handling commands: {e}")

    def _acknowledge_command(self, command_id):
        """Acknowledge command processing to the server"""
        if not command_id:
            return
            
        try:
            url = f"{self.server_url}/api/client/commands/{command_id}/ack"
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            data = {'client_id': self.client_id}
            
            requests.post(url, json=data, headers=headers)
        except Exception as e:
            logger.error(f"Error acknowledging command: {e}")

    def start(self):
        """Start the client agent"""
        logger.info("Starting GameNetMaster client agent")
        
        # Register with server
        if not self.register_with_server():
            logger.error("Failed to register with server, retrying in 30 seconds...")
            time.sleep(30)
            if not self.register_with_server():
                logger.error("Failed to register with server again, giving up")
                return False
        
        self.is_running = True
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        # Start stats collection thread
        self.stats_thread = threading.Thread(target=self.stats_loop)
        self.stats_thread.daemon = True
        self.stats_thread.start()
        
        logger.info("Client agent started successfully")
        return True

    def stop(self):
        """Stop the client agent"""
        logger.info("Stopping GameNetMaster client agent")
        self.is_running = False
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=2)
            
        if self.stats_thread:
            self.stats_thread.join(timeout=2)
            
        logger.info("Client agent stopped")

    def run(self):
        """Main run loop"""
        if not self.start():
            return
            
        try:
            while self.is_running:
                # Handle any commands from the server
                self.handle_commands()
                
                # Sleep for a bit to avoid busy looping
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self.stop()


if __name__ == "__main__":
    print("GameNetMaster Client Agent")
    print("==========================")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print()
    
    try:
        client = GameNetClient()
        client.run()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"Error: {e}")
        sys.exit(1)