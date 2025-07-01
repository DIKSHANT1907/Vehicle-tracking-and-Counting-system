from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session, flash
import cv2
import numpy as np
import time
import math
import json
from vehicle import VehicleTracker
from database import VehicleDatabase
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key
db = VehicleDatabase()

# Initialize the vehicle tracker
tracker = VehicleTracker()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if db.verify_user(username, password):
            session['username'] = username
            return redirect(url_for('history'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if db.add_user(username, password, email):
            session['username'] = username
            return redirect(url_for('history'))
        else:
            return render_template('register.html', error='Username or email already exists')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/history')
@login_required
def history():
    # Get all vehicles from database
    vehicles = db.get_all_vehicles()
    
    # Count total and active vehicles
    total_vehicles = len(vehicles)
    active_vehicles = sum(1 for v in vehicles if v[7] == 'active')
    
    return render_template('history.html',
                         vehicles=vehicles,
                         total_vehicles=total_vehicles,
                         active_vehicles=active_vehicles)

@app.route('/video_feed')
def video_feed():
    return Response(tracker.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_vehicle_data')
def get_vehicle_data():
    return jsonify(tracker.get_vehicle_data())

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000) 