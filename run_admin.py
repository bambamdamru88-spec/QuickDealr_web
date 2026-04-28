import os
from admin_app import admin_app as app, socketio

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)