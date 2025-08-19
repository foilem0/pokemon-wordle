W='pokemon_cache.db'
V=range
Q=input
P=bool
O=None
N='is_dual_type'
M='types'
L=ValueError
K=str
G=False
E=True
D='original_name'
C=len
B='name'
A=print
import json as R,logging as H,random as X,sqlite3 as F
from collections import Counter as Y
from dataclasses import dataclass as Z
from datetime import datetime as S,timedelta as a
from pathlib import Path
from typing import List
from urllib.parse import urlparse as b
from concurrent.futures import ThreadPoolExecutor as c
import requests as d
I=3
J=10
T=6
e=7
f='https://pokeapi.co/api/v2'
H.basicConfig(level=H.INFO,format='%(asctime)s - %(levelname)s - %(message)s',handlers=[H.FileHandler('pokemon_wordle.log'),H.StreamHandler()])
g=H.getLogger(__name__)
@Z
class U:name:K;original_name:K;types:List[K];is_dual_type:P;length:int
class h:
	def __init__(A,db_path=W):A.db_path=K(db_path);A._init_db()
	def _init_db(C):
		with F.connect(C.db_path)as A:B=A.cursor();B.execute('CREATE TABLE IF NOT EXISTS pokemon (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                name TEXT UNIQUE NOT NULL,\n                original_name TEXT NOT NULL,\n                types TEXT NOT NULL,\n                is_dual_type BOOLEAN NOT NULL,\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )');B.execute('CREATE TABLE IF NOT EXISTS cache_metadata (\n                key TEXT PRIMARY KEY,\n                value TEXT,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )');A.commit()
	def prune_cache(B,min_len,max_len):
		with F.connect(B.db_path)as A:A.execute('DELETE FROM pokemon WHERE length(name) < ? OR length(name) > ?',(min_len,max_len));A.commit()
	def get_all_pokemon(C):
		with F.connect(C.db_path)as E:A=E.cursor();A.execute('SELECT name, original_name, types, is_dual_type FROM pokemon\n                   WHERE length(name) >= ? AND length(name) <= ?',(I,J));return[{B:A[0],D:A[1],M:R.loads(A[2]),N:P(A[3])}for A in A.fetchall()]
	def save_pokemon(C,pokemon_list):
		with F.connect(C.db_path)as A:E=A.cursor();G=[(A[B],A[D],R.dumps(A[M]),A[N])for A in pokemon_list];E.executemany('INSERT OR REPLACE INTO pokemon \n                   (name, original_name, types, is_dual_type)\n                   VALUES (?, ?, ?, ?)',G);A.commit()
	def is_cache_valid(C):
		with F.connect(C.db_path)as D:A=D.cursor();A.execute("SELECT updated_at FROM cache_metadata WHERE key = 'last_update'");B=A.fetchone();return P(B and S.now()-S.fromisoformat(B[0])<a(days=e))
	def update_cache_timestamp(B):
		with F.connect(B.db_path)as A:A.execute("INSERT OR REPLACE INTO cache_metadata \n                   (key, value, updated_at) VALUES ('last_update', 'complete', CURRENT_TIMESTAMP)");A.commit()
class i:
	def __init__(A,base_url=f):A.base_url=A._validate_url(base_url);A.session=d.Session();A.session.headers.update({'User-Agent':'Pokemon-Wordle/1.0','Accept':'application/json'})
	def _validate_url(B,url):
		A=b(url)
		if A.scheme!='https'or'pokeapi.co'not in A.netloc:raise L('Invalid PokéAPI URL')
		return url
	def _get(A,endpoint):
		B=endpoint
		try:C=A.session.get(f"{A.base_url}/{B.lstrip("/")}",timeout=10);C.raise_for_status();return C.json()
		except Exception as D:g.error(f"API error on {B}: {D}");return
	def get_pokemon_list(A,limit=2000):return A._get(f"pokemon?limit={limit}")
	def get_pokemon_details(A,name_or_id):return A._get(f"pokemon/{name_or_id}")
class j:
	@staticmethod
	def sanitize_and_check(name,expected_len=O):
		A=expected_len
		if not isinstance(name,K):raise L('Name must be a string')
		B=''.join(A for A in name if A.isalnum()).upper()
		if not I<=C(B)<=J:raise L(f"Name length must be {I}-{J} letters")
		if A is not O and C(B)!=A:raise L(f"Guess must be {A} letters long")
		return B
class k:
	def __init__(A,data_dir='data'):A.data_dir=Path(data_dir);A.data_dir.mkdir(exist_ok=E);A.db=h(A.data_dir/W);A.api=i();A.pokemon_data=[];A.pokemon_names_set=set();A.current_pokemon=O;A.dual_type_only=G;A.games_played=A.games_won=0
	def _to_pokemon(A,p):return U(name=p[B].upper(),original_name=p[D],types=p[M],is_dual_type=p[N],length=C(p[B]))
	def _filter_names(H,pokes):
		G='url';E=[]
		for A in pokes:
			F=A[B].replace('-','')
			if I<=C(F)<=J:E.append({B:F,D:A[B],G:A[G]})
		return E
	def load_data(A):
		if A.db.is_cache_valid():
			B=A.db.get_all_pokemon()
			if B:
				A.pokemon_data=[A._to_pokemon(B)for B in B];A.pokemon_names_set={A.name for A in A.pokemon_data}
				if A.pokemon_data:return E
		return A._fetch_from_api()
	def _fetch_from_api(A):
		H=A.api.get_pokemon_list()
		if not H:return G
		K=A._filter_names(H['results'])
		def L(pokemon_info):
			E=pokemon_info;F=A.api.get_pokemon_details(E[D])
			if F:G=[A['type'][B].capitalize()for A in F[M]];return U(name=E[B].upper(),original_name=E[D],types=G,is_dual_type=C(G)==2,length=C(E[B]))
		F=[]
		with c(max_workers=20)as P:Q=P.map(L,K);F=[A for A in Q if A is not O]
		if not F:return G
		A.db.save_pokemon([{B:A.name,D:A.original_name,M:A.types,N:A.is_dual_type}for A in F]);A.db.update_cache_timestamp();A.db.prune_cache(I,J);A.pokemon_data=F;A.pokemon_names_set={A.name for A in A.pokemon_data};return E
	def select_random(B):
		if not B.pokemon_data and not B.load_data():return G
		C=[A for A in B.pokemon_data if A.is_dual_type]if B.dual_type_only else B.pokemon_data
		if not C:A(f"No Pokémon found for the current mode.");return G
		B.current_pokemon=X.choice(C);return E
	def check_guess(H,guess):
		B=guess;E=H.current_pokemon.name;F=C(E);D=['✗']*F;G=Y(E)
		for A in V(F):
			if A<C(B)and B[A]==E[A]:D[A]='✓';G[B[A]]-=1
		for A in V(F):
			if A<C(B)and D[A]=='✗'and G.get(B[A],0)>0:D[A]='O';G[B[A]]-=1
		return D
	def play_game(B):
		if not B.select_random():A('Could not load Pokémon data or find a suitable Pokémon for this mode.');return
		C=B.current_pokemon;A('');A('='*50);A(f"Type(s): {"/".join(C.types)} | Length: {C.length} | Mode: {"Dual"if B.dual_type_only else"All"}");A("Commands: 'hint' (h), 'toggle' (t), 'quit' (q)");D=1
		while D<=T:
			G=Q(f"Guess {D}/{T}: ").strip();F=G.lower()
			if F in('quit','q'):A(f"The Pokémon was: {C.name}");return
			if F in('toggle','t'):B.dual_type_only=not B.dual_type_only;A(f"Mode switched to: {"Dual-type only"if B.dual_type_only else"All Pokémon"}");return B.play_game()
			if F in('hint','h'):H=sum(1 for A in C.name if A in'AEIOU');A(f"Hint: First letter {C.name[0]}, Vowels: {H}");continue
			try:E=j.sanitize_and_check(G,expected_len=C.length)
			except L as I:A(I);continue
			if E!=C.name and E not in B.pokemon_names_set:A('Not a valid Pokémon name');continue
			J=B.check_guess(E);A('Guess:   '+' '.join(E));A('Result:  '+' '.join(J))
			if E==C.name:A(f"\nCorrect. {C.name} in {D} {"tries"if D!=1 else"try"}.");B.games_played+=1;B.games_won+=1;return
			D+=1
		A(f"Out of guesses. The Pokémon was {C.name}");B.games_played+=1
	def stats(B):
		if B.games_played:C=B.games_won/B.games_played*100;A(f"Stats: {B.games_won}/{B.games_played} wins ({C:.1f}%)")
def l():
	A('\n--- Pokémon Wordle ---\n1. All Pokémon\n2. Dual-type only\n0. Exit');B=k()
	while E:
		C=Q('Choose mode: ').strip()
		if C=='1':B.dual_type_only=G;break
		if C=='2':B.dual_type_only=E;break
		if C=='0':return
	while E:
		B.play_game();B.stats()
		if Q('\nPlay again? (y/n): ').strip().lower()not in('y','yes'):break
if __name__=='__main__':l()
