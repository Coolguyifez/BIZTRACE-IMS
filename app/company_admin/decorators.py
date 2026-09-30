# app/company_admin/decorators.py

from functools import wraps
import json

from flask import redirect, url_for
from flask_login import current_user, login_required


def company_permission_required(permission):
    """
    Require the logged-in company user to have a specific permission.

    System Administrators automatically pass the permission check.

    If the user does not have the required permission,
    display a modern BizTrace IMS access-denied page
    with a dark mode / red warning design.
    """

    def decorator(view):

        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):

            # ==========================================================
            # SYSTEM ADMINISTRATOR
            # ==========================================================

            if current_user.is_system_admin:
                return view(*args, **kwargs)

            # ==========================================================
            # COMPANY CHECK
            # ==========================================================

            if current_user.company_id is None:
                return _access_denied_page(
                    message="You are not assigned to a company.",
                    redirect_endpoint="auth.login",
                    button_text="Return to Login"
                )

            # ==========================================================
            # USER ACTIVE CHECK
            # ==========================================================

            if not current_user.is_active:
                return _access_denied_page(
                    message="Your account is currently inactive.",
                    redirect_endpoint="auth.login",
                    button_text="Return to Login"
                )

            # ==========================================================
            # PERMISSION CHECK
            # ==========================================================

            if not current_user.has_permission(permission):
                return _access_denied_page(
                    message="You do not have permission to access this page.",
                    redirect_endpoint="dashboard.dashboard",
                    button_text="Return to Dashboard"
                )

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def _access_denied_page(
    message,
    redirect_endpoint,
    button_text="Return"
):
    """
    Render a modern BizTrace IMS access-denied page.

    Dark mode with red warning styling.
    """

    redirect_url = url_for(redirect_endpoint)

    safe_message = json.dumps(message)
    safe_redirect_url = json.dumps(redirect_url)

    return f"""
<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <meta
        name="theme-color"
        content="#0b0b0d"
    >

    <title>Access Restricted</title>
    
    <!-- Bootstrap -->
    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
        rel="stylesheet"
    >

    <!-- Bootstrap Icons -->
    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css"
        rel="stylesheet"
    >

    <!-- Inter -->
    <link
        rel="preconnect"
        href="https://fonts.googleapis.com"
    >

    <link
        rel="preconnect"
        href="https://fonts.gstatic.com"
        crossorigin
    >

    <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
        rel="stylesheet"
    >


    <style>

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        :root {{
            --bg: #0b0b0d;
            --card: #151518;
            --card-2: #1c1c20;
            --border: rgba(255,255,255,0.08);

            --text: #f5f5f7;
            --muted: #a1a1aa;

            --red: #ff3b30;
            --red-dark: #d70015;
            --red-soft: rgba(255, 59, 48, 0.12);

            --shadow:
                0 30px 80px rgba(0,0,0,0.45);
        }}

        html,
        body {{
            width: 100%;
            min-height: 100%;
        }}

        body {{
            min-height: 100vh;

            display: flex;
            align-items: center;
            justify-content: center;

            padding: 24px;

            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "SF Pro Display",
                "SF Pro Text",
                "Helvetica Neue",
                Arial,
                sans-serif;

            background:
                radial-gradient(
                    circle at 50% 20%,
                    rgba(255, 59, 48, 0.10),
                    transparent 35%
                ),
                linear-gradient(
                    135deg,
                    #09090b 0%,
                    #0b0b0d 50%,
                    #101013 100%
                );

            color: var(--text);

            overflow-x: hidden;
        }}

        /* ==========================================================
           BACKGROUND EFFECT
           ========================================================== */

        .background-glow {{
            position: fixed;

            width: 420px;
            height: 420px;

            top: -180px;
            right: -150px;

            background: rgba(255, 59, 48, 0.08);

            border-radius: 50%;

            filter: blur(80px);

            pointer-events: none;
        }}

        .background-glow-bottom {{
            position: fixed;

            width: 350px;
            height: 350px;

            bottom: -180px;
            left: -120px;

            background: rgba(255, 59, 48, 0.05);

            border-radius: 50%;

            filter: blur(90px);

            pointer-events: none;
        }}

        /* ==========================================================
           CONTAINER
           ========================================================== */

        .page {{
            width: 100%;
            max-width: 520px;

            position: relative;
            z-index: 2;
        }}

        /* ==========================================================
           CARD
           ========================================================== */

        .access-card {{
            position: relative;

            background:
                linear-gradient(
                    145deg,
                    rgba(30,30,34,0.96),
                    rgba(16,16,19,0.98)
                );

            border: 1px solid var(--border);

            border-radius: 28px;

            padding: 42px 38px;

            text-align: center;

            box-shadow: var(--shadow);

            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);

            animation:
                cardAppear 0.45s ease-out;
        }}

        @keyframes cardAppear {{
            from {{
                opacity: 0;
                transform: translateY(18px) scale(0.98);
            }}

            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}

        /* ==========================================================
           BRAND
           ========================================================== */

        .brand {{
            display: flex;
            align-items: center;
            justify-content: center;

            gap: 9px;

            margin-bottom: 32px;

            font-size: 18px;
            font-weight: 700;

            letter-spacing: -0.4px;
        }}

        .brand-icon {{
            width: 34px;
            height: 34px;

            display: flex;
            align-items: center;
            justify-content: center;

            border-radius: 10px;

            background: linear-gradient(
                135deg,
                #ff453a,
                #ff2d20
            );

            color: white;

            font-size: 16px;

            box-shadow:
                0 8px 25px rgba(255,59,48,0.25);
        }}

        /* ==========================================================
           WARNING ICON
           ========================================================== */

        .warning-wrapper {{
            width: 86px;
            height: 86px;

            margin: 0 auto 24px;

            display: flex;
            align-items: center;
            justify-content: center;

            border-radius: 50%;

            background: var(--red-soft);

            border: 1px solid rgba(
                255,
                59,
                48,
                0.18
            );

            animation:
                iconAppear 0.5s ease-out;
        }}

        @keyframes iconAppear {{
            from {{
                opacity: 0;
                transform: scale(0.75);
            }}

            to {{
                opacity: 1;
                transform: scale(1);
            }}
        }}

        .warning-icon {{
            width: 52px;
            height: 52px;

            display: flex;
            align-items: center;
            justify-content: center;

            border-radius: 50%;

            background: rgba(
                255,
                59,
                48,
                0.15
            );

            color: var(--red);

            font-size: 27px;
            font-weight: 800;
        }}

        /* ==========================================================
           TEXT
           ========================================================== */

        .title {{
            margin-bottom: 12px;

            font-size: 28px;
            line-height: 1.15;

            font-weight: 700;

            letter-spacing: -0.8px;

            color: var(--text);
        }}

        .subtitle {{
            max-width: 390px;

            margin: 0 auto;

            font-size: 15px;

            line-height: 1.65;

            color: var(--muted);
        }}

        /* ==========================================================
           MESSAGE
           ========================================================== */

        .message-box {{
            margin-top: 26px;

            padding: 15px 17px;

            text-align: left;

            border-radius: 14px;

            background: rgba(
                255,
                59,
                48,
                0.07
            );

            border: 1px solid rgba(
                255,
                59,
                48,
                0.14
            );

            color: #e5e5e7;

            font-size: 14px;

            line-height: 1.55;
        }}

        .message-label {{
            display: block;

            margin-bottom: 5px;

            color: var(--red);

            font-size: 11px;

            font-weight: 700;

            text-transform: uppercase;

            letter-spacing: 0.7px;
        }}

        /* ==========================================================
           BUTTON
           ========================================================== */

        .action-button {{
            width: 100%;

            display: flex;
            align-items: center;
            justify-content: center;

            gap: 9px;

            margin-top: 26px;

            min-height: 52px;

            padding: 14px 20px;

            border: none;

            border-radius: 14px;

            background: linear-gradient(
                135deg,
                #ff453a,
                #ff2d20
            );

            color: #ffffff;

            font-size: 15px;

            font-weight: 600;

            text-decoration: none;

            cursor: pointer;

            box-shadow:
                0 10px 30px
                rgba(255,59,48,0.20);

            transition:
                transform 0.2s ease,
                box-shadow 0.2s ease,
                filter 0.2s ease;
        }}

        .action-button:hover {{
            color: #ffffff;

            transform: translateY(-2px);

            filter: brightness(1.05);

            box-shadow:
                0 14px 34px
                rgba(255,59,48,0.30);
        }}

        .action-button:active {{
            transform: translateY(0);
        }}

        .arrow {{
            font-size: 18px;
            transition: transform 0.2s ease;
        }}

        .action-button:hover .arrow {{
            transform: translateX(3px);
        }}

        /* ==========================================================
           FOOTER
           ========================================================== */

        .footer {{
            margin-top: 28px;

            padding-top: 20px;

            border-top: 1px solid var(--border);

            color: #71717a;

            font-size: 12px;

            line-height: 1.5;
        }}

        .footer strong {{
            color: #a1a1aa;
        }}

        /* ==========================================================
           MOBILE
           ========================================================== */

        @media (max-width: 576px) {{

            body {{
                padding: 16px;
            }}

            .access-card {{
                padding: 34px 22px;

                border-radius: 22px;
            }}

            .brand {{
                margin-bottom: 28px;
            }}

            .warning-wrapper {{
                width: 76px;
                height: 76px;
            }}

            .warning-icon {{
                width: 46px;
                height: 46px;

                font-size: 23px;
            }}

            .title {{
                font-size: 24px;
            }}

            .subtitle {{
                font-size: 14px;
            }}
        }}

    </style>

</head>

<body>

    <div class="background-glow"></div>
    <div class="background-glow-bottom"></div>

    <main class="page">

        <section class="access-card">

            <!-- BRAND -->

            <div class="brand">

                <div class="brand-icon">
                    <i class="bi bi-bar-chart-fill"></i>
                </div>

                <span>
                    BizTrace <small><small><small class="text-danger">IMS</small></small></small>
                </span>

            </div>


            <!-- WARNING ICON -->

            <div class="warning-wrapper">

                <div class="warning-icon">
                    !
                </div>

            </div>


            <!-- TITLE -->

            <h1 class="title">
                Access Restricted
            </h1>


            <!-- DESCRIPTION -->

            <p class="subtitle">
                You don't have the required permission
                to access this section of BizTrace IMS.
            </p>


            <!-- MESSAGE -->

            <div class="message-box">

                <span class="message-label">
                    Access Notice
                </span>

                {message}

            </div>


            <!-- BUTTON -->

            <a
                href="{redirect_url}"
                class="action-button"
            >

                <span>
                    {button_text}
                </span>

                <span class="arrow">
                    →
                </span>

            </a>


            <!-- FOOTER -->

            <div class="footer">

                If you believe you should have access,
                contact your <strong>Company Administrator</strong>
                to request the required permission.

            </div>

        </section>

    </main>


    <script>

        /*
         * Optional automatic redirect protection.
         *
         * The page remains visible long enough for the user
         * to understand why access was denied.
         */

        const redirectUrl = {safe_redirect_url};

        // No automatic redirect.
        // User chooses when to return.

    </script>

</body>

</html>
"""
