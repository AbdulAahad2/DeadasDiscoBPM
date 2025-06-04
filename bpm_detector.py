import librosa
import numpy as np
import argparse
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import sys
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QFileDialog, QTextEdit
from PyQt5.QtCore import Qt

def setup_spotify_client():
    """Set up Spotify API client using environment variables or hardcoded credentials."""
    try:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            client_id = "178f7acf67e24baf9e59e879bbc4b466"
            client_secret = "e3fa86799c85420c8c86e5e2276a6f0c"
            print("Using hardcoded Spotify credentials as fallback.")
        
        if not client_id or not client_secret:
            raise ValueError("Spotify API credentials not found. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables or update hardcoded credentials.")
        
        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        print("Spotify API client initialized successfully.")
        return sp
    except Exception as e:
        print(f"Error setting up Spotify API client: {e}")
        print("Visit https://developer.spotify.com/dashboard to set up credentials.")
        return None

def search_spotify_bpm(sp, song_name):
    """Search Spotify for a song by name and return its BPM."""
    try:
        results = sp.search(q=song_name, type="track", limit=1)
        tracks = results["tracks"]["items"]
        
        if not tracks:
            print(f"No tracks found for song name: {song_name}")
            return None, f"No tracks found for '{song_name}' on Spotify."
        
        track = tracks[0]
        track_id = track["id"]
        track_name = track["name"]
        artist = track["artists"][0]["name"]
        print(f"Found track: {track_name} by {artist} (Spotify ID: {track_id})")
        
        audio_features = sp.audio_features(track_id)[0]
        if audio_features and "tempo" in audio_features:
            tempo = round(float(audio_features["tempo"]), 2)
            print(f"Spotify BPM: {tempo}")
            return tempo, f"Spotify BPM for '{track_name} by {artist}': {tempo}"
        else:
            print("No BPM data available for this track on Spotify.")
            return None, "No BPM data available on Spotify for this track."
    
    except spotipy.exceptions.SpotifyException as se:
        print(f"Spotify API error: {se}")
        error_msg = f"Spotify API error: {se}"
        if se.http_status == 403:
            error_msg = "403 Forbidden: Check your Spotify API credentials or try again later due to rate limits. Visit https://developer.spotify.com/dashboard."
            print(error_msg)
        return None, error_msg
    except Exception as e:
        print(f"Error retrieving BPM from Spotify: {e}")
        return None, f"Error retrieving BPM from Spotify: {e}"

def scan_directory_for_song(directory, song_name):
    """Scan the specified directory for an audio file matching the song name."""
    try:
        song_name_clean = re.sub(r'[^\w\s]', '', song_name.lower())
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.mp3', '.wav')):
                    file_name_clean = re.sub(r'[^\w\s]', '', os.path.splitext(file)[0].lower())
                    if song_name_clean in file_name_clean:
                        file_path = os.path.join(root, file)
                        print(f"Found matching file: {file_path}")
                        return file_path
        print(f"No matching audio file found for '{song_name}' in directory: {directory}")
        return None
    except Exception as e:
        print(f"Error scanning directory {directory}: {e}")
        return None

def detect_bpm_local(file_path):
    """Detect BPM of a local audio file using librosa."""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file {file_path} not found.")
        
        print(f"Loading audio file: {file_path}")
        y, sr = librosa.load(file_path, sr=None)
        print(f"Audio loaded successfully. Sample rate: {sr} Hz, Duration: {len(y)/sr:.2f} seconds")
        
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        
        if isinstance(tempo, np.ndarray):
            print(f"Multiple tempo values detected: {tempo}")
            tempo = float(tempo[0])
            print(f"Selecting first tempo value: {tempo}")
        
        tempo = round(tempo, 2)
        print(f"Estimated BPM (local analysis): {tempo}")
        return tempo, f"Local analysis BPM for '{file_path}': {tempo}"
    
    except Exception as e:
        print(f"Error processing audio file: {e}")
        return None, f"Error processing audio file: {e}"

class BPMDetectorApp(QMainWindow):
    """PyQt5 GUI for BPM detection."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BPM Detector for Dead as Disco")
        self.setGeometry(100, 100, 450, 350)

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Song name input
        self.song_label = QLabel("Enter Song Name (e.g., Firefly Jim Yosef):")
        self.layout.addWidget(self.song_label)
        self.song_entry = QLineEdit()
        self.song_entry.setFixedWidth(300)
        self.layout.addWidget(self.song_entry)

        # Directory selection
        self.dir_label = QLabel("Select Directory to Scan for Audio Files:")
        self.layout.addWidget(self.dir_label)
        self.dir_entry = QLineEdit()
        self.dir_entry.setFixedWidth(300)
        self.layout.addWidget(self.dir_entry)
        self.dir_button = QPushButton("Browse Directory")
        self.dir_button.clicked.connect(self.browse_directory)
        self.layout.addWidget(self.dir_button)

        # File selection
        self.file_label = QLabel("Or Select Audio File (.mp3 or .wav):")
        self.layout.addWidget(self.file_label)
        self.file_entry = QLineEdit()
        self.file_entry.setFixedWidth(300)
        self.layout.addWidget(self.file_entry)
        self.file_button = QPushButton("Browse File")
        self.file_button.clicked.connect(self.browse_file)
        self.layout.addWidget(self.file_button)

        # Get BPM button
        self.get_bpm_button = QPushButton("Get BPM")
        self.get_bpm_button.clicked.connect(self.process_bpm)
        self.layout.addWidget(self.get_bpm_button)

        # Result display
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFixedHeight(100)
        self.layout.addWidget(self.result_text)

        self.layout.addStretch()

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.dir_entry.setText(directory)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.wav)")
        if file_path:
            self.file_entry.setText(file_path)

    def process_bpm(self):
        song_name = self.song_entry.text().strip()
        directory = self.dir_entry.text().strip()
        file_path = self.file_entry.text().strip()

        if not song_name and not file_path:
            self.result_text.setText("Error: Please enter a song name or select a file.")
            print("Error: Please enter a song name or select a file.")
            return

        bpm, message = None, ""
        if file_path:
            if not file_path.lower().endswith(('.mp3', '.wav')):
                self.result_text.setText("Error: Only .mp3 and .wav files are supported.")
                print("Error: Only .mp3 and .wav files are supported.")
                return
            bpm, message = detect_bpm_local(file_path)
        else:
            sp = setup_spotify_client()
            if sp:
                bpm, message = search_spotify_bpm(sp, song_name)
            
            if bpm is None and directory:
                print(f"Spotify lookup failed, scanning directory: {directory}")
                local_file = scan_directory_for_song(directory, song_name)
                if local_file:
                    bpm, message = detect_bpm_local(local_file)

        if bpm is not None:
            self.result_text.setText(f"Use this BPM in Dead as Disco: {bpm}\n{message}")
            print(f"Use this BPM value in Dead as Disco: {bpm}")
        else:
            self.result_text.setText(f"Failed to find BPM.\n{message}")
            print("Failed to find BPM. Try a different song name, directory, or local file.")

def main():
    # Set up argument parser for command-line usage
    parser = argparse.ArgumentParser(description="Detect BPM of a song for Dead as Disco game, prioritizing Spotify or scanning a directory.")
    parser.add_argument('--song', help="Name of the song to search for BPM on Spotify (e.g., 'Firefly Jim Yosef')")
    parser.add_argument('--filename', help="Path to the audio file (.mp3 or .wav) for local analysis")
    parser.add_argument('--directory', help="Directory to scan for audio files (e.g., 'C:/Music')")
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no arguments, launch GUI
    if not args.song and not args.filename and not args.directory:
        app = QApplication(sys.argv)
        window = BPMDetectorApp()
        window.show()
        sys.exit(app.exec_())
    
    # Validate input
    if args.filename and (args.song or args.directory):
        print("Error: Provide either --filename or (--song and/or --directory), not both.")
        return
    
    bpm, message = None, ""
    if args.filename:
        if not args.filename.lower().endswith(('.mp3', '.wav')):
            print("Error: Only .mp3 and .wav files are supported.")
            return
        bpm, message = detect_bpm_local(args.filename)
    else:
        if not args.song:
            print("Error: Provide a --song name when using --directory.")
            return
        sp = setup_spotify_client()
        if sp:
            bpm, message = search_spotify_bpm(sp, args.song)
        
        if bpm is None and args.directory:
            print(f"Spotify lookup failed, scanning directory: {args.directory}")
            local_file = scan_directory_for_song(args.directory, args.song)
            if local_file:
                bpm, message = detect_bpm_local(local_file)
    
    if bpm is not None:
        print(f"Use this BPM value in Dead as Disco: {bpm}")
        print(message)
    else:
        print("Failed to find BPM. Try a different song name, directory, or local file.")
        print(message)

if __name__ == "__main__":
    main()