import os
import subprocess
import logging
import psutil
import socket
import netifaces
import time
import threading
import uuid
import ipaddress
from collections import defaultdict

# For network discovery
try:
    import scapy.all as scapy
except ImportError:
    scapy = None

logger = logging.getLogger(__name__)

class NetworkManager:
    """
    Class for managing network settings and monitoring network traffic
    
    This is a simplified implementation for demonstration purposes.
    """
    
    def __init__(self):
        self.traffic_monitors = {}
        self.traffic_data = defaultdict(lambda: {'rx_bytes': 0, 'tx_bytes': 0, 'rx_speed': 0, 'tx_speed': 0})
        self.monitoring = False
        logger.info("Network Manager initialized")
    
    def get_interfaces(self):
        """
        Get list of available network interfaces
        
        Returns:
            list: List of interface names
        """
        try:
            interfaces = netifaces.interfaces()
            return [iface for iface in interfaces if not iface.startswith('lo')]
        except Exception as e:
            logger.error(f"Failed to get network interfaces: {e}")
            return []
    
    def get_interface_info(self, interface_name):
        """
        Get information about a network interface
        
        Args:
            interface_name (str): Name of the interface
            
        Returns:
            dict: Information about the interface, or None if an error occurred
        """
        try:
            if interface_name not in netifaces.interfaces():
                logger.warning(f"Interface {interface_name} does not exist")
                return None
            
            addresses = netifaces.ifaddresses(interface_name)
            
            info = {
                'name': interface_name,
                'ipv4': None,
                'ipv6': None,
                'mac': None
            }
            
            if netifaces.AF_INET in addresses:
                info['ipv4'] = addresses[netifaces.AF_INET][0]['addr']
            
            if netifaces.AF_INET6 in addresses:
                info['ipv6'] = addresses[netifaces.AF_INET6][0]['addr']
            
            if netifaces.AF_LINK in addresses:
                info['mac'] = addresses[netifaces.AF_LINK][0]['addr']
            
            return info
        except Exception as e:
            logger.error(f"Failed to get information for interface {interface_name}: {e}")
            return None
    
    def get_gateway(self):
        """
        Get default gateway
        
        Returns:
            str: IP address of the default gateway, or None if an error occurred
        """
        try:
            gateways = netifaces.gateways()
            if 'default' in gateways and netifaces.AF_INET in gateways['default']:
                return gateways['default'][netifaces.AF_INET][0]
            return None
        except Exception as e:
            logger.error(f"Failed to get default gateway: {e}")
            return None
    
    def ping(self, host, timeout=1):
        """
        Ping a host to check connectivity
        
        Args:
            host (str): Host to ping
            timeout (int): Timeout in seconds
            
        Returns:
            bool: True if ping was successful, False otherwise
        """
        try:
            # Create a socket connection to check if host is reachable
            socket.create_connection((host, 80), timeout=timeout)
            return True
        except:
            return False
    
    def monitor_traffic(self, interface_name):
        """
        Monitor network traffic on an interface
        
        Args:
            interface_name (str): Name of the interface to monitor
        """
        if interface_name in self.traffic_monitors and self.traffic_monitors[interface_name].is_alive():
            logger.warning(f"Traffic monitoring already active for interface {interface_name}")
            return
        
        self.monitoring = True
        
        def _monitor():
            last_stats = psutil.net_io_counters(pernic=True)[interface_name]
            last_time = time.time()
            
            while self.monitoring:
                try:
                    # Get new stats
                    stats = psutil.net_io_counters(pernic=True)[interface_name]
                    current_time = time.time()
                    time_delta = current_time - last_time
                    
                    # Calculate speed
                    rx_delta = stats.bytes_recv - last_stats.bytes_recv
                    tx_delta = stats.bytes_sent - last_stats.bytes_sent
                    
                    rx_speed = rx_delta / time_delta
                    tx_speed = tx_delta / time_delta
                    
                    # Update traffic data
                    self.traffic_data[interface_name] = {
                        'rx_bytes': stats.bytes_recv,
                        'tx_bytes': stats.bytes_sent,
                        'rx_speed': rx_speed,
                        'tx_speed': tx_speed
                    }
                    
                    # Update last values
                    last_stats = stats
                    last_time = current_time
                    
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error monitoring traffic on interface {interface_name}: {e}")
                    time.sleep(5)
        
        monitor_thread = threading.Thread(target=_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        self.traffic_monitors[interface_name] = monitor_thread
        logger.info(f"Started traffic monitoring for interface {interface_name}")
    
    def stop_monitoring(self, interface_name=None):
        """
        Stop monitoring network traffic
        
        Args:
            interface_name (str, optional): Name of the interface to stop monitoring.
                                          If None, stop monitoring on all interfaces.
        """
        self.monitoring = False
        
        if interface_name:
            if interface_name in self.traffic_monitors and self.traffic_monitors[interface_name].is_alive():
                self.traffic_monitors[interface_name].join(2)
                logger.info(f"Stopped traffic monitoring for interface {interface_name}")
            else:
                logger.warning(f"Traffic monitoring not active for interface {interface_name}")
        else:
            for iface, thread in self.traffic_monitors.items():
                if thread.is_alive():
                    thread.join(2)
            logger.info("Stopped traffic monitoring for all interfaces")
    
    def get_traffic_stats(self, interface_name=None):
        """
        Get network traffic statistics
        
        Args:
            interface_name (str, optional): Name of the interface to get stats for.
                                          If None, get stats for all interfaces.
                                          
        Returns:
            dict: Traffic statistics
        """
        if interface_name:
            if interface_name in self.traffic_data:
                return {interface_name: self.traffic_data[interface_name]}
            else:
                logger.warning(f"No traffic data available for interface {interface_name}")
                return {interface_name: {'rx_bytes': 0, 'tx_bytes': 0, 'rx_speed': 0, 'tx_speed': 0}}
        else:
            return dict(self.traffic_data)
    
    def limit_bandwidth(self, interface_name, download_limit_mbps=None, upload_limit_mbps=None):
        """
        Limit bandwidth on an interface
        
        Args:
            interface_name (str): Name of the interface
            download_limit_mbps (int, optional): Download speed limit in Mbps
            upload_limit_mbps (int, optional): Upload speed limit in Mbps
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # In a real implementation, we would use traffic control (tc) to limit bandwidth
            # For the demo, we'll just log the action
            limits = []
            if download_limit_mbps:
                limits.append(f"download: {download_limit_mbps}Mbps")
            if upload_limit_mbps:
                limits.append(f"upload: {upload_limit_mbps}Mbps")
            
            if limits:
                logger.info(f"Set bandwidth limits on {interface_name}: {', '.join(limits)}")
            else:
                logger.info(f"Removed bandwidth limits on {interface_name}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set bandwidth limits: {e}")
            return False
            
    def discover_clients(self, interface_name, subnet=None):
        """
        Scan the network to discover clients
        
        Args:
            interface_name (str): Name of the interface to use for scanning
            subnet (str, optional): Subnet to scan (e.g. '192.168.1.0/24').
                                  If None, will determine subnet from interface.
                                  
        Returns:
            list: List of dictionaries with client information (IP and MAC addresses)
        """
        try:
            # Ensure we have the specified interface
            if interface_name not in self.get_interfaces():
                logger.error(f"Interface {interface_name} does not exist for client discovery")
                return []
            
            # Get interface info
            interface_info = self.get_interface_info(interface_name)
            if not interface_info or not interface_info['ipv4']:
                logger.error(f"Interface {interface_name} has no IPv4 address")
                return []
            
            # Determine subnet to scan
            if not subnet:
                ipv4 = interface_info['ipv4']
                # Simplistic approach - assuming a /24 subnet
                subnet = ipv4.rsplit('.', 1)[0] + '.0/24'
                logger.info(f"Automatically determined subnet: {subnet}")
            
            # First method: Use ARP ping via scapy (if available)
            if scapy:
                logger.info(f"Scanning network {subnet} on interface {interface_name} using scapy...")
                try:
                    # Create ARP request packet
                    arp_request = scapy.ARP(pdst=subnet)
                    broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
                    arp_request_broadcast = broadcast / arp_request
                    
                    # Send packet and get responses
                    answered_list = scapy.srp(arp_request_broadcast, timeout=3, verbose=0, iface=interface_name)[0]
                    
                    # Process the responses
                    clients = []
                    for sent, received in answered_list:
                        clients.append({'ip': received.psrc, 'mac': received.hwsrc})
                    
                    logger.info(f"Discovered {len(clients)} clients using scapy")
                    return clients
                except Exception as e:
                    logger.warning(f"Scapy scan failed, falling back to alternative method: {e}")
            
            # Alternative method: Use built-in tools
            logger.info(f"Scanning network {subnet} on interface {interface_name} using alternative method...")
            
            # Generate a list of IPs to ping
            network = ipaddress.ip_network(subnet, strict=False)
            
            # We'll use a simpler approach here - ping a range of IPs
            clients = []
            
            # For demonstration, we'll only scan a small subset
            max_hosts = 254
            
            # Get our own MAC address to exclude from the results
            own_mac = interface_info.get('mac', '').lower()
            
            # This would be done in a more sophisticated way in production
            # For demo purposes, we'll simulate finding some clients
            for host in list(network.hosts())[:max_hosts]:
                host_str = str(host)
                
                # Skip our own IP
                if host_str == interface_info['ipv4']:
                    continue
                
                # Try to ping the host
                if self.ping(host_str, timeout=0.5):
                    try:
                        # Try to get MAC address (platform-specific)
                        if os.name == 'nt':  # Windows
                            output = subprocess.check_output(f"arp -a {host_str}", shell=True).decode('utf-8')
                            for line in output.split('\n'):
                                if host_str in line:
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        mac = parts[1].replace('-', ':').lower()
                                        if mac != own_mac and mac != "ff:ff:ff:ff:ff:ff":
                                            clients.append({'ip': host_str, 'mac': mac})
                        else:  # Unix/Linux
                            output = subprocess.check_output(f"arp -n {host_str}", shell=True).decode('utf-8')
                            for line in output.split('\n'):
                                if host_str in line:
                                    parts = line.split()
                                    if len(parts) >= 3:
                                        mac = parts[2].lower()
                                        if mac != own_mac and mac != "ff:ff:ff:ff:ff:ff":
                                            clients.append({'ip': host_str, 'mac': mac})
                    except Exception as e:
                        logger.debug(f"Error getting MAC address for {host_str}: {e}")
            
            logger.info(f"Discovered {len(clients)} clients using alternative method")
            return clients
            
        except Exception as e:
            logger.error(f"Failed to discover clients: {e}")
            return []
            
    def start_client_discovery_loop(self, interface_name, subnet=None, callback=None, interval=60):
        """
        Start a background thread that periodically discovers clients
        
        Args:
            interface_name (str): Name of the interface to use for scanning
            subnet (str, optional): Subnet to scan
            callback (callable, optional): Function to call with discovered clients
            interval (int): Interval between scans in seconds
        """
        stop_event = threading.Event()
        
        def _discovery_loop():
            while not stop_event.is_set():
                try:
                    clients = self.discover_clients(interface_name, subnet)
                    if callback and callable(callback):
                        callback(clients)
                except Exception as e:
                    logger.error(f"Error in client discovery loop: {e}")
                    
                # Wait for the next scan or until stop is called
                stop_event.wait(interval)
        
        discovery_thread = threading.Thread(target=_discovery_loop)
        discovery_thread.daemon = True
        discovery_thread.start()
        
        logger.info(f"Started client discovery on interface {interface_name} every {interval} seconds")
        
        # Return the stop event, which can be used to stop the discovery loop
        return stop_event
