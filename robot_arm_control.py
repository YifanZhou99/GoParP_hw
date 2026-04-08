#!/usr/bin/env python3
"""
Robot Arm Control Script
Extracted from curl command for ESP8266 web interface
Supports X, Y, Z positioning + B (base rotation) and E (end effector)
"""

import requests
import time
import logging
import json
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RobotArmController:
    """Control the robot arm via ESP8266 web interface"""
    
    def __init__(self, host: str = "192.168.1.1", port: int = 80, session_id: Optional[str] = None):
        """
        Initialize the robot arm controller
        
        Args:
            host: IP address of ESP8266
            port: Port number (default 80)
            session_id: Session cookie ID for authentication
        """
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.current_position = {}
        
        # Set default headers (extracted from curl)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': f'{self.base_url}/index.html',
            'Priority': 'u=0'
        })
        
        # Set session cookie if provided
        if session_id:
            self.session.cookies.set('SessionID_R3', session_id)
    
    def send_command(self, command: str, x: str = "?", y: str = "?", z: str = "?", 
                     b: str = "?", e: str = "?", speed: int = 75, delay_ms: int = 2000, 
                     filename: str = "H.txt") -> Dict[str, Any]:
        """
        Send a command to the robot arm
        
        Args:
            command: Command type (e.g., "XYZ" for XYZ positioning)
            x, y, z: Position coordinates (use "?" for current position)
            b: Base rotation (use "?" for current)
            e: End effector/wrist angle (use "?" for current)
            speed: Movement speed (default 75)
            delay_ms: Delay in milliseconds after command
            filename: Optional filename reference
            
        Returns:
            Dict with response data: {"X": float, "Y": float, "Z": float, "B": float, "E": float, "Cmd": int}
            
        Example:
            controller.send_command("XYZ", x="100", y="50", z="150", speed=75)
        """
        # Construct the command string: "XYZ ?,?,?,?,75;delay 2000;H.txt"
        cmd_string = f"{command} {x},{y},{z},{b},{e},{speed};delay {delay_ms};{filename}"
        
        # Build URL - command goes directly in URL path, not as query param
        # Format: /cmd?COMMAND%20param1,param2,...&time=...
        url = f"{self.base_url}/cmd?{cmd_string}&time={int(time.time() * 1000)}"
        
        logger.info(f"Sending command: {cmd_string}")
        logger.debug(f"Full URL: {url}")
        
        try:
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            logger.info(f"Response status: {response.status_code}")
            
            # Parse JSON response
            try:
                data = response.json()
                self.current_position = data
                logger.info(f"Arm position: X={data.get('X')}, Y={data.get('Y')}, Z={data.get('Z')}, B={data.get('B')}, E={data.get('E')}")
                return data
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON response: {response.text[:100]}")
                return {"error": "Invalid JSON response"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send command: {e}")
            raise
    
    def move_xyz(self, x: str = "?", y: str = "?", z: str = "?", 
                 b: str = "?", e: str = "?", speed: int = 75, delay_ms: int = 2000) -> Dict[str, Any]:
        """
        Move arm to XYZ coordinates
        
        Args:
            x, y, z: Coordinates (use "?" to keep current position)
            b: Base rotation (use "?" to keep current)
            e: End effector angle (use "?" to keep current)
            speed: Movement speed (default 75)
            delay_ms: Delay after movement in milliseconds
            
        Returns:
            Dict with response data
        """
        return self.send_command("XYZ", x=x, y=y, z=z, b=b, e=e, speed=speed, delay_ms=delay_ms)
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get current arm position
        
        Returns:
            Dict with current position: {"X": float, "Y": float, "Z": float, "B": float, "E": float}
        """
        return self.current_position
    
    def head_hammer(self, repeats: int = 1, speed: int = 100) -> None:
        """
        Execute head hammer motion - quick downward strike followed by recovery
        
        Start pose: E=55, B=33, Z=37, Y=116, X=103
        End pose (hammer down): E=91, B=33, Z=164, Y=116, X=103
        Duration: 0.5 seconds per strike
        
        Args:
            repeats: Number of hammer strikes to perform (default 1)
            speed: Movement speed (default 100 for fast movement)
        """
        start_pos = {"x": "103", "y": "116", "z": "37", "b": "33", "e": "55"}
        hammer_pos = {"x": "103", "y": "116", "z": "164", "b": "33", "e": "91"}
        
        # 0.5 second duration = 500ms delay
        hammer_duration = 500
        
        logger.info(f"Head Hammer: Starting {repeats} strike(s)")
        
        for strike in range(repeats):
            logger.info(f"Head Hammer: Strike {strike + 1}/{repeats}")
            
            # Move to start position
            logger.debug("Moving to start position...")
            self.move_xyz(
                x=start_pos["x"], 
                y=start_pos["y"], 
                z=start_pos["z"],
                b=start_pos["b"],
                e=start_pos["e"],
                speed=speed,
                delay_ms=200
            )
            time.sleep(0.3)
            
            # Execute hammer strike (move down quickly)
            logger.debug("Executing hammer strike...")
            self.move_xyz(
                x=hammer_pos["x"],
                y=hammer_pos["y"],
                z=hammer_pos["z"],
                b=hammer_pos["b"],
                e=hammer_pos["e"],
                speed=speed,
                delay_ms=hammer_duration
            )
            #time.sleep(hammer_duration / 1000 + 0.2)
        
        logger.info("Head Hammer: Complete!")


def main():
    """
    Example usage of the RobotArmController
    """
    print("\n" + "="*60)
    print("ROBOT ARM CONTROL - FUNCTIONAL TEST")
    print("="*60)
    
    # Initialize controller with session ID
    controller = RobotArmController(
        host="192.168.1.1",
        port=80,
        session_id="JfLiwMiyU6zz802mJi48Ylw1N7MfGV1n4t8lEfa0XignprdBtBNK4KIgM4PG449tCx90icNy8dzppew0f9AFxquIq80hSFdD0bylfK400XC80NmdYoOnONbugA0QwSH"
    )
    
    # Example 1: Get current position (send command with all "?")
    print("\n[Example 1] Getting current arm position...")
    try:
        #pos = controller.move_xyz()
        print(f"  Current Position: X={pos.get('X')}, Y={pos.get('Y')}, Z={pos.get('Z')}")
        print(f"                    B={pos.get('B')} (base), E={pos.get('E')} (end effector)")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Example 2: Move to specific coordinates
    print("\n[Example 2] Moving to coordinates X=100, Y=50, Z=150...")
    try:
        #pos = controller.move_xyz(x="100", y="50", z="150", speed=75, delay_ms=2000)
        print(f"  Response: {pos}")
        print(f"  Waiting for movement...")
        time.sleep(2.5)
    except Exception as e:
        print(f"  Error: {e}")
    
    # Example 3: Move with base rotation and end effector
    print("\n[Example 3] Moving with base rotation and end effector...")
    try:
        #pos = controller.move_xyz(x="120", y="80", z="170", b="45", e="90", speed=75)
        print(f"  Response: {pos}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Example 4: Head Hammer
    print("\n[Example 4] Executing head hammer strike...")
    try:
        controller.head_hammer(repeats=1, speed=100)
        print(f"  Head hammer complete!")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n" + "="*60)
    print("Ready to integrate with monitor_fsr.py!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
