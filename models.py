from app import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    mac_address = db.Column(db.String(17), unique=True, nullable=False)
    ip_address = db.Column(db.String(15))
    vhd_id = db.Column(db.Integer, db.ForeignKey('vhd_image.id'))
    is_persistent = db.Column(db.Boolean, default=False)
    is_online = db.Column(db.Boolean, default=False)
    last_boot = db.Column(db.DateTime)
    last_shutdown = db.Column(db.DateTime)
    last_seen = db.Column(db.DateTime)
    boot_mode = db.Column(db.String(10), default='UEFI')  # UEFI or Legacy
    post_boot_script = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    system_info = db.Column(db.Text)  # JSON string with system info
    
    # Relationship to VHD
    vhd = db.relationship('VHDImage', backref='clients')

class VHDImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(256), nullable=False)
    size_gb = db.Column(db.Float, nullable=False)
    windows_version = db.Column(db.String(32))
    is_template = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_super_mode = db.Column(db.Boolean, default=False)  # Flag for super mode
    parent_id = db.Column(db.Integer, db.ForeignKey('vhd_image.id'))  # For linking restoration points
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationship to User
    created_by = db.relationship('User', backref='vhd_images')
    # Relationship to parent VHD (for restoration points)
    parent = db.relationship('VHDImage', remote_side=[id], backref='restoration_points')
    
class RestorationPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vhd_id = db.Column(db.Integer, db.ForeignKey('vhd_image.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    backup_path = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    vhd = db.relationship('VHDImage', backref='backups')
    created_by = db.relationship('User', backref='created_backups')

class NetworkSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tftp_enabled = db.Column(db.Boolean, default=True)
    dhcp_enabled = db.Column(db.Boolean, default=True)
    network_interface = db.Column(db.String(32), default='eth0')
    subnet = db.Column(db.String(32), default='192.168.1.0/24')
    gateway = db.Column(db.String(15), default='192.168.1.1')
    dns_server = db.Column(db.String(15), default='8.8.8.8')
    tftp_root_dir = db.Column(db.String(256), default='/tmp/tftp')
    vhd_storage_dir = db.Column(db.String(256), default='/opt/gamenet/vhd')
    bandwidth_limit_mbps = db.Column(db.Integer, default=0)  # 0 means unlimited
    caching_enabled = db.Column(db.Boolean, default=True)
    cache_size_mb = db.Column(db.Integer, default=1024)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class ClientStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cpu_usage = db.Column(db.Float)
    memory_usage_mb = db.Column(db.Float)
    network_rx_mbps = db.Column(db.Float)
    network_tx_mbps = db.Column(db.Float)
    
    # Relationship to Client
    client = db.relationship('Client', backref='stats')

# New models for client-server communication

class ApiToken(db.Model):
    """API Tokens for client authentication"""
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    is_revoked = db.Column(db.Boolean, default=False)
    revoked_at = db.Column(db.DateTime)

    # Relationship to Client
    client = db.relationship('Client', backref='api_tokens')

class ClientCommand(db.Model):
    """Commands sent from server to clients"""
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    command_type = db.Column(db.String(32), nullable=False)  # reboot, shutdown, launch_app, update_config
    command_data = db.Column(db.Text)  # JSON string with command parameters
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed = db.Column(db.Boolean, default=False)
    executed_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Relationships
    client = db.relationship('Client', backref='commands')
    created_by = db.relationship('User', backref='commands')

class Rate(db.Model):
    """Pricing rates for client usage"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    hourly_rate = db.Column(db.Float, nullable=False)  # Cost per hour
    minimum_minutes = db.Column(db.Integer, default=15)  # Minimum billing time in minutes
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationship to User
    created_by = db.relationship('User', backref='created_rates')

class ClientSession(db.Model):
    """User sessions on client computers"""
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    user_name = db.Column(db.String(64))  # Client user (not server user)
    rate_id = db.Column(db.Integer, db.ForeignKey('rate.id'))
    billed_amount = db.Column(db.Float)  # Amount billed for this session
    payment_status = db.Column(db.String(20), default='Pending')  # Pending, Paid, Waived
    notes = db.Column(db.Text)
    
    # Relationships
    client = db.relationship('Client', backref='sessions')
    rate = db.relationship('Rate', backref='sessions')
    
class BillingSettings(db.Model):
    """Global billing settings"""
    id = db.Column(db.Integer, primary_key=True)
    default_rate_id = db.Column(db.Integer, db.ForeignKey('rate.id'))
    currency_symbol = db.Column(db.String(5), default='$')
    payment_methods = db.Column(db.Text, default='Cash,Credit Card')  # Comma-separated list
    receipt_header = db.Column(db.Text)
    receipt_footer = db.Column(db.Text)
    tax_percentage = db.Column(db.Float, default=0)  # e.g., 9.5 for 9.5%
    enable_automatic_billing = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    default_rate = db.relationship('Rate')
    updated_by = db.relationship('User')
    
class Payment(db.Model):
    """Payment records"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('client_session.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # Cash, Credit Card, etc.
    payment_time = db.Column(db.DateTime, default=datetime.utcnow)
    receipt_number = db.Column(db.String(32), unique=True)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationships
    session = db.relationship('ClientSession', backref='payments')
    created_by = db.relationship('User', backref='processed_payments')
