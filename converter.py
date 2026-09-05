import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import webbrowser
import tidalapi
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Voreingestellte Standard-Werte
DEFAULT_REDIRECT_URI = "http://127.0.0.1:9090"
SPOTIFY_DEV_URL = "https://developer.spotify.com/dashboard"


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Spotify to Tidal Converter")
        self.geometry("620x720")
        
        # Header / Anleitung
        header_frame = tk.LabelFrame(self, text=" Anleitung: Spotify API Keys erstellen ", padx=10, pady=10)
        header_frame.pack(padx=10, pady=10, fill="x")

        instructions = (
            "1. Klicke auf 'Spotify Dashboard öffnen' und melde dich an.\n"
            "2. Klicke auf 'Create App'.\n"
            "3. Gib einen beliebigen Namen ein und trage unter 'Redirect URIs':\n"
            f"   {DEFAULT_REDIRECT_URI} ein.\n"
            "4. Speichere und kopiere 'Client ID' und 'Client Secret' hierher."
        )
        tk.Label(header_frame, text=instructions, justify="left", anchor="w").pack(fill="x")
        
        btn_open_dashboard = tk.Button(
            header_frame, 
            text="🔗 Spotify Dashboard öffnen", 
            command=self.open_spotify_dashboard,
            fg="#1DB954",
            cursor="hand2"
        )
        btn_open_dashboard.pack(anchor="w", pady=(5, 0))

        # Inputs Frame
        input_frame = tk.Frame(self, padx=10, pady=5)
        input_frame.pack(fill="x")

        tk.Label(input_frame, text="Spotify Client ID:").pack(anchor="w")
        self.client_id_entry = tk.Entry(input_frame, width=65)
        self.client_id_entry.pack(fill="x", pady=(0, 5))

        tk.Label(input_frame, text="Spotify Client Secret:").pack(anchor="w")
        self.client_secret_entry = tk.Entry(input_frame, width=65, show="*")
        self.client_secret_entry.pack(fill="x", pady=(0, 5))

        tk.Label(input_frame, text="Redirect URI (Standard belassen):").pack(anchor="w")
        self.redirect_uri_entry = tk.Entry(input_frame, width=65)
        self.redirect_uri_entry.insert(0, DEFAULT_REDIRECT_URI)
        self.redirect_uri_entry.pack(fill="x", pady=(0, 5))

        # Start Button
        self.start_button = tk.Button(
            self, 
            text="🚀 Transfer Starten", 
            command=self.start_conversion_thread, 
            bg="#1DB954", 
            fg="white", 
            font=("Arial", 11, "bold"),
            padx=20,
            pady=8
        )
        self.start_button.pack(pady=10)

        # Log Area
        tk.Label(self, text="Status / Logs:").pack(anchor="w", padx=10)
        self.log_area = scrolledtext.ScrolledText(self, state="disabled", height=12)
        self.log_area.pack(padx=10, pady=(0, 10), fill="both", expand=True)

    def open_spotify_dashboard(self):
        webbrowser.open(SPOTIFY_DEV_URL)

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state="disabled")

    def start_conversion_thread(self):
        c_id = self.client_id_entry.get().strip()
        c_secret = self.client_secret_entry.get().strip()
        r_uri = self.redirect_uri_entry.get().strip()

        if not c_id or not c_secret or not r_uri:
            messagebox.showerror("Fehler", "Bitte gib deine Spotify Client ID und dein Secret ein!")
            return

        self.start_button.config(state="disabled")
        threading.Thread(target=self.run_conversion, args=(c_id, c_secret, r_uri), daemon=True).start()

    def run_conversion(self, client_id, client_secret, redirect_uri):
        try:
            # 1. Spotify Login
            self.log("Starte Spotify Login...")
            self.log("--> Bitte melde dich im Browser bei Spotify an.")
            
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="playlist-read-private user-library-read",
                open_browser=True
            ))
            
            spotify_user = sp.current_user()
            self.log(f"Spotify Login erfolgreich: {spotify_user['display_name']}")

            # 2. Tidal Login
            self.log("\nStarte Tidal Login...")
            session = tidalapi.Session()
            login_url, code, future = session.login_oauth()
            
            self.log(f"--> Öffne Tidal Login im Browser...")
            webbrowser.open(f"https://{login_url}")
            
            self.log("Warte auf Bestätigung im Browser...")
            future.result()  # Blockiert bis Nutzer bestätigt
            
            user = session.user
            self.log(f"Tidal Login erfolgreich: User ID {user.id}")

            # 3. Playlists verarbeiten
            self.log("\nLade Spotify Playlists...")
            playlists = []
            results = sp.current_user_playlists(limit=50)
            while results:
                playlists.extend(results['items'])
                results = sp.next(results) if results['next'] else None

            self.log(f"Gefundene Playlists: {len(playlists)}")

            for playlist in playlists:
                p_name = playlist['name']
                p_id = playlist['id']
                self.log(f"\n--- Übertrage Playlist: {p_name} ---")

                new_playlist = user.create_playlist(p_name, description="Imported from Spotify")
                
                tracks_added = 0
                tracks_failed = 0
                
                track_results = sp.playlist_items(p_id, limit=50)
                while track_results:
                    for item in track_results['items']:
                        if not item or not item.get('track'):
                            continue

                        track = item['track']
                        title = track['name']
                        artist = track['artists'][0]['name'] if track['artists'] else ""

                        # Tidal Suche
                        search_results = session.search(f"{title} {artist}", models=[tidalapi.media.Track], limit=5)
                        found_track_id = None

                        for t_item in search_results.get('tracks', []):
                            if artist.lower() in t_item.artist.name.lower() or t_item.artist.name.lower() in artist.lower():
                                found_track_id = t_item.id
                                break

                        if found_track_id:
                            new_playlist.add([str(found_track_id)])
                            tracks_added += 1
                        else:
                            self.log(f"Nicht gefunden: {title} - {artist}")
                            tracks_failed += 1

                    track_results = sp.next(track_results) if track_results['next'] else None

                self.log(f"Fertig '{p_name}': {tracks_added} hinzugefügt, {tracks_failed} gefehlt.")

            self.log("\n=== Übertragung vollständig abgeschlossen! ===")

        except Exception as e:
            self.log(f"\nFehler aufgetreten: {str(e)}")
        finally:
            self.start_button.config(state="normal")


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
