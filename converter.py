import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import tidalapi
import spotipy
from spotipy.oauth2 import SpotifyOAuth


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Spotify to Tidal Converter")
        self.geometry("600 x 500")
        
        # UI Elements
        tk.Label(self, text="Spotify Client ID:").pack(anchor="w", padx=10, pady=(10, 0))
        self.client_id_entry = tk.Entry(self, width=60)
        self.client_id_entry.pack(padx=10, fill="x")

        tk.Label(self, text="Spotify Client Secret:").pack(anchor="w", padx=10, pady=(5, 0))
        self.client_secret_entry = tk.Entry(self, width=60, show="*")
        self.client_secret_entry.pack(padx=10, fill="x")

        tk.Label(self, text="Spotify Redirect URI:").pack(anchor="w", padx=10, pady=(5, 0))
        self.redirect_uri_entry = tk.Entry(self, width=60)
        self.redirect_uri_entry.insert(0, "http://127.0.0.1:9090")
        self.redirect_uri_entry.pack(padx=10, fill="x")

        self.start_button = tk.Button(self, text="Start Transfer", command=self.start_conversion_thread, bg="#1DB954", fg="white")
        self.start_button.pack(pady=15)

        tk.Label(self, text="Logs:").pack(anchor="w", padx=10)
        self.log_area = scrolledtext.ScrolledText(self, state="disabled", height=15)
        self.log_area.pack(padx=10, pady=(0, 10), fill="both", expand=True)

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
            messagebox.showerror("Fehler", "Bitte alle Spotify Credentials ausfüllen!")
            return

        self.start_button.config(state="disabled")
        threading.Thread(target=self.run_conversion, args=(c_id, c_secret, r_uri), daemon=True).start()

    def run_conversion(self, client_id, client_secret, redirect_uri):
        try:
            self.log("Initialisiere Tidal Login...")
            session = tidalapi.Session()
            session.login_oauth_simple()
            user = session.user
            self.log(f"Tidal Login erfolgreich für User: {user.id}")

            self.log("Initialisiere Spotify Login...")
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="playlist-read-private user-library-read"
            ))

            # Playlists abrufen
            playlists = []
            results = sp.current_user_playlists(limit=50)
            while results:
                playlists.extend(results['items'])
                results = sp.next(results) if results['next'] else None

            self.log(f"Gefundene Spotify Playlists: {len(playlists)}")

            for playlist in playlists:
                p_name = playlist['name']
                p_id = playlist['id']
                self.log(f"\n--- Verarbeite Playlist: {p_name} ---")

                new_playlist = user.create_playlist(p_name, description="Imported from Spotify")
                
                # Tracks der Playlist abrufen mit sauberem Paging
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
                        album = track['album']['name'] if track.get('album') else ""

                        # Tidal Suche
                        search_results = session.search(f"{title} {artist}", models=[tidalapi.media.Track], limit=10)
                        found_track_id = None

                        for t_item in search_results.get('tracks', []):
                            # Einfaches Matching
                            if (artist.lower() in t_item.artist.name.lower() or 
                                t_item.artist.name.lower() in artist.lower()):
                                found_track_id = t_item.id
                                break

                        if found_track_id:
                            new_playlist.add([str(found_track_id)])
                            tracks_added += 1
                        else:
                            self.log(f"Nicht gefunden: {title} - {artist}")
                            tracks_failed += 1

                    track_results = sp.next(track_results) if track_results['next'] else None

                self.log(f"Fertig mit '{p_name}': {tracks_added} hinzugefügt, {tracks_failed} fehlgeschlagen.")

            self.log("\n=== Konvertierung abgeschlossen! ===")

        except Exception as e:
            self.log(f"Fehler aufgetreten: {str(e)}")
        finally:
            self.start_button.config(state="normal")


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()


