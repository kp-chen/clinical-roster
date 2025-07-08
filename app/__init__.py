"""Application factory for Clinical Roster System"""
import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from datetime import timedelta

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Create and configure the Flask application"""
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    from config import config
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Create necessary directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    
    # Register blueprints
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.roster import roster_bp
    app.register_blueprint(roster_bp)
    
    # Register API blueprints
    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    
    # Register custom template filters
    @app.template_filter('datetime')
    def datetime_filter(date_string):
        """Convert date string to datetime object for formatting"""
        from datetime import datetime
        try:
            return datetime.strptime(date_string, '%Y-%m-%d')
        except:
            return datetime.now()
    
    # Register login manager user loader
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Register context processors
    @app.context_processor
    def inject_user():
        """Make current_user available in all templates"""
        from flask_login import current_user
        return dict(current_user=current_user)
    
    # Register security middleware
    if app.config['ENV'] == 'production':
        from app.security.middleware import setup_security_headers
        setup_security_headers(app)
    
    # Register error handlers
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Setup audit logging
    if not app.config.get('TESTING'):
        from app.security.audit import setup_audit_logging
        setup_audit_logging(app)
    
    # Create tables in app context
    with app.app_context():
        if app.config.get('CREATE_TABLES_ON_START', True):
            db.create_all()
            logger.info("Database tables created/verified")
    
    return app