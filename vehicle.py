import cv2
import numpy as np
import time
import math
import json
from database import VehicleDatabase

class VehicleTracker:
    def __init__(self):
        self.cap = cv2.VideoCapture("video.mp4")
        self.algo = cv2.createBackgroundSubtractorMOG2()
        
        # Initialize database
        self.db = VehicleDatabase()
        
        # Calibration constants for speed calculation
        self.PIXELS_TO_METERS = 0.1  # 10 pixels = 1 meter (adjust based on your video)
        self.FPS = 30  # Assuming 30 FPS video
        self.MIN_SPEED_THRESHOLD = 5  # Minimum speed in km/h to consider valid
        self.MAX_SPEED = 200  # Maximum speed in km/h
        
        # Speed calculation constants
        self.METERS_TO_KM = 0.001    # Convert meters to kilometers
        self.SECONDS_TO_HOURS = 3600 # Convert seconds to hours
        
        self.detect = []
        self.offset = 6
        self.counter = 0
        self.count_line_position = 500
        self.min_width_react = 80
        self.min_height_react = 80
        self.vehicle_positions = {}
        self.vehicle_data = {}
        self.total_vehicles = 0
        self.counted_vehicles = set()  # Set to track counted vehicles
        self.active_vehicles = {}  # Dictionary to track active vehicles
        
        # Speed smoothing
        self.speed_history = {}
        self.HISTORY_LENGTH = 5  # Number of frames to average speed over
        
        # Vehicle tracking
        self.tracking_threshold = 50  # Maximum distance to consider same vehicle
        self.last_vehicle_id = 0

    def center_handle(self, x, y, w, h):
        x1 = int(w / 2)
        y1 = int(h / 2)
        cx = x + x1
        cy = y + y1
        return cx, cy

    def calculate_distance(self, x1, y1, x2, y2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def convert_to_kmh(self, speed_px_per_sec):
        # Convert pixels to meters, then to kilometers, and seconds to hours
        speed_kmh = speed_px_per_sec * self.PIXELS_TO_METERS * self.METERS_TO_KM * self.SECONDS_TO_HOURS
        return min(speed_kmh, self.MAX_SPEED)  # Cap speed at MAX_SPEED

    def calculate_speed(self, prev_position, current_position, time_diff):
        if time_diff <= 0:
            return 0
            
        # Calculate distance in pixels
        distance_px = self.calculate_distance(
            prev_position[0], prev_position[1],
            current_position[0], current_position[1]
        )
        
        # Convert to meters per second
        speed_mps = (distance_px * self.PIXELS_TO_METERS) / time_diff
        
        # Convert to km/h and cap at MAX_SPEED
        speed_kmh = min(speed_mps * 3.6, self.MAX_SPEED)  # 3.6 = (3600/1000) for m/s to km/h conversion
        
        return speed_kmh

    def smooth_speed(self, vehicle_id, current_speed):
        if vehicle_id not in self.speed_history:
            self.speed_history[vehicle_id] = []
            
        self.speed_history[vehicle_id].append(current_speed)
        if len(self.speed_history[vehicle_id]) > self.HISTORY_LENGTH:
            self.speed_history[vehicle_id].pop(0)
            
        # Calculate average speed
        avg_speed = sum(self.speed_history[vehicle_id]) / len(self.speed_history[vehicle_id])
        return min(avg_speed, self.MAX_SPEED)  # Ensure speed doesn't exceed MAX_SPEED

    def check_vehicle_count(self, center_y):
        # Check if vehicle has crossed the counting line
        if center_y < self.count_line_position + self.offset and center_y > self.count_line_position - self.offset:
            return True
        return False

    def find_nearest_vehicle(self, center):
        min_dist = float('inf')
        nearest_id = None
        
        for vehicle_id, data in self.active_vehicles.items():
            dist = self.calculate_distance(
                center[0], center[1],
                data['last_position'][0], data['last_position'][1]
            )
            if dist < min_dist and dist < self.tracking_threshold:
                min_dist = dist
                nearest_id = vehicle_id
                
        return nearest_id

    def generate_frames(self):
        while True:
            ret, frame1 = self.cap.read()
            
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            grey = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(grey, (3, 3), 5)

            img_sub = self.algo.apply(blur)
            dilat = cv2.dilate(img_sub, np.ones((5, 5)))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            dilatada = cv2.morphologyEx(dilat, cv2.MORPH_CLOSE, kernel)
            dilatada = cv2.morphologyEx(dilatada, cv2.MORPH_CLOSE, kernel)
            counterShape, h = cv2.findContours(dilatada, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Draw counting line
            cv2.line(frame1, (25, self.count_line_position), (1200, self.count_line_position), (255, 127, 0), 3)

            # Update active vehicles
            current_vehicles = set()
            
            for (i, c) in enumerate(counterShape):
                (x, y, w, h) = cv2.boundingRect(c)
                validate_counter = (w >= self.min_width_react) and (h >= self.min_height_react)
                if not validate_counter:
                    continue

                cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                center = self.center_handle(x, y, w, h)
                self.detect.append(center)
                cv2.circle(frame1, center, 4, (0, 255, 0), -1)

                # Find nearest existing vehicle or create new one
                nearest_id = self.find_nearest_vehicle(center)
                
                if nearest_id is None:
                    # New vehicle detected
                    self.last_vehicle_id += 1
                    vehicle_id = f"Vehicle_{self.last_vehicle_id}"
                    self.active_vehicles[vehicle_id] = {
                        'last_position': center,
                        'last_time': time.time(),
                        'speed': 0,
                        'max_speed': 0,
                        'total_distance': 0,
                        'speed_sum': 0,
                        'speed_count': 0
                    }
                    self.vehicle_data[vehicle_id] = {'speed': 0}
                    # Add new vehicle to database
                    self.db.add_vehicle(vehicle_id)
                else:
                    # Update existing vehicle
                    vehicle_id = nearest_id
                    prev_data = self.active_vehicles[vehicle_id]
                    
                    # Calculate speed
                    time_diff = time.time() - prev_data['last_time']
                    speed_kmh = self.calculate_speed(prev_data['last_position'], center, time_diff)
                    smoothed_speed = self.smooth_speed(vehicle_id, speed_kmh)
                    
                    # Update vehicle statistics
                    self.active_vehicles[vehicle_id]['max_speed'] = max(prev_data['max_speed'], smoothed_speed)
                    self.active_vehicles[vehicle_id]['speed_sum'] += smoothed_speed
                    self.active_vehicles[vehicle_id]['speed_count'] += 1
                    self.active_vehicles[vehicle_id]['total_distance'] += self.calculate_distance(
                        prev_data['last_position'][0], prev_data['last_position'][1],
                        center[0], center[1]
                    ) * self.PIXELS_TO_METERS
                    
                    # Update vehicle data
                    self.active_vehicles[vehicle_id].update({
                        'last_position': center,
                        'last_time': time.time(),
                        'speed': smoothed_speed
                    })
                    self.vehicle_data[vehicle_id] = {'speed': round(smoothed_speed, 1)}
                    
                    # Add speed record to database
                    self.db.add_speed_record(vehicle_id, smoothed_speed, center[0], center[1])
                
                current_vehicles.add(vehicle_id)

                # Check if vehicle should be counted
                if self.check_vehicle_count(center[1]) and vehicle_id not in self.counted_vehicles:
                    self.counted_vehicles.add(vehicle_id)
                    self.total_vehicles += 1

                # Display vehicle ID and speed
                speed_text = f"{vehicle_id} - Speed: {self.vehicle_data[vehicle_id]['speed']:.1f} km/h"
                cv2.putText(frame1, speed_text, (x, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Remove vehicles that are no longer detected
            for vehicle_id in list(self.active_vehicles.keys()):
                if vehicle_id not in current_vehicles:
                    # Update vehicle exit in database
                    vehicle_data = self.active_vehicles[vehicle_id]
                    avg_speed = vehicle_data['speed_sum'] / vehicle_data['speed_count'] if vehicle_data['speed_count'] > 0 else 0
                    self.db.update_vehicle_exit(
                        vehicle_id,
                        vehicle_data['max_speed'],
                        avg_speed,
                        vehicle_data['total_distance']
                    )
                    del self.active_vehicles[vehicle_id]
                    if vehicle_id in self.vehicle_data:
                        del self.vehicle_data[vehicle_id]

            # Display total vehicle count and active vehicles
            cv2.putText(frame1, f"Total Vehicles: {self.total_vehicles}", (450, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
            cv2.putText(frame1, f"Active Vehicles: {len(self.active_vehicles)}", (450, 140), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
            
            ret, buffer = cv2.imencode('.jpg', frame1)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    def get_vehicle_data(self):
        return {
            'vehicles': self.vehicle_data,
            'total_count': self.total_vehicles,
            'active_count': len(self.active_vehicles)
        }

    def __del__(self):
        self.cap.release()
        cv2.destroyAllWindows()
