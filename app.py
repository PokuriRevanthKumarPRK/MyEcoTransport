import os
import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime, timedelta
import math
import time
import hashlib

USER_DATA_FILE = "user_trips.csv"
USER_CREDENTIALS_FILE = "users.csv"


# Load user credentials
def load_users():
    if os.path.exists(USER_CREDENTIALS_FILE):
        return pd.read_csv(USER_CREDENTIALS_FILE)
    return pd.DataFrame(columns=["username", "password_hash", "email"])


# Save user credentials
def save_user(username, password, email):
    users_df = load_users()

    # Check if username already exists
    if username in users_df["username"].values:
        return False

    # Hash the password
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    # Add new user
    new_user = pd.DataFrame({
        "username": [username],
        "password_hash": [password_hash],
        "email": [email]
    })

    users_df = pd.concat([users_df, new_user], ignore_index=True)
    users_df.to_csv(USER_CREDENTIALS_FILE, index=False)
    return True


# Verify user credentials
def verify_user(username, password):
    users_df = load_users()
    if username not in users_df["username"].values:
        return False

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_hash = users_df.loc[users_df["username"] == username, "password_hash"].values[0]

    return password_hash == stored_hash


# Load trips from file
def load_trips():
    if os.path.exists(USER_DATA_FILE):
        return pd.read_csv(USER_DATA_FILE).to_dict(orient="records")
    return []


# Save trips to file
def save_trips():
    df = pd.DataFrame(st.session_state.trips)
    df.to_csv(USER_DATA_FILE, index=False)


# Calculate distance between two coordinates
def calculate_distance(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return distance


# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "trips" not in st.session_state:
    st.session_state.trips = load_trips()
if "start_location" not in st.session_state:
    st.session_state.start_location = None
    st.session_state.start_time = None
if "camera_on" not in st.session_state:
    st.session_state.camera_on = False
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "login"  # Default to login page

STATIONS = {
    "HarbourFront": (1.2850, 103.8500),
    "Outram Park": (1.2950, 103.8550),
    "Chinatown": (1.3000, 103.8500),
    "Dhoby Ghaut": (1.3050, 103.8450),
    "Clarke Quay": (1.3100, 103.8500),
    "Little India": (1.3150, 103.8550),
    "Farrer Park": (1.3200, 103.8600),
    "Boon Keng": (1.3250, 103.8550),
    "Potong Pasir": (1.3300, 103.8600),
    "Woodleigh": (1.3400, 103.8650),
    "Serangoon": (1.3500, 103.8700),
    "Kovan": (1.3550, 103.8750),
    "Hougang": (1.3600, 103.8800),
    "Buangkok": (1.3650, 103.8850),
    "Sengkang": (1.3700, 103.8900),
    "Punggol": (1.3800, 103.8950),
    "Punggol Coast": (1.3850, 103.9000),
}


# QR code scanning function with webcam
def scan_qr_webcam():
    st.write("Position the QR code in front of your webcam")

    # Handle camera state
    if not st.session_state.camera_on:
        if st.button("Start Camera"):
            st.session_state.camera_on = True
            st.rerun()
    else:
        if st.button("Stop Camera"):
            st.session_state.camera_on = False
            st.rerun()

    # Create placeholders outside the camera condition
    webcam_placeholder = st.empty()
    status_placeholder = st.empty()

    if st.session_state.camera_on:
        # Access webcam
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                status_placeholder.error("Could not access webcam. Please ensure your webcam is connected.")
                st.session_state.camera_on = False
                return None

            status_placeholder.info("Scanning for QR code...")

            # Keep scanning until a valid QR code is found or camera is stopped
            scanning_active = True
            waiting_until = None

            while st.session_state.camera_on:
                # Check if we're in waiting period
                current_time = datetime.now()
                if waiting_until is not None:
                    if current_time < waiting_until:
                        seconds_left = (waiting_until - current_time).seconds
                        status_placeholder.info(
                            f"QR code detected! Waiting for {seconds_left} seconds before resuming scan...")
                        time.sleep(0.5)  # Update less frequently during wait
                        continue
                    else:
                        waiting_until = None
                        status_placeholder.info("Resuming scan...")

                # Read a frame from the webcam
                ret, frame = cap.read()
                if not ret:
                    status_placeholder.error("Failed to grab frame from webcam")
                    time.sleep(1)
                    continue

                # Convert to grayscale for better QR code detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Try to decode QR codes in the frame only if scanning is active
                if scanning_active:
                    decoded_objects = decode(gray)
                else:
                    decoded_objects = []

                # Draw rectangle around QR codes
                for obj in decoded_objects:
                    points = obj.polygon
                    if len(points) > 4:
                        hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                        cv2.polylines(frame, [hull], True, (0, 255, 0), 3)
                    else:
                        cv2.polylines(frame, [np.array(points, dtype=np.int32)], True, (0, 255, 0), 3)

                # Display the webcam feed
                webcam_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", caption="Webcam Feed")

                # If QR code detected
                if decoded_objects:
                    station_name = decoded_objects[0].data.decode("utf-8")
                    if station_name in STATIONS:
                        status_placeholder.success(f"QR code detected: {station_name}")

                        # Set waiting time to 1 minute
                        waiting_until = current_time + timedelta(minutes=1)
                        status_placeholder.info(f"Waiting for 60 seconds before resuming scan...")

                        # Return the station name for use
                        return station_name
                    else:
                        status_placeholder.error(f"Invalid QR code: {station_name}")

                time.sleep(0.1)  # To reduce CPU usage

        except Exception as e:
            status_placeholder.error(f"Error accessing webcam: {e}")
        finally:
            # Always release the webcam when done
            if 'cap' in locals() and cap.isOpened():
                cap.release()
    else:
        status_placeholder.info("Camera is stopped. Press 'Start Camera' to begin scanning.")

    return None


# Authentication Page
def auth_page():
    st.title("MyEcoTransport")

    # Create tabs for login and signup
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        st.header("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Login", key="login_button"):
                if verify_user(username, password):
                    st.session_state.user = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    with tab2:
        st.header("Sign Up")
        new_username = st.text_input("Choose a username", key="signup_username")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Choose a password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm password", type="password", key="confirm_password")

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Sign Up", key="signup_button"):
                if not new_username or not new_email or not new_password:
                    st.error("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    if save_user(new_username, new_password, new_email):
                        st.success("Account created successfully! Please log in.")
                    else:
                        st.error("Username already exists. Please choose another.")


# Main App
def main_app():
    st.title("MyEcoTransport")
    st.write(f"Welcome, {st.session_state.user}!")

    # Create tabs for different functionalities
    tab1, tab2 = st.tabs(["Trip History", "Scan QR Code"])

    with tab1:
        if st.button("Logout", key="logout_button"):
            st.session_state.user = None
            st.rerun()

        # Show user-specific trip history
        user_trips = [trip for trip in st.session_state.trips if trip.get("username") == st.session_state.user]
        if user_trips:
            st.subheader("Your Transit History")
            df = pd.DataFrame(user_trips)
            st.dataframe(df)
            total_points = sum(trip["Points Earned"] for trip in user_trips)
            st.metric(label="Total Points", value=total_points)
            csv = df.to_csv(index=False)
            st.download_button("Download Transit History", data=csv, file_name="transit_history.csv", mime="text/csv")
        else:
            st.write("No trips recorded yet.")

    with tab2:
        if st.session_state.start_location is None:
            # First scan - Start location
            st.subheader("Start Your Trip")
            st.write("Scan the QR code at your starting station")

            start_station = scan_qr_webcam()
            if start_station:
                st.session_state.start_location = start_station
                st.session_state.start_time = datetime.now()
                st.success(f"Trip started at {start_station}")
                st.rerun()
        else:
            # Second scan - End location
            st.subheader("End Your Trip")
            st.write(
                f"Trip started at {st.session_state.start_location} at {st.session_state.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            st.write("Scan the QR code at your destination station")

            end_station = scan_qr_webcam()
            if end_station:
                end_time = datetime.now()

                # Calculate distance between stations
                start_coords = STATIONS[st.session_state.start_location]
                end_coords = STATIONS[end_station]
                distance = calculate_distance(start_coords, end_coords)

                # Calculate points (10 points per km)
                points = int(distance * 10)

                # Create new trip record
                new_trip = {
                    "username": st.session_state.user,
                    "Start Location": st.session_state.start_location,
                    "End Location": end_station,
                    "Start Time": st.session_state.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "End Time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "Distance (km)": round(distance, 2),
                    "Points Earned": points
                }

                # Add trip to records and save
                st.session_state.trips.append(new_trip)
                save_trips()

                # Reset trip state
                st.session_state.start_location = None
                st.session_state.start_time = None

                st.success(f"Trip completed! You earned {points} points for traveling {round(distance, 2)} km.")
                st.rerun()

            # Option to cancel trip
            if st.button("Cancel Trip"):
                st.session_state.start_location = None
                st.session_state.start_time = None
                st.warning("Trip canceled")
                st.rerun()


# Main app flow
if st.session_state.user:
    main_app()
else:
    auth_page()


