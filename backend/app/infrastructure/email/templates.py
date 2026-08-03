import html


def get_verification_html(verification_link: str) -> str:
    """Generates the HTML email body for email verification."""
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #4F46E5;">Welcome to SIET!</h2>
                <p>Thank you for signing up. Please verify your email address by clicking the button below:</p>
                <p style="margin: 30px 0;">
                    <a href="{verification_link}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Verify Email Address</a>
                </p>
                <p>If the button doesn't work, copy and paste the following URL into your browser:</p>
                <p><a href="{verification_link}">{verification_link}</a></p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">This verification link will expire in 24 hours.</p>
            </div>
        </body>
    </html>
    """

def get_reset_password_html(reset_link: str) -> str:
    """Generates the HTML email body for password resets."""
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #E11D48;">Reset Your Password</h2>
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                <p style="margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #E11D48; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Reset Password</a>
                </p>
                <p>If the button doesn't work, copy and paste the following URL into your browser:</p>
                <p><a href="{reset_link}">{reset_link}</a></p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">This password reset link will expire in 2 hours.</p>
            </div>
        </body>
    </html>
    """


def get_contact_notification_html(name: str, email: str, subject: str | None, message: str) -> str:
    """Generates the HTML email body for contact form submissions."""
    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_subject = html.escape(subject) if subject else "General Inquiry"
    safe_message = html.escape(message)

    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #0F2B5C;">New Contact Inquiry — SIET AI Lab</h2>
                <p><strong>From:</strong> {safe_name} (&lt;<a href="mailto:{safe_email}">{safe_email}</a>&gt;)</p>
                <p><strong>Subject:</strong> {safe_subject}</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;">
                <p><strong>Message:</strong></p>
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 4px; white-space: pre-wrap;">{safe_message}</div>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">Submitted via SIET News Contact Form.</p>
            </div>
        </body>
    </html>
    """
