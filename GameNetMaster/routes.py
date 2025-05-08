import os
from flask import render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import uuid
import logging
import threading

from app import app, db
from models import User, Client, VHDImage, NetworkSettings, ClientStats
from pxe_server import PXEServer
from vhd_manager import VHDManager
from network_manager import NetworkManager
from language_utils import get_user_language, set_user_language, get_direction, translate

# Initialize managers
vhd_manager = VHDManager()
network_manager = NetworkManager()
pxe_server = None
client_discovery_stop_event = None

# Logger
logger = logging.getLogger(__name__)

# Start PXE server in a separate thread
def start_pxe_server():
    global pxe_server
    
    with app.app_context():
        settings = NetworkSettings.query.first()
        if settings and settings.tftp_enabled:
            logger.info(f"Starting PXE server with settings: {settings.network_interface}, {settings.tftp_root_dir}")
            pxe_server = PXEServer(
                interface=settings.network_interface,
                tftp_root=settings.tftp_root_dir,
                dhcp_enabled=settings.dhcp_enabled,
                subnet=settings.subnet,
                gateway=settings.gateway,
                dns_server=settings.dns_server
            )
            pxe_server_thread = threading.Thread(target=pxe_server.start)
            pxe_server_thread.daemon = True
            pxe_server_thread.start()
            logger.info("PXE server started in background thread")

# Handle auto-discovered clients
def handle_discovered_clients(clients_list):
    """
    Process the discovered clients and add them to the database if they don't exist
    
    Args:
        clients_list (list): List of dictionaries with client info (mac, ip)
    """
    if not clients_list:
        return
        
    try:
        with app.app_context():
            # Get list of existing MAC addresses
            existing_macs = {client.mac_address.lower() for client in Client.query.all()}
            
            # Process new clients
            for client in clients_list:
                mac = client.get('mac', '').lower()
                ip = client.get('ip', '')
                
                if not mac or mac in existing_macs:
                    continue
                
                logger.info(f"Auto-discovered new client with MAC: {mac}, IP: {ip}")
                
                # Create a new client
                new_client = Client(
                    name=f"Auto-discovered client ({mac})",
                    mac_address=mac,
                    ip_address=ip,
                    is_persistent=False,  # Default to non-persistent
                    is_online=True,  # It's online since we just discovered it
                    last_seen=db.func.now()
                )
                
                db.session.add(new_client)
            
            db.session.commit()
            logger.info(f"Processed {len(clients_list)} discovered clients")
    except Exception as e:
        logger.error(f"Error processing discovered clients: {e}")

# Start client auto-discovery
def start_client_discovery():
    global client_discovery_stop_event
    
    with app.app_context():
        settings = NetworkSettings.query.first()
        if settings:
            # Stop existing discovery if running
            if client_discovery_stop_event:
                client_discovery_stop_event.set()
                client_discovery_stop_event = None
                
            interface = settings.network_interface
            subnet = settings.subnet
            
            # Start new discovery loop
            logger.info(f"Starting client auto-discovery on interface {interface}, subnet {subnet}")
            client_discovery_stop_event = network_manager.start_client_discovery_loop(
                interface_name=interface,
                subnet=subnet,
                callback=handle_discovered_clients,
                interval=60  # Check every minute
            )

# Start the PXE server when the application starts
# Initialize services on startup
def initialize_services():
    start_pxe_server()
    start_client_discovery()
    
# Call initialize_services on application startup
with app.app_context():
    initialize_services()

# Language routes
@app.route('/language/<lang>')
def change_language(lang):
    """Change the user's language preference"""
    if lang in ['en', 'fa']:
        set_user_language(lang)
        # Get the URL to redirect back to
        next_page = request.args.get('next') or request.referrer or url_for('dashboard')
        return redirect(next_page)
    return redirect(url_for('dashboard'))

# Context processor to make language functions available in all templates
@app.context_processor
def inject_language_utilities():
    """Inject language utilities into all templates"""
    return {
        'get_user_language': get_user_language,
        'get_direction': get_direction,
        'translate': translate,
        't': translate  # Shorter alias for convenience
    }

# Login and Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash(translate('invalid_username_password'), 'danger')
            return render_template('login.html')
            
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash(translate('invalid_username_password'), 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Main Dashboard
@app.route('/')
@login_required
def dashboard():
    # Get summary statistics
    total_clients = Client.query.count()
    online_clients = Client.query.filter_by(is_online=True).count()
    total_vhds = VHDImage.query.count()
    
    # Get recent activities
    recent_boots = Client.query.filter(Client.last_boot != None).order_by(Client.last_boot.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html', 
        total_clients=total_clients,
        online_clients=online_clients,
        total_vhds=total_vhds,
        recent_boots=recent_boots
    )

# Client Management Routes
@app.route('/clients')
@login_required
def clients():
    clients_list = Client.query.all()
    vhds = VHDImage.query.all()
    return render_template('clients.html', clients=clients_list, vhds=vhds)

@app.route('/clients/view/<int:client_id>')
@login_required
def view_client(client_id):
    client = Client.query.get_or_404(client_id)
    
    # Parse system_info JSON if available
    hardware_specs = {}
    if client.system_info:
        try:
            import json
            hardware_specs = json.loads(client.system_info)
        except:
            hardware_specs = {"error": "Could not parse system information"}
    
    # Get client statistics
    stats = ClientStats.query.filter_by(client_id=client.id).order_by(ClientStats.timestamp.desc()).limit(20).all()
    
    return render_template('client_detail.html', 
                          client=client, 
                          hardware_specs=hardware_specs, 
                          stats=stats)

@app.route('/clients/add', methods=['POST'])
@login_required
def add_client():
    name = request.form.get('name')
    mac_address = request.form.get('mac_address')
    vhd_id = request.form.get('vhd_id')
    is_persistent = 'is_persistent' in request.form
    boot_mode = request.form.get('boot_mode', 'UEFI')
    
    if not name or not mac_address:
        flash('Client name and MAC address are required', 'danger')
        return redirect(url_for('clients'))
    
    # Normalize MAC address format (XX:XX:XX:XX:XX:XX)
    mac_address = mac_address.replace('-', ':').lower()
    
    # Check if client with this MAC already exists
    existing_client = Client.query.filter_by(mac_address=mac_address).first()
    if existing_client:
        flash(f'Client with MAC address {mac_address} already exists', 'danger')
        return redirect(url_for('clients'))
    
    # Create new client
    new_client = Client(
        name=name,
        mac_address=mac_address,
        vhd_id=vhd_id if vhd_id else None,
        is_persistent=is_persistent,
        boot_mode=boot_mode
    )
    
    db.session.add(new_client)
    db.session.commit()
    
    flash(f'Client {name} added successfully', 'success')
    return redirect(url_for('clients'))

@app.route('/clients/edit/<int:client_id>', methods=['POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    
    client.name = request.form.get('name')
    client.mac_address = request.form.get('mac_address').replace('-', ':').lower()
    client.vhd_id = request.form.get('vhd_id') or None
    client.is_persistent = 'is_persistent' in request.form
    client.boot_mode = request.form.get('boot_mode', 'UEFI')
    client.post_boot_script = request.form.get('post_boot_script')
    
    db.session.commit()
    flash(f'Client {client.name} updated successfully', 'success')
    return redirect(url_for('clients'))

@app.route('/clients/delete/<int:client_id>', methods=['POST'])
@login_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash(f'Client {client.name} deleted successfully', 'success')
    return redirect(url_for('clients'))

@app.route('/clients/reboot/<int:client_id>', methods=['POST'])
@login_required
def reboot_client(client_id):
    client = Client.query.get_or_404(client_id)
    
    if not client.is_online:
        flash(f'Cannot reboot offline client {client.name}', 'danger')
    else:
        # In a real implementation, we would send a reboot command to the client
        flash(f'Reboot command sent to {client.name}', 'success')
    
    return redirect(url_for('clients'))

# VHD Management Routes
@app.route('/vhd')
@login_required
def vhd_management():
    vhds = VHDImage.query.all()
    return render_template('vhd_management.html', vhds=vhds)

@app.route('/vhd/add', methods=['POST'])
@login_required
def add_vhd():
    name = request.form.get('name')
    description = request.form.get('description')
    size_gb = float(request.form.get('size_gb', 50))
    windows_version = request.form.get('windows_version')
    is_template = 'is_template' in request.form
    
    if not name:
        flash('VHD name is required', 'danger')
        return redirect(url_for('vhd_management'))
    
    # In a real implementation, we would create the VHD file here
    # For the demo, we'll assume it's created at a predefined location
    
    settings = NetworkSettings.query.first()
    file_path = os.path.join(settings.vhd_storage_dir, f"{secure_filename(name)}.vhd")
    
    # Create VHD record
    new_vhd = VHDImage(
        name=name,
        description=description,
        file_path=file_path,
        size_gb=size_gb,
        windows_version=windows_version,
        is_template=is_template,
        created_by_id=current_user.id
    )
    
    db.session.add(new_vhd)
    db.session.commit()
    
    # In a real implementation, we would actually create the VHD file here
    success = vhd_manager.create_vhd(file_path, size_gb)
    
    if success:
        flash(f'VHD {name} added successfully', 'success')
    else:
        flash(f'Error creating VHD file at {file_path}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/edit/<int:vhd_id>', methods=['POST'])
@login_required
def edit_vhd(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    vhd.name = request.form.get('name')
    vhd.description = request.form.get('description')
    vhd.windows_version = request.form.get('windows_version')
    vhd.is_template = 'is_template' in request.form
    vhd.is_locked = 'is_locked' in request.form
    vhd.last_modified = db.func.now()
    
    db.session.commit()
    flash(f'VHD {vhd.name} updated successfully', 'success')
    return redirect(url_for('vhd_management'))

@app.route('/vhd/delete/<int:vhd_id>', methods=['POST'])
@login_required
def delete_vhd(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    # Check if any clients are using this VHD
    clients_using_vhd = Client.query.filter_by(vhd_id=vhd_id).count()
    if clients_using_vhd > 0:
        flash(f'Cannot delete VHD {vhd.name} because it is assigned to {clients_using_vhd} clients', 'danger')
        return redirect(url_for('vhd_management'))
    
    # In a real implementation, we would delete the actual VHD file here
    vhd_manager.delete_vhd(vhd.file_path)
    
    db.session.delete(vhd)
    db.session.commit()
    flash(f'VHD {vhd.name} deleted successfully', 'success')
    return redirect(url_for('vhd_management'))

@app.route('/vhd/clone/<int:vhd_id>', methods=['POST'])
@login_required
def clone_vhd(vhd_id):
    source_vhd = VHDImage.query.get_or_404(vhd_id)
    new_name = request.form.get('new_name', f"Clone of {source_vhd.name}")
    
    settings = NetworkSettings.query.first()
    new_file_path = os.path.join(settings.vhd_storage_dir, f"{secure_filename(new_name)}.vhd")
    
    # Create clone record
    clone_vhd = VHDImage(
        name=new_name,
        description=f"Clone of {source_vhd.name}: {source_vhd.description}",
        file_path=new_file_path,
        size_gb=source_vhd.size_gb,
        windows_version=source_vhd.windows_version,
        is_template=False,
        is_super_mode=source_vhd.is_super_mode,  # Copy super mode setting
        created_by_id=current_user.id
    )
    
    db.session.add(clone_vhd)
    db.session.commit()
    
    # In a real implementation, we would actually clone the VHD file here
    success = vhd_manager.clone_vhd(source_vhd.file_path, new_file_path)
    
    if success:
        flash(f'VHD cloned successfully as {new_name}', 'success')
    else:
        flash(f'Error cloning VHD to {new_file_path}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/toggle_super_mode/<int:vhd_id>', methods=['POST'])
@login_required
def toggle_super_mode(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    if vhd.is_super_mode:
        # Disable super mode
        commit_changes = 'commit_changes' in request.form
        success = vhd_manager.disable_super_mode(vhd.file_path, commit_changes)
        
        if success:
            vhd.is_super_mode = False
            db.session.commit()
            
            if commit_changes:
                flash(f'Super mode disabled for {vhd.name} and changes committed', 'success')
            else:
                flash(f'Super mode disabled for {vhd.name}, changes discarded', 'success')
        else:
            flash(f'Error disabling super mode for {vhd.name}', 'danger')
    else:
        # Enable super mode
        settings = NetworkSettings.query.first()
        diff_dir = os.path.join(settings.vhd_storage_dir, 'diffs')
        success = vhd_manager.enable_super_mode(vhd.file_path, diff_dir)
        
        if success:
            vhd.is_super_mode = True
            db.session.commit()
            flash(f'Super mode enabled for {vhd.name}', 'success')
        else:
            flash(f'Error enabling super mode for {vhd.name}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/commit_changes/<int:vhd_id>', methods=['POST'])
@login_required
def commit_vhd_changes(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    if not vhd.is_super_mode:
        flash(f'VHD {vhd.name} is not in super mode', 'warning')
        return redirect(url_for('vhd_management'))
    
    success = vhd_manager.commit_changes(vhd.file_path)
    
    if success:
        vhd.last_modified = db.func.now()
        db.session.commit()
        flash(f'Changes committed for {vhd.name}', 'success')
    else:
        flash(f'Error committing changes for {vhd.name}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/discard_changes/<int:vhd_id>', methods=['POST'])
@login_required
def discard_vhd_changes(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    if not vhd.is_super_mode:
        flash(f'VHD {vhd.name} is not in super mode', 'warning')
        return redirect(url_for('vhd_management'))
    
    success = vhd_manager.discard_changes(vhd.file_path)
    
    if success:
        flash(f'Changes discarded for {vhd.name}', 'success')
    else:
        flash(f'Error discarding changes for {vhd.name}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/create_restoration_point/<int:vhd_id>', methods=['POST'])
@login_required
def create_restoration_point(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    if not name:
        flash('Restoration point name is required', 'danger')
        return redirect(url_for('vhd_management'))
    
    settings = NetworkSettings.query.first()
    backup_dir = os.path.join(settings.vhd_storage_dir, 'backups', str(vhd_id))
    
    backup_path = vhd_manager.create_restoration_point(vhd.file_path, name, description, backup_dir)
    
    if backup_path:
        # Create restoration point record
        new_point = RestorationPoint(
            vhd_id=vhd.id,
            name=name,
            description=description,
            backup_path=backup_path,
            created_by_id=current_user.id
        )
        
        db.session.add(new_point)
        db.session.commit()
        
        flash(f'Restoration point "{name}" created for {vhd.name}', 'success')
    else:
        flash(f'Error creating restoration point for {vhd.name}', 'danger')
    
    return redirect(url_for('vhd_management'))

@app.route('/vhd/restoration_points/<int:vhd_id>')
@login_required
def restoration_points(vhd_id):
    vhd = VHDImage.query.get_or_404(vhd_id)
    points = RestorationPoint.query.filter_by(vhd_id=vhd_id).order_by(RestorationPoint.created_at.desc()).all()
    
    return render_template('restoration_points.html', vhd=vhd, points=points)

@app.route('/vhd/restore/<int:point_id>', methods=['POST'])
@login_required
def restore_from_point(point_id):
    point = RestorationPoint.query.get_or_404(point_id)
    vhd = VHDImage.query.get_or_404(point.vhd_id)
    
    # Check if any clients are currently using this VHD
    clients_using_vhd = Client.query.filter_by(vhd_id=vhd.id, is_online=True).count()
    if clients_using_vhd > 0:
        flash(f'Cannot restore VHD {vhd.name} because it is in use by {clients_using_vhd} online clients', 'danger')
        return redirect(url_for('restoration_points', vhd_id=vhd.id))
    
    success = vhd_manager.restore_from_point(point.backup_path, vhd.file_path)
    
    if success:
        vhd.last_modified = db.func.now()
        db.session.commit()
        flash(f'VHD {vhd.name} restored to point "{point.name}"', 'success')
    else:
        flash(f'Error restoring VHD from point "{point.name}"', 'danger')
    
    return redirect(url_for('restoration_points', vhd_id=vhd.id))

@app.route('/vhd/delete_point/<int:point_id>', methods=['POST'])
@login_required
def delete_restoration_point(point_id):
    point = RestorationPoint.query.get_or_404(point_id)
    vhd_id = point.vhd_id
    
    # Delete the actual backup file
    if os.path.exists(point.backup_path):
        os.remove(point.backup_path)
    
    db.session.delete(point)
    db.session.commit()
    
    flash(f'Restoration point "{point.name}" deleted', 'success')
    return redirect(url_for('restoration_points', vhd_id=vhd_id))

# Network Settings Routes
@app.route('/network')
@login_required
def network_settings():
    settings = NetworkSettings.query.first()
    return render_template('network.html', settings=settings)

@app.route('/network/update', methods=['POST'])
@login_required
def update_network_settings():
    settings = NetworkSettings.query.first()
    
    restart_required = False
    
    # Check if critical settings have changed
    if (settings.tftp_enabled != ('tftp_enabled' in request.form) or
        settings.dhcp_enabled != ('dhcp_enabled' in request.form) or
        settings.network_interface != request.form.get('network_interface') or
        settings.subnet != request.form.get('subnet') or
        settings.gateway != request.form.get('gateway') or
        settings.dns_server != request.form.get('dns_server')):
        restart_required = True
    
    # Update settings
    settings.tftp_enabled = 'tftp_enabled' in request.form
    settings.dhcp_enabled = 'dhcp_enabled' in request.form
    settings.network_interface = request.form.get('network_interface')
    settings.subnet = request.form.get('subnet')
    settings.gateway = request.form.get('gateway')
    settings.dns_server = request.form.get('dns_server')
    settings.tftp_root_dir = request.form.get('tftp_root_dir')
    settings.vhd_storage_dir = request.form.get('vhd_storage_dir')
    settings.bandwidth_limit_mbps = int(request.form.get('bandwidth_limit_mbps', 0))
    settings.caching_enabled = 'caching_enabled' in request.form
    settings.cache_size_mb = int(request.form.get('cache_size_mb', 1024))
    settings.last_updated = db.func.now()
    
    db.session.commit()
    
    # Restart PXE server if necessary
    if restart_required and pxe_server:
        pxe_server.stop()
        start_pxe_server()
        flash('Network settings updated and PXE server restarted', 'success')
    else:
        flash('Network settings updated successfully', 'success')
    
    return redirect(url_for('network_settings'))

# User Management Routes
@app.route('/settings')
@login_required
def settings():
    if current_user.is_admin:
        users = User.query.all()
    else:
        users = [current_user]
    
    return render_template('settings.html', users=users)

@app.route('/settings/change_password', methods=['POST'])
@login_required
def change_password():
    user_id = request.form.get('user_id')
    
    # Only allow admin to change other users' passwords
    if int(user_id) != current_user.id and not current_user.is_admin:
        flash('You do not have permission to change this password', 'danger')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(user_id)
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # If admin is changing another user's password, don't require current password
    if user_id != str(current_user.id) and current_user.is_admin:
        pass
    elif not check_password_hash(user.password_hash, current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('settings'))
    
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash('Password changed successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/add_user', methods=['POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        flash('You do not have permission to add users', 'danger')
        return redirect(url_for('settings'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    
    if not username or not email or not password:
        flash('All fields are required', 'danger')
        return redirect(url_for('settings'))
    
    # Check if username or email already exists
    existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        flash('Username or email already exists', 'danger')
        return redirect(url_for('settings'))
    
    # Create new user
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_admin=is_admin
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'User {username} added successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/settings/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to delete users', 'danger')
        return redirect(url_for('settings'))
    
    if user_id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.username} deleted successfully', 'success')
    return redirect(url_for('settings'))

# API endpoints for AJAX calls
@app.route('/api/clients/status', methods=['GET'])
@login_required
def client_status():
    clients = Client.query.all()
    status_data = [{
        'id': client.id,
        'name': client.name,
        'mac_address': client.mac_address,
        'ip_address': client.ip_address,
        'is_online': client.is_online,
        'vhd_name': client.vhd.name if client.vhd else "No VHD assigned"
    } for client in clients]
    
    return jsonify(status_data)

@app.route('/api/clients/stats/<int:client_id>', methods=['GET'])
@login_required
def client_stats(client_id):
    # Get the most recent stats for this client
    stats = ClientStats.query.filter_by(client_id=client_id).order_by(ClientStats.timestamp.desc()).first()
    
    if stats:
        return jsonify({
            'cpu_usage': stats.cpu_usage,
            'memory_usage_mb': stats.memory_usage_mb,
            'network_rx_mbps': stats.network_rx_mbps,
            'network_tx_mbps': stats.network_tx_mbps,
            'timestamp': stats.timestamp.isoformat()
        })
    else:
        return jsonify({
            'error': 'No stats available for this client'
        }), 404

@app.route('/api/clients/update_status', methods=['POST'])
def update_client_status():
    """API endpoint for clients to update their status"""
    # In a real implementation, we would authenticate clients using a token
    data = request.json
    
    mac_address = data.get('mac_address')
    ip_address = data.get('ip_address')
    is_online = data.get('is_online', True)
    
    if not mac_address:
        return jsonify({'error': 'MAC address is required'}), 400
    
    client = Client.query.filter_by(mac_address=mac_address).first()
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    client.is_online = is_online
    client.ip_address = ip_address
    
    if is_online:
        client.last_boot = db.func.now()
    else:
        client.last_shutdown = db.func.now()
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/clients/submit_stats', methods=['POST'])
def submit_client_stats():
    """API endpoint for clients to submit their performance stats"""
    # In a real implementation, we would authenticate clients using a token
    data = request.json
    
    mac_address = data.get('mac_address')
    
    if not mac_address:
        return jsonify({'error': 'MAC address is required'}), 400
    
    client = Client.query.filter_by(mac_address=mac_address).first()
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    # Create new stats record
    stats = ClientStats(
        client_id=client.id,
        cpu_usage=data.get('cpu_usage'),
        memory_usage_mb=data.get('memory_usage_mb'),
        network_rx_mbps=data.get('network_rx_mbps'),
        network_tx_mbps=data.get('network_tx_mbps')
    )
    
    db.session.add(stats)
    db.session.commit()
    
    return jsonify({'success': True})
