"""
API Routes for GameNetMaster
This file contains API endpoints for client-server communication
"""

import os
import uuid
import logging
import json
from datetime import datetime
from functools import wraps
from flask import request, jsonify, Blueprint
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from app import app, db
from models import Client, ClientStats, ClientCommand, ApiToken

# Setup logging
logger = logging.getLogger(__name__)

# Create Blueprint
api = Blueprint('api', __name__)

# Helper function to validate API token
def require_api_token(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Invalid or missing token'}), 401
            
        token = auth_header.replace('Bearer ', '')
        
        # Check if token exists in database
        token_record = ApiToken.query.filter_by(token=token).first()
        if not token_record or token_record.is_revoked:
            return jsonify({'error': 'Invalid token'}), 401
            
        # Update last used timestamp
        token_record.last_used = db.func.now()
        db.session.commit()
        
        return func(*args, **kwargs)
    return decorated_function

# Client registration and authentication
@api.route('/client/register', methods=['POST'])
def register_client():
    """Register a client with the server and receive API token"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        mac_address = data.get('mac_address')
        hostname = data.get('hostname')
        ip_address = data.get('ip_address')
        
        if not mac_address or not hostname:
            return jsonify({'error': 'MAC address and hostname are required'}), 400
            
        # Check if client exists
        client = Client.query.filter_by(mac_address=mac_address).first()
        
        if not client:
            return jsonify({'error': 'Client not recognized. Please add client on server first.'}), 403
            
        # Update client IP and online status
        client.ip_address = ip_address
        client.is_online = True
        client.last_boot = db.func.now()
        
        # Generate or retrieve API token
        token_record = ApiToken.query.filter_by(client_id=client.id, is_revoked=False).first()
        
        if not token_record:
            # Generate new token
            token = str(uuid.uuid4())
            token_record = ApiToken(
                client_id=client.id,
                token=token,
                created_at=db.func.now(),
                last_used=db.func.now()
            )
            db.session.add(token_record)
            
        else:
            # Use existing token
            token = token_record.token
            token_record.last_used = db.func.now()
        
        db.session.commit()
        
        # Return client info and token
        return jsonify({
            'client_id': client.id,
            'auth_token': token,
            'config': {
                'server_url': request.host_url.rstrip('/'),
                'auto_login': True,
                'monitoring_interval': 30,
                'heartbeat_interval': 60
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error registering client: {e}")
        return jsonify({'error': 'Server error'}), 500

# Client heartbeat to update status
@api.route('/client/heartbeat', methods=['POST'])
@require_api_token
def client_heartbeat():
    """Update client status through heartbeat"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        client_id = data.get('client_id')
        mac_address = data.get('mac_address')
        ip_address = data.get('ip_address')
        
        if not client_id or not mac_address:
            return jsonify({'error': 'Client ID and MAC address are required'}), 400
            
        # Find client
        client = Client.query.get(client_id)
        
        if not client or client.mac_address != mac_address:
            return jsonify({'error': 'Client not found or MAC address mismatch'}), 404
            
        # Update client status
        client.is_online = True
        client.ip_address = ip_address
        client.last_seen = db.func.now()
        
        db.session.commit()
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        return jsonify({'error': 'Server error'}), 500

# Client submits performance stats
@api.route('/client/stats', methods=['POST'])
@require_api_token
def submit_client_stats():
    """Submit client performance statistics"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({'error': 'Client ID is required'}), 400
            
        # Verify client exists
        client = Client.query.get(client_id)
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
            
        # Create stats record
        stats = ClientStats(
            client_id=client_id,
            cpu_usage=data.get('cpu_usage'),
            memory_usage_mb=data.get('memory_usage_mb'),
            network_rx_mbps=data.get('network_rx_mbps'),
            network_tx_mbps=data.get('network_tx_mbps')
        )
        
        db.session.add(stats)
        db.session.commit()
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error submitting stats: {e}")
        return jsonify({'error': 'Server error'}), 500

# Get commands for client
@api.route('/client/commands', methods=['GET'])
@require_api_token
def get_client_commands():
    """Get pending commands for client"""
    try:
        client_id = request.args.get('client_id')
        
        if not client_id:
            return jsonify({'error': 'Client ID is required'}), 400
            
        # Find pending commands
        commands = ClientCommand.query.filter_by(
            client_id=client_id,
            executed=False
        ).all()
        
        result = {
            'commands': [
                {
                    'id': cmd.id,
                    'type': cmd.command_type,
                    'data': json.loads(cmd.command_data) if cmd.command_data else {},
                    'created_at': cmd.created_at.isoformat() if cmd.created_at else None
                } for cmd in commands
            ]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting commands: {e}")
        return jsonify({'error': 'Server error'}), 500

# Acknowledge command execution
@api.route('/client/commands/<int:command_id>/ack', methods=['POST'])
@require_api_token
def acknowledge_command(command_id):
    """Mark command as executed"""
    try:
        data = request.json
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({'error': 'Client ID is required'}), 400
            
        # Find command
        command = ClientCommand.query.get(command_id)
        
        if not command or str(command.client_id) != str(client_id):
            return jsonify({'error': 'Command not found or not for this client'}), 404
            
        # Update command
        command.executed = True
        command.executed_at = db.func.now()
        
        db.session.commit()
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error acknowledging command: {e}")
        return jsonify({'error': 'Server error'}), 500

# Admin endpoints (require login)

# List all client stats
@api.route('/admin/client_stats', methods=['GET'])
@login_required
def list_client_stats():
    """List stats for all clients or a specific client"""
    try:
        client_id = request.args.get('client_id')
        limit = int(request.args.get('limit', 100))
        
        if client_id:
            # Get stats for specific client
            stats = ClientStats.query.filter_by(client_id=client_id).order_by(
                ClientStats.timestamp.desc()).limit(limit).all()
            
            client = Client.query.get(client_id)
            if not client:
                return jsonify({'error': 'Client not found'}), 404
                
            client_name = client.name
        else:
            # Get most recent stats for all clients
            stats = []
            clients = Client.query.all()
            
            for client in clients:
                recent_stat = ClientStats.query.filter_by(client_id=client.id).order_by(
                    ClientStats.timestamp.desc()).first()
                    
                if recent_stat:
                    stats.append(recent_stat)
            
            client_name = None
        
        result = {
            'client_id': client_id,
            'client_name': client_name,
            'stats': [
                {
                    'id': stat.id,
                    'client_id': stat.client_id,
                    'timestamp': stat.timestamp.isoformat() if stat.timestamp else None,
                    'cpu_usage': stat.cpu_usage,
                    'memory_usage_mb': stat.memory_usage_mb,
                    'network_rx_mbps': stat.network_rx_mbps,
                    'network_tx_mbps': stat.network_tx_mbps
                } for stat in stats
            ]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error listing client stats: {e}")
        return jsonify({'error': 'Server error'}), 500

# Send command to client
@api.route('/admin/client_commands', methods=['POST'])
@login_required
def send_client_command():
    """Send a command to a client"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
            
        client_id = data.get('client_id')
        command_type = data.get('command_type')
        command_data = data.get('command_data', {})
        
        if not client_id or not command_type:
            return jsonify({'error': 'Client ID and command type are required'}), 400
            
        # Verify client exists
        client = Client.query.get(client_id)
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
            
        # Create command
        command = ClientCommand(
            client_id=client_id,
            command_type=command_type,
            command_data=json.dumps(command_data),
            created_by_id=current_user.id,
            created_at=db.func.now()
        )
        
        db.session.add(command)
        db.session.commit()
        
        return jsonify({
            'status': 'ok',
            'command_id': command.id
        }), 200
        
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({'error': 'Server error'}), 500

# Register the blueprint
app.register_blueprint(api, url_prefix='/api')