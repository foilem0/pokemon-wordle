import json
import logging
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import requests

POKEMON_NAME_MIN = 3
POKEMON_NAME_MAX = 10
MAX_GUESSES = 6
CACHE_DAYS = 7
API_URL = "https://pokeapi.co/api/v2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pokemon_wordle.log"),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class Pokemon:
    name: str
    original_name: str
    types: List[str]
    is_dual_type: bool
    length: int


class DatabaseManager:

    def __init__(self, db_path="pokemon_cache.db"):
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS pokemon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                original_name TEXT NOT NULL,
                types TEXT NOT NULL,
                is_dual_type BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.commit()

    def prune_cache(self, min_len: int, max_len: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM pokemon WHERE length(name) < ? OR length(name) > ?",
                (min_len, max_len),
            )
            conn.commit()

    def get_all_pokemon(self) -> List[Dict]:
        """Fetches all Pokémon from the cache that are within the valid name length."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT name, original_name, types, is_dual_type FROM pokemon
                   WHERE length(name) >= ? AND length(name) <= ?""",
                (POKEMON_NAME_MIN, POKEMON_NAME_MAX),
            )
            return [{
                "name": row[0],
                "original_name": row[1],
                "types": json.loads(row[2]),
                "is_dual_type": bool(row[3]),
            } for row in c.fetchall()]

    def save_pokemon(self, pokemon_list: List[Dict]):
        """Saves a list of Pokémon to the database using a bulk insert."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            data_to_insert = [(
                p["name"],
                p["original_name"],
                json.dumps(p["types"]),
                p["is_dual_type"],
            ) for p in pokemon_list]
            c.executemany(
                """INSERT OR REPLACE INTO pokemon 
                   (name, original_name, types, is_dual_type)
                   VALUES (?, ?, ?, ?)""",
                data_to_insert,
            )
            conn.commit()

    def is_cache_valid(self) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT updated_at FROM cache_metadata WHERE key = 'last_update'"
            )
            row = c.fetchone()
            return bool(row and datetime.now() - datetime.fromisoformat(row[0])
                        < timedelta(days=CACHE_DAYS))

    def update_cache_timestamp(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""INSERT OR REPLACE INTO cache_metadata 
                   (key, value, updated_at) VALUES ('last_update', 'complete', CURRENT_TIMESTAMP)"""
                         )
            conn.commit()


class PokeAPIClient:

    def __init__(self, base_url=API_URL):
        self.base_url = self._validate_url(base_url)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Pokemon-Wordle/1.0",
            "Accept": "application/json"
        })

    def _validate_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or "pokeapi.co" not in parsed.netloc:
            raise ValueError("Invalid PokéAPI URL")
        return url

    def _get(self, endpoint: str) -> Optional[Dict]:
        try:
            resp = self.session.get(f"{self.base_url}/{endpoint.lstrip('/')}",
                                    timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"API error on {endpoint}: {e}")
            return None

    def get_pokemon_list(self, limit=2000) -> Optional[Dict]:
        return self._get(f"pokemon?limit={limit}")

    def get_pokemon_details(self, name_or_id: str) -> Optional[Dict]:
        return self._get(f"pokemon/{name_or_id}")


class InputValidator:

    @staticmethod
    def sanitize_and_check(name: str,
                           expected_len: Optional[int] = None) -> str:
        if not isinstance(name, str):
            raise ValueError("Name must be a string")
        clean = "".join(c for c in name if c.isalnum()).upper()
        if not (POKEMON_NAME_MIN <= len(clean) <= POKEMON_NAME_MAX):
            raise ValueError(
                f"Name length must be {POKEMON_NAME_MIN}-{POKEMON_NAME_MAX} letters"
            )
        if expected_len is not None and len(clean) != expected_len:
            raise ValueError(f"Guess must be {expected_len} letters long")
        return clean


class PokemonWordle:

    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.db = DatabaseManager(self.data_dir / "pokemon_cache.db")
        self.api = PokeAPIClient()
        self.pokemon_data: List[Pokemon] = []
        self.pokemon_names_set: set[str] = set()
        self.current_pokemon: Optional[Pokemon] = None
        self.dual_type_only = False
        self.games_played = self.games_won = 0

    def _to_pokemon(self, p: Dict) -> Pokemon:
        return Pokemon(
            name=p["name"].upper(),
            original_name=p["original_name"],
            types=p["types"],
            is_dual_type=p["is_dual_type"],
            length=len(p["name"]),
        )

    def _filter_names(self, pokes: List[Dict]) -> List[Dict]:
        out = []
        for p in pokes:
            clean = p["name"].replace("-", "")
            if POKEMON_NAME_MIN <= len(clean) <= POKEMON_NAME_MAX:
                out.append({
                    "name": clean,
                    "original_name": p["name"],
                    "url": p["url"]
                })
        return out

    def load_data(self) -> bool:
        if self.db.is_cache_valid():
            cached = self.db.get_all_pokemon()
            if cached:
                self.pokemon_data = [self._to_pokemon(p) for p in cached]
                self.pokemon_names_set = {p.name for p in self.pokemon_data}
                if self.pokemon_data:
                    return True
        return self._fetch_from_api()

    def _fetch_from_api(self) -> bool:
        """Fetches all Pokémon data from the API concurrently."""
        resp = self.api.get_pokemon_list()
        if not resp:
            return False

        filtered_list = self._filter_names(resp["results"])

        def fetch_details(pokemon_info: Dict) -> Optional[Pokemon]:
            details = self.api.get_pokemon_details(
                pokemon_info["original_name"])
            if details:
                types = [
                    t["type"]["name"].capitalize() for t in details["types"]
                ]
                return Pokemon(
                    name=pokemon_info["name"].upper(),
                    original_name=pokemon_info["original_name"],
                    types=types,
                    is_dual_type=len(types) == 2,
                    length=len(pokemon_info["name"]),
                )
            return None

        processed: List[Pokemon] = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(fetch_details, filtered_list)
            processed = [p for p in results if p is not None]

        if not processed:
            return False

        self.db.save_pokemon([{
            "name": p.name,
            "original_name": p.original_name,
            "types": p.types,
            "is_dual_type": p.is_dual_type,
        } for p in processed])
        self.db.update_cache_timestamp()
        self.db.prune_cache(POKEMON_NAME_MIN, POKEMON_NAME_MAX)

        self.pokemon_data = processed
        self.pokemon_names_set = {p.name for p in self.pokemon_data}
        return True

    def select_random(self) -> bool:
        """Selects a random Pokémon based on the current game mode."""
        if not self.pokemon_data and not self.load_data():
            return False

        pool = ([p for p in self.pokemon_data if p.is_dual_type]
                if self.dual_type_only else self.pokemon_data)

        if not pool:
            print(f"No Pokémon found for the current mode.")
            return False

        self.current_pokemon = random.choice(pool)
        return True

    def check_guess(self, guess: str) -> List[str]:
        # ✓ correct, O present, ✗ absent
        ans = self.current_pokemon.name
        n = len(ans)
        feedback = ["✗"] * n
        counts = Counter(ans)

        # 1st pass: exact matches
        for i in range(n):
            if i < len(guess) and guess[i] == ans[i]:
                feedback[i] = "✓"
                counts[guess[i]] -= 1

        # 2nd pass: present but misplaced
        for i in range(n):
            if i < len(guess) and feedback[i] == "✗" and counts.get(
                    guess[i], 0) > 0:
                feedback[i] = "O"
                counts[guess[i]] -= 1

        return feedback

    def play_game(self):
        if not self.select_random():
            print(
                "Could not load Pokémon data or find a suitable Pokémon for this mode."
            )
            return

        cp = self.current_pokemon
        print("")
        print("=" * 50)
        print(
            f"Type(s): {'/'.join(cp.types)} | Length: {cp.length} | Mode: {'Dual' if self.dual_type_only else 'All'}"
        )
        print("Commands: 'hint' (h), 'toggle' (t), 'quit' (q)")

        attempt = 1
        while attempt <= MAX_GUESSES:
            raw = input(f"Guess {attempt}/{MAX_GUESSES}: ").strip()

            cmd = raw.lower()
            if cmd in ("quit", "q"):
                print(f"The Pokémon was: {cp.name}")
                return
            if cmd in ("toggle", "t"):
                self.dual_type_only = not self.dual_type_only
                print(
                    f"Mode switched to: {'Dual-type only' if self.dual_type_only else 'All Pokémon'}"
                )
                return self.play_game()
            if cmd in ("hint", "h"):
                vowels = sum(1 for c in cp.name if c in "AEIOU")
                print(f"Hint: First letter {cp.name[0]}, Vowels: {vowels}")
                continue

            try:
                clean = InputValidator.sanitize_and_check(
                    raw, expected_len=cp.length)
            except ValueError as e:
                print(e)
                continue

            if clean != cp.name and clean not in self.pokemon_names_set:
                print("Not a valid Pokémon name")
                continue

            feedback = self.check_guess(clean)
            print("Guess:   " + " ".join(clean))
            print("Result:  " + " ".join(feedback))

            if clean == cp.name:
                print(
                    f"\nCorrect. {cp.name} in {attempt} {'tries' if attempt != 1 else 'try'}."
                )
                self.games_played += 1
                self.games_won += 1
                return

            attempt += 1

        print(f"Out of guesses. The Pokémon was {cp.name}")
        self.games_played += 1

    def stats(self):
        if self.games_played:
            pct = self.games_won / self.games_played * 100
            print(
                f"Stats: {self.games_won}/{self.games_played} wins ({pct:.1f}%)"
            )


def main():
    print(
        "\n--- Pokémon Wordle ---\n1. All Pokémon\n2. Dual-type only\n0. Exit")
    game = PokemonWordle()
    while True:
        choice = input("Choose mode: ").strip()
        if choice == "1":
            game.dual_type_only = False
            break
        if choice == "2":
            game.dual_type_only = True
            break
        if choice == "0":
            return

    while True:
        game.play_game()
        game.stats()
        if input("\nPlay again? (y/n): ").strip().lower() not in ("y", "yes"):
            break


if __name__ == "__main__":
    main()
