from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required


def company_permission_required(permission):
    """
    Require the logged-in company user to have
    a specific permission.

    System Administrators automatically pass
    the permission check.
    """

    def decorator(view):

        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):

            # System administrators have full access
            if current_user.is_system_admin:
                return view(*args, **kwargs)

            # User must belong to a company
            if current_user.company_id is None:
                flash(
                    "You are not assigned to a company.",
                    "danger"
                )
                return redirect(
                    request.referrer or url_for("dashboard.dashboard")
                )

            # User account must be active
            if not current_user.is_active:
                flash(
                    "Your account is currently inactive.",
                    "danger"
                )
                return redirect(
                    request.referrer or url_for("dashboard.dashboard")
                )

            # Check required permission
            if not current_user.has_permission(permission):
                flash(
                    "You do not have permission to access this page.",
                    "warning"
                )
                return redirect(
                    request.referrer or url_for("dashboard.dashboard")
                )

            return view(*args, **kwargs)

        return wrapped_view

    return decorator