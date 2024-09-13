import os
import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# Initialize rich console
console = Console()

# Define your qBittorrent credentials
username = ""  # Replace with your qBittorrent username
password = ""  # Replace with your qBittorrent password
qb_url = "http://127.0.0.1:8080"  # Replace with your qBittorrent Web UI URL
output_dir = "/path/to/save/.torrent_files"  # Where to save the .torrent files

# Function to log out and exit the script
def logout_and_exit(session, qb_url, message):
    console.print(f"Logging out from qBittorrent Web UI due to error: {message}", style="bold bright_red")
    try:
        session.post(f"{qb_url}/api/v2/auth/logout")
    except RequestException as e:
        console.print(f"Failed to log out: {e}", style="bold bright_red")
    exit()

# Create output directory if it doesn't exist
try:
    if not os.path.exists(output_dir):
        console.print(f"Creating output directory at {output_dir}", style="bold bright_green")
        os.makedirs(output_dir)
    else:
        console.print(f"Output directory already exists at {output_dir}", style="bold yellow")
except OSError as e:
    console.print(f"Failed to create or access output directory: {e}", style="bold bright_red")
    exit()

# Create a session to persist the login
session = requests.Session()

# Log into qBittorrent
console.print("Attempting to log into qBittorrent Web UI...", style="bold bright_cyan")
login_payload = {
    'username': username,
    'password': password
}
try:
    login_response = session.post(f"{qb_url}/api/v2/auth/login", data=login_payload)
    if login_response.status_code == 200 and login_response.text == "Ok.":
        console.print("Login successful!", style="bold bright_green")
    else:
        console.print(f"Login failed: {login_response.text}", style="bold bright_red")
        exit()
except RequestException as e:
    console.print(f"Failed to connect to qBittorrent Web UI: {e}", style="bold bright_red")
    exit()

# Mapping of tracker URLs (partial matches) to their respective codes
tracker_codes = {
    "Aither.cc": "[ATH] ",
    "Upload.cx": "[ULCX] ",
    "Blutopia.cc": "[BLU] ",
    "FearNoPeer.com": "[FNP] ",
    "LST.gg": "[LST] ",
    "TheLDU.to": "[LDU] ",
    "OldToons.world": "[OTW] ",
    "TLeechReload.org": "[TL] ",
    "TorrentLeech.org": "[TL] " 
}

# Function to get the tracker code based on the tracker URL
def get_tracker_code(trackers):
    try:
        for tracker in trackers:
            for url, code in tracker_codes.items():
                if url.lower() in tracker['url'].lower():  # Case-insensitive match
                    return code
        return ""  # Return empty if no matching tracker is found
    except (KeyError, TypeError) as e:
        console.print(f"Error processing tracker information: {e}", style="bold bright_red")
        return ""

# Fetch all torrents
console.print("Fetching list of all torrents...", style="bold bright_cyan")
try:
    torrents_response = session.get(f"{qb_url}/api/v2/torrents/info")
    torrents_response.raise_for_status()
except RequestException as e:
    logout_and_exit(session, qb_url, f"Failed to fetch torrents: {e}")

# Process the torrents list
torrents = torrents_response.json()
console.print(f"Found {len(torrents)} torrents to export.", style="bold bright_green")

# Initialize the progress bar with brighter spinner and percentage
with Progress(
    TextColumn("[bold bright_cyan]{task.description}"),  # Add task description column
    SpinnerColumn(style="bold bright_cyan"),  # Brighter spinner
    BarColumn(bar_width=None, complete_style="bold bright_blue", finished_style="bold bright_green"),
    TextColumn("[bold bright_cyan]{task.percentage:>3.1f}%[/]"),  # Correctly styled percentage
    TextColumn("[progress.completed]{task.completed}/{task.total} torrents", style="bold bright_cyan"),
    console=console,
    expand=True
) as progress:
    
    total_torrents = len(torrents)
    task = progress.add_task("Exporting torrents...", total=total_torrents)

    # Loop through all torrents and download the .torrent files
    for torrent in torrents:
        try:
            torrent_hash = torrent['hash']  # Unique identifier for each torrent
            torrent_name = torrent['name']  # The name of the torrent

            # Fetch the tracker information for this torrent
            trackers_response = session.get(f"{qb_url}/api/v2/torrents/trackers", params={'hash': torrent_hash})
            trackers_response.raise_for_status()

            trackers = trackers_response.json()  # List of trackers for this torrent

            # Get the tracker code
            tracker_code = get_tracker_code(trackers)

            # Clean the torrent name to make it safe for file system usage
            torrent_name_cleaned = "".join(x for x in torrent_name if x.isalnum() or x in "._- ")

            # Append the tracker code at the beginning of the torrent name
            torrent_file_name = f"{tracker_code}{torrent_name_cleaned}"

            # Use the correct API endpoint to export the .torrent file
            torrent_file_response = session.get(f"{qb_url}/api/v2/torrents/export", params={'hash': torrent_hash})
            torrent_file_response.raise_for_status()

            # Save the .torrent file to the specified directory with the tracker code
            torrent_file_path = os.path.join(output_dir, f"{torrent_file_name}.torrent")
            with open(torrent_file_path, 'wb') as f:
                f.write(torrent_file_response.content)

        except (RequestException, KeyError, OSError) as e:
            # Enhanced error message for failed torrents
            console.print(f"[bold bright_red]Failed to download torrent: {torrent_name}[/bold bright_red]\nError: {e}", style="bold bright_red")
            continue

        # Update the progress bar
        progress.update(task, advance=1)

# Logout from qBittorrent Web UI
try:
    session.post(f"{qb_url}/api/v2/auth/logout")
    console.print("All .torrent files exported successfully.", style="bold bright_green")
except RequestException as e:
    console.print(f"Failed to log out: {e}", style="bold bright_red")