# run_admin.py
# -*- coding: utf-8 -*-
"""Start QuickDealr Admin App on port 5001"""
from admin_app import admin_app   # ← no socketio import
from models import init_db

if __name__ == '__main__':
    init_db()
    print("\n  QuickDealr - Admin App")
    print("  http://localhost:5001")
    print("  Login: admin / admin123\n")
    admin_app.run(debug=True, port=5001)