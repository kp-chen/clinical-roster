"""Pytest configuration and fixtures"""
import pytest
import tempfile
import os
from app import create_app, db
from app.models.user import User, Role


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with testing config
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    
    with app.app_context():
        db.create_all()
        Role.create_default_roles()
    
    yield app
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create a test runner for CLI commands"""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def auth_client(client, test_user):
    """Create an authenticated test client"""
    client.post('/auth/login', data={
        'email': test_user.email,
        'password': 'Test123!'
    })
    return client


@pytest.fixture(scope='function')
def test_user(app):
    """Create a test user"""
    with app.app_context():
        user = User(email='test@example.com')
        user.set_password('Test123!')
        db.session.add(user)
        db.session.commit()
        
        yield user
        
        # Cleanup
        db.session.delete(user)
        db.session.commit()


@pytest.fixture(scope='function')
def admin_user(app):
    """Create an admin user"""
    with app.app_context():
        from app.security.rbac import PermissionManager
        
        admin = User(email='admin@example.com')
        admin.set_password('Admin123!')
        db.session.add(admin)
        db.session.commit()
        
        PermissionManager.grant_role(admin, Role.ADMIN)
        
        yield admin
        
        # Cleanup
        db.session.delete(admin)
        db.session.commit()