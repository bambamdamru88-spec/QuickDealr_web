# -*- coding: utf-8 -*-
"""Start QuickDealr User App on port 5000"""
from user_app import user_app, socketio
from models import init_db

if __name__ == '__main__':
    init_db()
    print("\n  QuickDealr - User App (Buyers & Sellers)")
    print("  http://localhost:5000")
    print("  Register a buyer or seller account to get started\n")
    socketio.run(user_app, debug=True, port=5000, allow_unsafe_werkzeug=True)
