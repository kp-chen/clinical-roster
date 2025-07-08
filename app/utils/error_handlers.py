"""Error handlers for the application"""
from flask import render_template, jsonify, request
from werkzeug.exceptions import HTTPException
import logging

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers with the Flask app"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle bad request errors"""
        if request.is_json:
            return jsonify({'error': 'Bad request', 'message': str(error)}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle forbidden errors"""
        if request.is_json:
            return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle not found errors"""
        if request.is_json:
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal error: {str(error)}")
        
        from app import db
        db.session.rollback()
        
        if request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle all HTTP exceptions"""
        logger.warning(f"HTTP Exception: {error.code} - {error.description}")
        
        if request.is_json:
            return jsonify({
                'error': error.name,
                'message': error.description,
                'code': error.code
            }), error.code
        
        # Try to render specific error template
        try:
            return render_template(f'errors/{error.code}.html'), error.code
        except:
            # Fallback to generic error template
            return render_template('errors/generic.html', error=error), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors"""
        logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        
        from app import db
        db.session.rollback()
        
        # Log security event for unexpected errors
        try:
            from app.security.audit import log_security_event
            from app.models.audit import SecurityEvent
            
            log_security_event(
                SecurityEvent.EVENT_DATA_BREACH_SUSPECTED,
                severity='critical',
                description=f"Unexpected error: {type(error).__name__}",
                details={'error': str(error)}
            )
        except:
            pass  # Don't let logging fail the error handler
        
        if request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        
        if app.config.get('DEBUG'):
            raise  # Re-raise in debug mode
        
        return render_template('errors/500.html'), 500