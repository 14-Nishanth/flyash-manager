from functools import wraps
from flask import request, redirect, url_for, flash, jsonify
from flask_login import current_user

def role_required(*allowed_roles):
    """
    Role-based Access Control (RBAC) decorator.
    Restricts route access to specified roles. Owner and Admin always have full access.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            user_role = (current_user.role or 'staff').lower()
            allowed = [r.lower() for r in allowed_roles]
            
            # Superuser access for owner and admin
            if user_role in ['owner', 'admin'] or user_role in allowed:
                return f(*args, **kwargs)
            
            flash('⛔ Access Denied: Your account role does not have permission to perform this action.', 'error')
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
                return jsonify({'error': 'Forbidden: Insufficient role permissions'}), 403
            return redirect(url_for('dashboard.index')), 403
        return decorated_function
    return decorator
