#!/usr/bin/env python3
"""Initialize the database and create an initial admin/teacher user.

Run once on first setup:
    python init_db.py

For subsequent updates (new features/columns) run instead:
    flask db upgrade
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_migrate import upgrade
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Apply all pending migrations (creates tables on first run too)
    upgrade()
    print("Database schema up to date.")

    # Check if admin user already exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            role='teacher',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: username='admin', password='admin123'")
        print("IMPORTANT: Change the password after first login!")
    else:
        print("Admin user already exists.")

    print("Initialization complete.")
