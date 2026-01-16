"""
Connection Monitor - Track Socket.IO disconnects and their timing

Run this alongside your Flask app to monitor connection patterns
"""

import re
from datetime import datetime
from collections import defaultdict

class ConnectionMonitor:
    def __init__(self):
        self.connections = []
        self.disconnects = []
        self.websocket_upgrades = []
        self.user_sessions = defaultdict(list)

    def parse_log_line(self, line):
        """Parse a log line and extract connection info"""
        timestamp_match = re.search(r'\[(.*?)\]', line)
        timestamp = timestamp_match.group(1) if timestamp_match else None

        # Track connections
        if "Client connected!" in line:
            session_match = re.search(r'Session ID: (\S+)', line)
            if session_match:
                self.connections.append({
                    'time': timestamp,
                    'session_id': session_match.group(1),
                    'type': 'connect'
                })

        # Track disconnects
        if "Client disconnected!" in line:
            session_match = re.search(r'Session ID: (\S+)', line)
            if session_match:
                self.disconnects.append({
                    'time': timestamp,
                    'session_id': session_match.group(1),
                    'type': 'disconnect'
                })

        # Track WebSocket upgrades
        if "transport=websocket" in line and "HTTP/1.1" in line:
            time_match = re.search(r'200 0 ([\d.]+)', line)
            if time_match:
                duration = float(time_match.group(1))
                self.websocket_upgrades.append({
                    'time': timestamp,
                    'duration': duration
                })

        # Track user activity
        if "User" in line and "connected" in line:
            user_match = re.search(r'User (\S+) connected', line)
            if user_match:
                username = user_match.group(1)
                self.user_sessions[username].append({
                    'time': timestamp,
                    'action': 'connect'
                })
        elif "User" in line and "disconnected" in line:
            user_match = re.search(r'User (\S+) disconnected', line)
            if user_match:
                username = user_match.group(1)
                self.user_sessions[username].append({
                    'time': timestamp,
                    'action': 'disconnect'
                })

    def analyze(self):
        """Analyze connection patterns"""
        print("=" * 80)
        print("CONNECTION ANALYSIS")
        print("=" * 80)

        print(f"\nTotal Connections: {len(self.connections)}")
        print(f"Total Disconnects: {len(self.disconnects)}")
        print(f"WebSocket Upgrades: {len(self.websocket_upgrades)}")

        if self.websocket_upgrades:
            avg_upgrade_time = sum(ws['duration'] for ws in self.websocket_upgrades) / len(self.websocket_upgrades)
            max_upgrade_time = max(ws['duration'] for ws in self.websocket_upgrades)
            min_upgrade_time = min(ws['duration'] for ws in self.websocket_upgrades)

            print(f"\nWebSocket Upgrade Times:")
            print(f"  Average: {avg_upgrade_time:.2f} seconds")
            print(f"  Max: {max_upgrade_time:.2f} seconds")
            print(f"  Min: {min_upgrade_time:.2f} seconds")

            if avg_upgrade_time > 5:
                print(f"\n⚠️  WARNING: WebSocket upgrades are taking {avg_upgrade_time:.0f}s on average!")
                print("   Normal WebSocket upgrades should complete in under 1 second.")
                print("   This is likely causing your disconnects.")
                print("\n   RECOMMENDATION: Use TEST 2 (polling_only) from socketio_test_configs.py")

        print(f"\nUser Connection Patterns:")
        for username, sessions in self.user_sessions.items():
            connects = sum(1 for s in sessions if s['action'] == 'connect')
            disconnects = sum(1 for s in sessions if s['action'] == 'disconnect')
            print(f"  {username}: {connects} connects, {disconnects} disconnects")

            if disconnects > 2:
                print(f"    ⚠️  {username} has disconnected {disconnects} times - connection unstable")


# Example usage with your log
if __name__ == "__main__":
    # Paste your logs here as a multiline string
    sample_log = """
CoopPuzzle: Broadcasting progress: {'team_1': {'pieces_locked': 4, 'total_pieces': 25, 'percentage': 16.0}}
Socket.IO: Client disconnected! Session ID: -ihzMxwp4R_1KywbAAAT
Socket.IO: Client disconnected! Session ID: bXvsKR8QSixA9vOkAAAV
Socket.IO: User Kai disconnected
192.168.178.75 - - [24/Dec/2025 21:52:34] "GET /socket.io/?EIO=4&transport=websocket&sid=GPQ0mJtPaWb0W0DXAAAI HTTP/1.1" 200 0 71.028684
192.168.178.75 - - [24/Dec/2025 21:52:34] "GET /socket.io/?EIO=4&transport=websocket&sid=JIGEuBzS3c1hEV1bAAAS HTTP/1.1" 200 0 48.610806
Socket.IO: Client connected! Session ID: g2Le_rfJ_d-NGCOgAAAX
Socket.IO: Client connected! Session ID: tOv5O9JRgOFnyI1BAAAZ
Socket.IO: User Kai connected
Socket.IO: Client disconnected! Session ID: NF3Hi-6zrrOnd8OBAAAJ
Socket.IO: User admin disconnected
Socket.IO: Client connected! Session ID: 2Zs16Zl1bG3kVoeRAAAb
Socket.IO: User admin connected
    """

    monitor = ConnectionMonitor()
    for line in sample_log.split('\n'):
        monitor.parse_log_line(line)

    monitor.analyze()
