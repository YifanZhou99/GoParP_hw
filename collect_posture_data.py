#!/usr/bin/env python3
"""
FSR Posture Data Collection Script
Collects pressure sensor data for two postures (normal and cross-legged) with user information.
"""

import serial
import subprocess
import sys
import time
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

PORT = "/dev/ttyACM0"
BAUD = 9600
SOUND_FILE = "/home/yifzhou/Arduino/media/parp_sound.mp3"
DATA_DIR = "/home/yifzhou/Arduino/data"
COLLECTION_DURATION = 30  # seconds


def play_sound(sound_path):
    """Play sound file using mpg123."""
    try:
        subprocess.Popen(
            ["mpg123", "-q", sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("⚠️  mpg123 not found. Skipping sound playback.")


def check_serial_connection():
    """Check if serial port is available."""
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        ser.close()
        return True
    except serial.SerialException as e:
        print(f"❌ Could not open port {PORT}: {e}")
        return False


def get_next_id():
    """Get the next chronological ID by scanning data directory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Find all files with pattern like "001_*" or "123_*"
    pattern = re.compile(r"^(\d{3})_")
    existing_ids = set()
    
    for filename in os.listdir(DATA_DIR):
        match = pattern.match(filename)
        if match:
            existing_ids.add(int(match.group(1)))
    
    if not existing_ids:
        return "001"
    
    next_id = max(existing_ids) + 1
    return f"{next_id:03d}"


def collect_data_for_period(ser, duration=COLLECTION_DURATION):
    """
    Collect FSR data for the specified duration.
    Returns list of tuples: (relative_timestamp, fsr1, fsr2, fsr3, fsr4, fsr5)
    Displays sensor readings every 1 second for real-time progress visualization.
    """
    data_buffer = []
    start_time = time.time()
    end_time = start_time + duration
    last_display_time = start_time
    last_fsr_values = None
    
    print(f"⏱️  Collecting data for {duration} seconds...")
    print("Sensor readings (updated every 1 second):\n")
    
    while time.time() < end_time:
        try:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                
                # Parse line: "FSR1: X  FSR2: Y  FSR3: Z  FSR4: W  FSR5: V"
                match = re.search(
                    r"FSR1:\s*(\d+)\s+FSR2:\s*(\d+)\s+FSR3:\s*(\d+)\s+FSR4:\s*(\d+)\s+FSR5:\s*(\d+)",
                    line,
                )
                
                if match:
                    relative_time = time.time() - start_time
                    fsr_values = tuple(map(int, match.groups()))
                    data_buffer.append((relative_time, *fsr_values))
                    last_fsr_values = fsr_values
                    
                    # Display readings every 1 second
                    current_time = time.time()
                    elapsed_seconds = int(current_time - start_time)
                    if current_time - last_display_time >= 1.0:
                        print(
                            f"  [{elapsed_seconds:02d}s] "
                            f"FSR1:{fsr_values[0]:4d}  "
                            f"FSR2:{fsr_values[1]:4d}  "
                            f"FSR3:{fsr_values[2]:4d}  "
                            f"FSR4:{fsr_values[3]:4d}  "
                            f"FSR5:{fsr_values[4]:4d}"
                        )
                        last_display_time = current_time
        except Exception as e:
            print(f"⚠️  Error parsing data: {e}")
            continue
    
    # Display final reading if not already shown
    if data_buffer:
        elapsed_seconds = int(time.time() - start_time)
        if elapsed_seconds > int(last_display_time - start_time):
            last_values = data_buffer[-1][1:]
            print(
                f"  [{elapsed_seconds:02d}s] "
                f"FSR1:{last_values[0]:4d}  "
                f"FSR2:{last_values[1]:4d}  "
                f"FSR3:{last_values[2]:4d}  "
                f"FSR4:{last_values[3]:4d}  "
                f"FSR5:{last_values[4]:4d}"
            )
    
    print()  # Blank line after readings
    return data_buffer


def save_csv(filepath, data):
    """Save data to CSV file."""
    with open(filepath, "w") as f:
        f.write("timestamp,fsr1,fsr2,fsr3,fsr4,fsr5\n")
        for row in data:
            timestamp = row[0]
            fsr_values = row[1:]
            f.write(f"{timestamp:.3f}," + ",".join(map(str, fsr_values)) + "\n")


def save_metadata(filepath, metadata):
    """Save metadata to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def get_user_info():
    """Collect user information from input."""
    print("\n=== User Information ===")
    
    # Basic info collected earlier, now collect additional info
    gender = input("Gender (M/F/Other): ").strip().upper()
    
    while True:
        try:
            height = float(input("Height (cm): ").strip())
            break
        except ValueError:
            print("Please enter a valid number.")
    
    while True:
        try:
            weight = float(input("Weight (kg): ").strip())
            break
        except ValueError:
            print("Please enter a valid number.")
    
    while True:
        try:
            age = int(input("Age: ").strip())
            break
        except ValueError:
            print("Please enter a valid integer.")
    
    while True:
        try:
            score = int(input("Posture comfort score (1-5, 1=unhealthy, 5=healthy): ").strip())
            if 1 <= score <= 5:
                break
            else:
                print("Please enter a number between 1 and 5.")
        except ValueError:
            print("Please enter a valid integer.")
    
    return {
        "gender": gender,
        "height_cm": height,
        "weight_kg": weight,
        "age": age,
        "posture_score": score,
    }


def display_statistics(normal_data, cross_data):
    """Display collection statistics."""
    print("\n=== Data Collection Statistics ===")
    
    normal_count = len(normal_data)
    cross_count = len(cross_data)
    
    print(f"Normal posture samples: {normal_count}")
    print(f"Cross-legged posture samples: {cross_count}")
    
    if normal_data:
        normal_duration = normal_data[-1][0] - normal_data[0][0]
        print(f"Normal posture duration: {normal_duration:.2f}s")
    
    if cross_data:
        cross_duration = cross_data[-1][0] - cross_data[0][0]
        print(f"Cross-legged posture duration: {cross_duration:.2f}s")


def main():
    print("╔════════════════════════════════════════╗")
    print("║   FSR Posture Data Collection System   ║")
    print("╚════════════════════════════════════════╝\n")
    
    # Phase 1: Initialize & get user name
    print("=== Phase 1: Initialization ===")
    user_name = input("Enter user name: ").strip()
    if not user_name:
        user_name = "Unknown"
    
    print(f"✓ User name: {user_name}")
    
    # Check serial connection
    print("Checking serial connection...")
    if not check_serial_connection():
        sys.exit(1)
    print("✓ Serial connection OK")
    
    input("\nPress ENTER to begin collection (ensure user is sitting normally)...")
    
    # Open serial connection
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"❌ Could not open port {PORT}: {e}")
        sys.exit(1)
    
    # Phase 2: Collect normal posture data
    print("\n=== Phase 2: Normal Posture Collection (30s) ===")
    normal_data = collect_data_for_period(ser)
    play_sound(SOUND_FILE)
    print("✓ Done! (Collection ended with sound signal)")
    
    # Phase 3: Collect cross-legged posture data
    print("\n=== Phase 3: Cross-Legged Posture Collection (30s) ===")
    input("Stand up and sit down again in cross-legged position. Press ENTER to start...")
    cross_data = collect_data_for_period(ser)
    play_sound(SOUND_FILE)
    print("✓ Done! (Collection ended with sound signal)")
    
    ser.close()
    
    # Phase 4: Collect user info and generate files
    print("\n=== Phase 4: User Information & File Generation ===")
    user_info = get_user_info()
    
    # Display statistics
    display_statistics(normal_data, cross_data)
    
    # Get next ID
    user_id = get_next_id()
    print(f"\n✓ Assigned ID: {user_id}")
    
    # Generate filenames
    base_name = f"{user_id}_{user_name}"
    normal_filename = f"{base_name}_normal.csv"
    cross_filename = f"{base_name}_cross.csv"
    metadata_filename = f"{base_name}_metadata.json"
    
    normal_filepath = os.path.join(DATA_DIR, normal_filename)
    cross_filepath = os.path.join(DATA_DIR, cross_filename)
    metadata_filepath = os.path.join(DATA_DIR, metadata_filename)
    
    # Save CSV files
    save_csv(normal_filepath, normal_data)
    save_csv(cross_filepath, cross_data)
    print(f"✓ Saved: {normal_filename}")
    print(f"✓ Saved: {cross_filename}")
    
    # Create and save metadata
    collection_timestamp = datetime.now()
    metadata = {
        "id": user_id,
        "name": user_name,
        "gender": user_info["gender"],
        "height_cm": user_info["height_cm"],
        "weight_kg": user_info["weight_kg"],
        "age": user_info["age"],
        "posture_score": user_info["posture_score"],
        "normal_file": normal_filename,
        "cross_file": cross_filename,
        "collection_date": collection_timestamp.strftime("%Y-%m-%d"),
        "collection_time": collection_timestamp.strftime("%H:%M:%S"),
        "normal_samples": len(normal_data),
        "cross_samples": len(cross_data),
    }
    
    save_metadata(metadata_filepath, metadata)
    print(f"✓ Saved: {metadata_filename}")
    
    # Print summary
    print("\n" + "="*50)
    print("📊 SESSION SUMMARY")
    print("="*50)
    print(f"User ID: {user_id}")
    print(f"User Name: {user_name}")
    print(f"Files saved in: {DATA_DIR}/")
    print(f"  - {normal_filename}")
    print(f"  - {cross_filename}")
    print(f"  - {metadata_filename}")
    print("="*50 + "\n")
    
    print("✅ Data collection complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user.")
        sys.exit(0)
