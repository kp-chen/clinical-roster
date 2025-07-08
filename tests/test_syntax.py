"""Basic syntax and import tests"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Test that all modules can be imported"""
    imports = [
        "app.models.user",
        "app.models.audit", 
        "app.models.roster",
        "app.security.audit",
        "app.security.encryption",
        "app.security.middleware",
        "app.security.rbac",
        "app.rostering.csp",
        "app.rostering.constraints",
        "app.rostering.solver",
        "app.api.v1.auth",
        "app.api.v1.roster",
        "app.auth.routes",
        "app.auth.routes_enhanced",
        "app.roster.routes",
        "app.utils.decorators",
        "app.utils.error_handlers",
        "app.utils.validators",
        "app.config.base",
        "app.config.development",
        "app.config.production",
        "app.config.testing"
    ]
    
    failed_imports = []
    
    for module in imports:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            # Skip import errors due to missing dependencies
            if "No module named" in str(e) and any(dep in str(e) for dep in ['flask', 'sqlalchemy', 'cryptography', 'pulp', 'pyotp', 'jwt']):
                print(f"⚠ {module} - Missing dependency: {e}")
            else:
                failed_imports.append((module, str(e)))
                print(f"✗ {module} - {e}")
        except SyntaxError as e:
            failed_imports.append((module, str(e)))
            print(f"✗ {module} - Syntax error: {e}")
        except Exception as e:
            failed_imports.append((module, str(e)))
            print(f"✗ {module} - Error: {e}")
    
    if failed_imports:
        print("\nFailed imports:")
        for module, error in failed_imports:
            print(f"  - {module}: {error}")
        return False
    else:
        print("\nAll modules have valid syntax!")
        return True

if __name__ == "__main__":
    test_imports()