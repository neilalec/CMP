import os
import sys
from app import app
from app_core import run_server_health_check

def manual_trigger():
    # This allows the script to see the Flask app's context
    with app.app_context():
        # Replace 1 with your actual server ID from the 'servers' table
        server_id = 1 
        
        print(f"Attempting to trigger health check for Server ID: {server_id}...")
        try:
            updated_server, result = run_server_health_check(server_id)
            print("--- Success ---")
            print(f"Server Name: {updated_server['display_name']}")
            print(f"Status: {updated_server.get('last_health_status')}")
            
            # Check for potential port mismatch (Query Port vs Game Port)
            conn_addr = updated_server.get('connect_address', '')
            if ':' in conn_addr:
                port = conn_addr.split(':')[-1]
                if port.startswith('27'):
                    print(f"⚠️  WARNING: Your connect_address ({conn_addr}) looks like a QUERY port.")
                    print("   The Join button requires the GAME port (usually 7787).")
                elif port == '3001':
                    print(f"⚠️  WARNING: Your connect_address ({conn_addr}) is set to the SQUADJS BRIDGE port.")
                    print("   It should be set to the Squad Game Port (usually 7787).")

            if updated_server.get('last_health_status') == 'offline':
                 print(f"Error Detail: {updated_server.get('last_health_error')}")
            print(f"Discovered Steam ID: {updated_server['steam_lobby_id']}")
            
            if not updated_server['steam_lobby_id'] and result.get('serverInfo'):
                print("\n--- Troubleshooting ---")
                print("The bridge is healthy but isn't reporting the Steam ID.")
                print("You can find it manually here (look for 'steamid'):")
                addr = updated_server.get('connect_address', '127.0.0.1').split(':')[0]
                print(f"https://api.steampowered.com/ISteamApps/GetServersAtAddress/v1/?addr={addr}")
        except Exception as e:
            print(f"--- Failed --- \nError: {e}")

if __name__ == "__main__":
    manual_trigger()