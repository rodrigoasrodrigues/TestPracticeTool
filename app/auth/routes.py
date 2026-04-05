from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Usuário ou senha incorretos.', 'danger')
            return redirect(url_for('auth.login'))
        if not user.is_active:
            flash('Seu cadastro foi recebido e está aguardando aprovação de um professor.',
                  'warning')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        # Validate the next URL to prevent open redirect attacks
        if next_page and urlsplit(next_page).netloc == '':
            safe_next = next_page
        else:
            safe_next = url_for('main.index')
        return redirect(safe_next)
    return render_template('auth/login.html', title='Login', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        approved_teachers_count = User.query.filter_by(role='teacher', is_active=True).count()
        should_activate = form.role.data == 'teacher' and approved_teachers_count == 0

        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data,
            is_active=should_activate
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        if should_activate:
            flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        else:
            flash('Cadastro realizado com sucesso! Aguarde aprovação de um professor para '
                  'acessar o sistema.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Registrar', form=form)
