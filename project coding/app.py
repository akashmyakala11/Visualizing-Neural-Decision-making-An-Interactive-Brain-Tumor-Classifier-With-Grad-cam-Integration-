from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
from flask_sqlalchemy import SQLAlchemy
from config import db_path, UPLOAD_FOLDER
import tempfile


app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)

# Create a temporary notepad
temp_notepad = os.path.join(os.path.dirname(__file__), 'temp_notepad.txt')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class MRIScan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('mri_scans', lazy=True))


with app.app_context():
    db.create_all()


@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email

            with open(temp_notepad, 'w') as f:
                f.write(username)

            # Check if the user has a folder under "Users saved images"
            saved_images_folder = os.path.join(SAVED_IMAGES_FOLDER, username)
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)

            if os.path.exists(saved_images_folder):
                # Move the folder from "Users saved images" to uploads folder
                shutil.move(saved_images_folder, upload_folder)
            else:
                # Create a folder for the user under the uploads folder if it doesn't exist
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

            return redirect(url_for('main'))
        else:
            error = 'Invalid username or password'

    return render_template('login.html', error=error)




@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            error = 'Passwords do not match'
        else:
            existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing_user:
                error = 'Username or Email already taken'
            else:
                new_user = User(username=username, email=email, password=password)
                db.session.add(new_user)
                db.session.commit()

                return redirect(url_for('main'))

    return render_template('register.html', error=error)


@app.route('/main')
def main():
    if 'user_id' in session:
        user_info = {
            'username': session['username'],
            'email': session['email']
        }

        user_id = session['user_id']
        scans_uploaded = MRIScan.query.filter_by(user_id=user_id).first() is not None
        user_info['scans_uploaded'] = scans_uploaded

        return render_template('main.html', user_info=user_info)
    else:
        return redirect(url_for('login'))


import shutil

# Define the directory path for "Users saved images" folder
SAVED_IMAGES_FOLDER = os.path.join(app.root_path, 'Users saved images')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        os.remove(temp_notepad)
        # Move user's uploaded images folder to the new location
        user = User.query.get(user_id)
        if user:
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
            new_folder = os.path.join(SAVED_IMAGES_FOLDER)

            # Create "Users saved images" folder if it doesn't exist
            if not os.path.exists(new_folder):
                os.makedirs(new_folder)

            # Move the entire folder
            shutil.move(upload_folder, new_folder)

        session.clear()

    return redirect(url_for('welcome'))

@app.route('/delete_account')
def delete_account():
    if 'user_id' in session:
        user_id = session['user_id']
        os.remove(temp_notepad)
        # Delete associated MRI scans
        MRIScan.query.filter_by(user_id=user_id).delete()

        # Delete the user account
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()

            # Delete user's uploaded images
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
            shutil.rmtree(upload_folder, ignore_errors=True)

        session.clear()

    return redirect(url_for('welcome'))


@app.route('/previous_scans')
def previous_scans():
    if 'user_id' in session:
        user_id = session['user_id']

        user_scans = MRIScan.query.filter_by(user_id=user_id).all()

        unique_images = set()

        for scan in user_scans:
            unique_images.add(scan.filename)

        image_data = [{'filename': filename} for filename in unique_images]

        if not image_data:
            return jsonify({'error': 'No images found or not uploaded'}), 404

        return jsonify({'image_data': image_data})

    return jsonify({'error': 'User not logged in'}), 401


@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = session['username']

    uploaded_file = request.files.get('file')

    if not uploaded_file:
        return jsonify({'error': 'No file provided'}), 400

    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    file_path = os.path.join(upload_folder, uploaded_file.filename)
    uploaded_file.save(file_path)

    new_scan = MRIScan(filename=uploaded_file.filename, user_id=user_id)
    db.session.add(new_scan)
    db.session.commit()

    return jsonify({'message': 'File uploaded successfully'})


@app.route('/uploads/<username>/<filename>')
def uploaded_file(username, filename):
    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        return send_from_directory(upload_folder, filename)
    else:
        return jsonify({'error': 'Image not found'}), 404


@app.route('/delete_image/<username>/<filename>', methods=['DELETE'])
def delete_image(username, filename):
    if 'user_id' in session:
        user_id = session['user_id']

        image = MRIScan.query.filter_by(user_id=user_id, filename=filename).first()

        if image:
            db.session.delete(image)
            db.session.commit()
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], username, filename)
            if os.path.exists(file_path):
                os.remove(file_path)

            return jsonify({'message': 'Image deleted successfully'})
        else:
            return jsonify({'error': 'Unauthorized deletion attempt'})

    return jsonify({'error': 'User not logged in'})

@app.route('/temporary/<path:filename>')
def serve_temporary_file(filename):
    return send_from_directory('temporary', filename)

if __name__ == '__main__':
    app.run(debug=True)
