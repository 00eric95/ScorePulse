"""
Error handling routes for ScorePulse AI
"""
import random
import string
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from werkzeug.exceptions import HTTPException, BadRequest, Unauthorized, Forbidden, NotFound, TooManyRequests, InternalServerError, ServiceUnavailable

errors = Blueprint('errors', __name__)

def random_string(length=8):
    """Generate a random string for transaction IDs"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_ip_address():
    """Get client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For')
    return request.remote_addr

# Custom HTTP Exception for 402 Payment Required
class PaymentRequired(HTTPException):
    """Custom exception for 402 Payment Required"""
    code = 402
    description = 'Payment required for this resource'

    def __init__(self, error_type='failed', transaction_id=None, amount=50):
        super().__init__()
        self.error_type = error_type
        self.transaction_id = transaction_id or f'TX-{random_string(8)}'
        self.amount = amount

# Custom HTTP Exception for 429 Rate Limit Exceeded
class RateLimitExceeded(HTTPException):
    """Custom exception for 429 Rate Limit Exceeded"""
    code = 429
    description = 'Rate limit exceeded'

    def __init__(self, limit='30 requests per minute', cooldown=30):
        super().__init__()
        self.limit = limit
        self.cooldown = cooldown

# Custom HTTP Exception for 503 Service Unavailable
class ServiceUnavailableCustom(HTTPException):
    """Custom exception for 503 Service Unavailable"""
    code = 503
    description = 'Service temporarily unavailable'

    def __init__(self, progress=75, start_time=None, end_time=None, message=None):
        super().__init__()
        self.progress = progress
        self.start_time = start_time or datetime.now().strftime('%H:%M UTC')
        self.end_time = end_time or (datetime.now() + timedelta(hours=2)).strftime('%H:%M UTC')
        self.message = message

# Standard HTTP error handlers
@errors.app_errorhandler(BadRequest)  # 400
def bad_request(error):
    """400 Bad Request error handler"""
    return render_template('errors/400.html'), 400

@errors.app_errorhandler(Unauthorized)  # 401
def unauthorized(error):
    """401 Unauthorized error handler"""
    return render_template('errors/401.html'), 401

@errors.app_errorhandler(PaymentRequired)  # 402
def payment_required(error):
    """402 Payment Required error handler"""
    # Parse error description to determine type
    error_type = getattr(error, 'error_type', 'failed')
    transaction_id = getattr(error, 'transaction_id', f'TX-{random_string(8)}')
    amount = getattr(error, 'amount', '50')
    
    # Also check request args
    error_type = request.args.get('error_type', error_type)
    transaction_id = request.args.get('transaction_id', transaction_id)
    amount = request.args.get('amount', amount)
    
    return render_template('errors/402.html',
                         error_type=error_type,
                         transaction_id=transaction_id,
                         amount=amount), 402

@errors.app_errorhandler(Forbidden)  # 403
def forbidden(error):
    """403 Forbidden error handler"""
    access_type = 'premium'
    
    # Determine access type from error or URL
    if hasattr(error, 'description'):
        desc = str(error.description).lower()
        if 'admin' in desc or 'administrator' in desc:
            access_type = 'admin'
        elif 'premium' in desc or 'subscription' in desc:
            access_type = 'premium'
    
    # Also check URL parameters
    access_type = request.args.get('access_type', access_type)
    
    return render_template('errors/403.html',
                         access_type=access_type), 403

@errors.app_errorhandler(NotFound)  # 404
def not_found(error):
    """404 Not Found error handler"""
    return render_template('errors/404.html'), 404

@errors.app_errorhandler(RateLimitExceeded)  # 429
def too_many_requests(error):
    """429 Too Many Requests error handler"""
    # Rate limit information
    limit = getattr(error, 'limit', '30 requests per minute')
    cooldown = getattr(error, 'cooldown', 30)
    
    # Also check request args
    limit = request.args.get('limit', limit)
    cooldown = request.args.get('cooldown', cooldown)
    
    # Calculate progress for progress bar (0-100)
    progress = min(int(request.args.get('progress', 30)), 100)
    
    return render_template('errors/429.html',
                         limit=limit,
                         cooldown=int(cooldown),
                         progress=progress,
                         ip_address=get_ip_address(),
                         endpoint=request.path), 429

@errors.app_errorhandler(InternalServerError)  # 500
def internal_server_error(error):
    """500 Internal Server Error handler"""
    error_id = f'ERR-{random_string(12)}'
    return render_template('errors/500.html',
                         error_id=error_id), 500

@errors.app_errorhandler(ServiceUnavailableCustom)  # 503
def service_unavailable(error):
    """503 Service Unavailable handler"""
    progress = getattr(error, 'progress', 75)
    start_time = getattr(error, 'start_time', '14:00 UTC')
    end_time = getattr(error, 'end_time', '16:00 UTC')
    maintenance_message = getattr(error, 'message', None)
    
    # Also check request args
    progress = request.args.get('progress', progress)
    start_time = request.args.get('start_time', start_time)
    end_time = request.args.get('end_time', end_time)
    maintenance_message = request.args.get('message', maintenance_message)
    
    return render_template('errors/503.html',
                         progress=int(progress),
                         start_time=start_time,
                         end_time=end_time,
                         maintenance_message=maintenance_message), 503

# Direct error routes for manual triggering (optional)
@errors.route('/error/402')
def payment_required_page():
    """Direct route for 402 error page"""
    error_type = request.args.get('type', 'failed')
    transaction_id = request.args.get('transaction_id', f'TX-{random_string(8)}')
    amount = request.args.get('amount', '50')
    
    return render_template('errors/402.html',
                         error_type=error_type,
                         transaction_id=transaction_id,
                         amount=amount), 402

@errors.route('/error/403')
def forbidden_page():
    """Direct route for 403 error page"""
    access_type = request.args.get('type', 'premium')
    return render_template('errors/403.html', access_type=access_type), 403

@errors.route('/error/404')
def not_found_page():
    """Direct route for 404 error page"""
    return render_template('errors/404.html'), 404

@errors.route('/error/429')
def too_many_requests_page():
    """Direct route for 429 error page"""
    limit = request.args.get('limit', '30 requests per minute')
    cooldown = request.args.get('cooldown', 30)
    progress = request.args.get('progress', 30)
    
    return render_template('errors/429.html',
                         limit=limit,
                         cooldown=int(cooldown),
                         progress=int(progress),
                         ip_address=get_ip_address(),
                         endpoint=request.path), 429

@errors.route('/error/500')
def internal_server_error_page():
    """Direct route for 500 error page"""
    error_id = f'ERR-{random_string(12)}'
    return render_template('errors/500.html', error_id=error_id), 500

@errors.route('/error/503')
def service_unavailable_page():
    """Direct route for 503 error page"""
    progress = request.args.get('progress', 75)
    start_time = request.args.get('start_time', '14:00 UTC')
    end_time = request.args.get('end_time', '16:00 UTC')
    maintenance_message = request.args.get('message', None)
    
    return render_template('errors/503.html',
                         progress=int(progress),
                         start_time=start_time,
                         end_time=end_time,
                         maintenance_message=maintenance_message), 503

# Custom exceptions for raising specific errors (compatible with the old names)
class PremiumAccessRequired(Exception):
    """Custom exception for 403 Premium Access Required"""
    status_code = 403
    
    def __init__(self, access_type='premium'):
        super().__init__()
        self.access_type = access_type

class MaintenanceMode(Exception):
    """Custom exception for 503 Maintenance Mode"""
    status_code = 503
    
    def __init__(self, progress=75, start_time=None, end_time=None, message=None):
        super().__init__()
        self.progress = progress
        self.start_time = start_time or datetime.now().strftime('%H:%M UTC')
        self.end_time = end_time or (datetime.now() + timedelta(hours=2)).strftime('%H:%M UTC')
        self.message = message