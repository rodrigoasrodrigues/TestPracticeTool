#!/usr/bin/env python3
"""Initialize the database and create an initial admin/teacher user."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    print("Database tables created.")

    # Check if admin user already exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            role='teacher'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: username='admin', password='admin123'")
        print("IMPORTANT: Change the password after first login!")
    else:
        print("Admin user already exists.")

    print("Initialization complete.")
