from flask import render_template, redirect, url_for
from flask_login import current_user, logout_user
from app.main import bp


@bp.route('/')
def index():
    if current_user.is_authenticated:
        if not current_user.is_active:
            logout_user()
            return redirect(url_for('auth.login'))
        if current_user.is_teacher():
            return redirect(url_for('teacher.dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))
