import os
import socket
import threading
import logging
import time
import struct
import ipaddress
from datetime import datetime

logger = logging.getLogger(__name__)

class PXEServer:
    """
    PXE Server implementation that provides TFTP and optionally DHCP services
    for booting clients over the network.
    
    This is a simplified implementation for demonstration purposes.
    In a production environment, you would use established TFTP/DHCP servers.
    """
    
    def __init__(self, interface='eth0', tftp_root='/tmp/tftp', 
                 dhcp_enabled=True, subnet='192.168.1.0/24', 
                 gateway='192.168.1.1', dns_server='8.8.8.8'):
        self.interface = interface
        self.tftp_root = tftp_root
        self.dhcp_enabled = dhcp_enabled
        self.subnet = subnet
        self.gateway = gateway
        self.dns_server = dns_server
        
        self.tftp_server = None
        self.dhcp_server = None
        self.running = False
        
        # Ensure TFTP root directory exists
        os.makedirs(self.tftp_root, exist_ok=True)
        
        # Generate boot files
        self._generate_boot_files()
    
    def _generate_boot_files(self):
        """Generate PXE boot files in the TFTP root directory"""
        # Create pxelinux.cfg directory
        pxelinux_cfg_dir = os.path.join(self.tftp_root, 'pxelinux.cfg')
        os.makedirs(pxelinux_cfg_dir, exist_ok=True)
        
        # Write default configuration file
        default_cfg_path = os.path.join(pxelinux_cfg_dir, 'default')
        with open(default_cfg_path, 'w') as f:
            f.write("""DEFAULT winpe
LABEL winpe
    KERNEL /winpe/boot/pxeboot.com
    APPEND /winpe/Boot/BCD /winpe/Boot/boot.sdi /winpe/sources/boot.wim
""")
        
        logger.info(f"Generated PXE boot files in {self.tftp_root}")
    
    def start_tftp_server(self):
        """Start a simple TFTP server for PXE boot"""
        tftp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tftp_sock.bind(('0.0.0.0', 69))  # TFTP port
        
        logger.info("TFTP server started on port 69")
        
        while self.running:
            try:
                data, addr = tftp_sock.recvfrom(512)
                # In a real implementation, we would handle TFTP requests here
                # This is just a placeholder for the demo
                logger.debug(f"Received TFTP request from {addr}")
            except Exception as e:
                logger.error(f"TFTP server error: {e}")
                time.sleep(1)
    
    def start_dhcp_server(self):
        """Start a simple DHCP server for PXE boot"""
        if not self.dhcp_enabled:
            return
        
        dhcp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dhcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        dhcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        dhcp_sock.bind(('0.0.0.0', 67))  # DHCP server port
        
        logger.info("DHCP server started on port 67")
        
        # Get IP range from subnet
        subnet_obj = ipaddress.ip_network(self.subnet)
        available_ips = list(subnet_obj.hosts())[10:50]  # Use a subset of IPs
        
        while self.running:
            try:
                data, addr = dhcp_sock.recvfrom(1024)
                # In a real implementation, we would handle DHCP requests here
                # This is just a placeholder for the demo
                logger.debug(f"Received DHCP request from {addr}")
            except Exception as e:
                logger.error(f"DHCP server error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start both TFTP and DHCP servers in separate threads"""
        if self.running:
            logger.warning("PXE server is already running")
            return
        
        self.running = True
        
        # Start TFTP server in a thread
        self.tftp_server = threading.Thread(target=self.start_tftp_server)
        self.tftp_server.daemon = True
        self.tftp_server.start()
        
        # Start DHCP server in a thread if enabled
        if self.dhcp_enabled:
            self.dhcp_server = threading.Thread(target=self.start_dhcp_server)
            self.dhcp_server.daemon = True
            self.dhcp_server.start()
        
        logger.info(f"PXE server started on interface {self.interface}")
    
    def stop(self):
        """Stop the PXE server"""
        if not self.running:
            logger.warning("PXE server is not running")
            return
        
        self.running = False
        
        # Wait for threads to terminate
        if self.tftp_server and self.tftp_server.is_alive():
            self.tftp_server.join(2)
        
        if self.dhcp_server and self.dhcp_server.is_alive():
            self.dhcp_server.join(2)
        
        logger.info("PXE server stopped")

    def status(self):
        """Return the current status of the PXE server"""
        return {
            'running': self.running,
            'interface': self.interface,
            'tftp_root': self.tftp_root,
            'dhcp_enabled': self.dhcp_enabled,
            'subnet': self.subnet,
            'gateway': self.gateway,
            'dns_server': self.dns_server,
            'start_time': self.start_time if hasattr(self, 'start_time') else None
        }
