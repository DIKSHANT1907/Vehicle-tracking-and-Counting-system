import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class VehicleDatabase:
    def __init__(self, db_name="vehicle_tracking.db"):
        self.db_name = db_name
        self.create_tables()

    def create_tables(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create vehicles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            exit_time TIMESTAMP,
            max_speed REAL,
            avg_speed REAL,
            total_distance REAL,
            status TEXT DEFAULT 'active'
        )
        ''')

        # Create speed_records table for detailed speed history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS speed_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            speed REAL NOT NULL,
            position_x INTEGER,
            position_y INTEGER,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (vehicle_id)
        )
        ''')

        conn.commit()
        conn.close()

    def add_user(self, username, password, email):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        hashed_password = generate_password_hash(password)
        try:
            cursor.execute('''
            INSERT INTO users (username, password, email)
            VALUES (?, ?, ?)
            ''', (username, hashed_password, email))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        finally:
            conn.close()
        return success

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result and check_password_hash(result[0], password):
            return True
        return False

    def get_user_by_username(self, username):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, username, email FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        return user

    def add_vehicle(self, vehicle_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO vehicles (vehicle_id, entry_time, status)
        VALUES (?, ?, 'active')
        ''', (vehicle_id, current_time))
        
        conn.commit()
        conn.close()

    def update_vehicle_exit(self, vehicle_id, max_speed, avg_speed, total_distance):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE vehicles 
        SET exit_time = ?, max_speed = ?, avg_speed = ?, total_distance = ?, status = 'completed'
        WHERE vehicle_id = ? AND status = 'active'
        ''', (current_time, max_speed, avg_speed, total_distance, vehicle_id))
        
        conn.commit()
        conn.close()

    def add_speed_record(self, vehicle_id, speed, position_x, position_y):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO speed_records (vehicle_id, timestamp, speed, position_x, position_y)
        VALUES (?, ?, ?, ?, ?)
        ''', (vehicle_id, current_time, speed, position_x, position_y))
        
        conn.commit()
        conn.close()

    def get_vehicle_history(self, vehicle_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM vehicles WHERE vehicle_id = ?
        ''', (vehicle_id,))
        vehicle_data = cursor.fetchone()
        
        cursor.execute('''
        SELECT * FROM speed_records WHERE vehicle_id = ? ORDER BY timestamp
        ''', (vehicle_id,))
        speed_history = cursor.fetchall()
        
        conn.close()
        return vehicle_data, speed_history

    def get_all_vehicles(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM vehicles ORDER BY entry_time DESC
        ''')
        vehicles = cursor.fetchall()
        
        conn.close()
        return vehicles

    def get_active_vehicles(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM vehicles WHERE status = 'active'
        ''')
        active_vehicles = cursor.fetchall()
        
        conn.close()
        return active_vehicles 