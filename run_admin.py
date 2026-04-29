import os
from admin_app import admin_app as app, socketio
from models import init_db

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)