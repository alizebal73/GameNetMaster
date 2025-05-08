import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up database base class
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # For proper URL generation

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///gamenet.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database with the app
db.init_app(app)

# Setup flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models and recreate database schema
with app.app_context():
    # Import all models
    from models import User, Client, VHDImage, NetworkSettings, ClientStats
    from models import ApiToken, ClientCommand, ClientSession
    
    # Drop and recreate all tables to handle schema changes
    logger.info("Recreating database tables")
    db.drop_all()
    db.create_all()
    
    # Create admin user if none exists
    from werkzeug.security import generate_password_hash
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        logger.info("Creating default admin user")
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin'),
            is_admin=True
        )
        db.session.add(admin)
        
        # Create default network settings
        default_settings = NetworkSettings(
            tftp_enabled=True,
            dhcp_enabled=True,
            network_interface='eth0',
            subnet='192.168.1.0/24',
            gateway='192.168.1.1',
            dns_server='8.8.8.8',
            tftp_root_dir='/tmp/tftp',
            vhd_storage_dir='/opt/gamenet/vhd'
        )
        db.session.add(default_settings)
        
        db.session.commit()

# User loader callback for flask-login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
