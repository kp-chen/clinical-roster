#!/usr/bin/env python
"""
Run script for Clinical Roster Builder
"""
import os
import sys
from app import create_app, db
from app.models.user import Role

# Get configuration name from environment
config_name = os.environ.get('FLASK_ENV', 'development')

# Create application
app = create_app(config_name)

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        return {'status': 'healthy', 'service': 'clinical-roster'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 503

# CLI commands
@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    Role.create_default_roles()
    print("Database initialized with default roles.")

@app.cli.command()
def create_admin():
    """Create an admin user."""
    from app.models.user import User
    from app.security.rbac import PermissionManager
    
    email = input("Admin email: ")
    password = input("Admin password: ")
    
    # Check if user exists
    user = User.query.filter_by(email=email).first()
    if user:
        print(f"User {email} already exists.")
        if input("Grant admin role? (y/n): ").lower() == 'y':
            PermissionManager.grant_role(user, Role.ADMIN)
            print("Admin role granted.")
    else:
        # Create new user
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Grant admin role
        PermissionManager.grant_role(user, Role.ADMIN)
        print(f"Admin user {email} created successfully.")

if __name__ == '__main__':
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("Warning: .env file not found. Creating from .env.example...")
        if os.path.exists('.env.example'):
            import shutil
            shutil.copy('.env.example', '.env')
            print("Created .env file. Please update it with your configuration.")
        else:
            print("Error: .env.example not found. Please create a .env file.")
            sys.exit(1)
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        Role.create_default_roles()
        print("Database tables created/verified.")
        
        # Create default admin in development
        if app.config['ENV'] == 'development':
            from app.models.user import User
            from app.security.rbac import PermissionManager
            
            admin = User.query.filter_by(email='admin@clinicalroster.com').first()
            if not admin:
                admin = User(email='admin@clinicalroster.com')
                admin.set_password('Admin123!')
                db.session.add(admin)
                db.session.commit()
                PermissionManager.grant_role(admin, Role.ADMIN)
                print("Created default admin user: admin@clinicalroster.com / Admin123!")
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = app.config['DEBUG']
    
    print(f"Starting Clinical Roster Builder on port {port}...")
    print(f"Debug mode: {debug}")
    print(f"Environment: {config_name}")
    print(f"Visit http://localhost:{port} to access the application")
    
    app.run(host='0.0.0.0', port=port, debug=debug)