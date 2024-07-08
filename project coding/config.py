import os

DB_FOLDER = os.path.join(os.path.dirname(__file__), 'db')
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)
db_path = os.path.join(DB_FOLDER, 'site.db')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

USERNAME = None

def set_username_in_config(username):
    global USERNAME
    USERNAME=username
    return USERNAME