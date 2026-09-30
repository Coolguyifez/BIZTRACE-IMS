# app/company_admin/decorators.py

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required


def company_permission_required(permission):
    """
    Require the logged-in company user to have a specific permission.

    System Administrators automatically pass the permission check.

    IMPORTANT:
    Permission failures must NOT redirect back to the same page,
    because that can create an infinite redirect loop.
    """

    def decorator(view):

        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):

            # =====================================================
            # SYSTEM ADMINISTRATOR
            # =====================================================

            if current_user.is_system_admin:
                return view(*args, **kwargs)

            # =====================================================
            # COMPANY CHECK
            # =====================================================

            if current_user.company_id is None:

                flash(
                    "You are not assigned to a company.",
                    "danger"
                )

                return redirect(
                    url_for("auth.login")
                )

            # =====================================================
            # USER ACTIVE CHECK
            # =====================================================

            if not current_user.is_active:

                flash(
                    "Your account is currently inactive.",
                    "danger"
                )

                return redirect(
                    url_for("auth.login")
                )

            # =====================================================
            # PERMISSION CHECK
            # =====================================================

            if not current_user.has_permission(permission):

                flash(
                    "You do not have permission to access this page.",
                    "warning"
                )

                # NEVER redirect back to request.referrer here.
                #
                # If the referrer is /dashboard and the user does
                # not have view_dashboard, this would cause:
                #
                # /dashboard -> /dashboard -> /dashboard ...
                #
                # Instead return a proper 403 response.
                abort(403)

            # =====================================================
            # ACCESS GRANTED
            # =====================================================

            return view(*args, **kwargs)

        return wrapped_view

    return decorator
