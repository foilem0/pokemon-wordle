W='pokemon_cache.db'
V=range
Q=None
P=input
O=bool
N='is_dual_type'
M='types'
L=ValueError
K=str
I=False
E=True
D='original_name'
C=len
B='name'
A=print
import json as R,logging as J,random as X,sqlite3 as F
from collections import Counter as Y
from dataclasses import dataclass as Z
from datetime import datetime as S,timedelta as a
from pathlib import Path
from typing import Dict,List,Optional
from urllib.parse import urlparse as b
import requests as c
G=3
H=10
T=6
d=7
e='https://pokeapi.co/api/v2'
J.basicConfig(level=J.INFO,format='%(asctime)s - %(levelname)s - %(message)s',handlers=[J.FileHandler('pokemon_wordle.log'),J.StreamHandler()])
f=J.getLogger(__name__)
@Z
class U:name:K;original_name:K;types:List[K];is_dual_type:O;length:int
class g:
	def __init__(A,db_path=W):A.db_path=K(db_path);A._init_db()
	def _init_db(C):
		with F.connect(C.db_path)as A:B=A.cursor();B.execute('CREATE TABLE IF NOT EXISTS pokemon (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                name TEXT UNIQUE NOT NULL,\n                original_name TEXT NOT NULL,\n                types TEXT NOT NULL,\n                is_dual_type BOOLEAN NOT NULL,\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )');B.execute('CREATE TABLE IF NOT EXISTS cache_metadata (\n                key TEXT PRIMARY KEY,\n                value TEXT,\n                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            )');A.commit()
	def prune_cache(B,min_len,max_len):
		with F.connect(B.db_path)as A:A.execute('DELETE FROM pokemon WHERE length(name) < ? OR length(name) > ?',(min_len,max_len));A.commit()
	def get_all_pokemon(C):
		with F.connect(C.db_path)as E:A=E.cursor();A.execute('SELECT name, original_name, types, is_dual_type FROM pokemon');return[{B:A[0],D:A[1],M:R.loads(A[2]),N:O(A[3])}for A in A.fetchall()]
	def save_pokemon(E,pokemon_list):
		with F.connect(E.db_path)as C:
			G=C.cursor()
			for A in pokemon_list:G.execute('INSERT OR REPLACE INTO pokemon \n                       (name, original_name, types, is_dual_type)\n                       VALUES (?, ?, ?, ?)',(A[B],A[D],R.dumps(A[M]),A[N]))
			C.commit()
	def is_cache_valid(C):
		with F.connect(C.db_path)as D:A=D.cursor();A.execute("SELECT updated_at FROM cache_metadata WHERE key = 'last_update'");B=A.fetchone();return O(B and S.now()-S.fromisoformat(B[0])<a(days=d))
	def update_cache_timestamp(B):
		with F.connect(B.db_path)as A:A.execute("INSERT OR REPLACE INTO cache_metadata \n                   (key, value, updated_at) VALUES ('last_update', 'complete', CURRENT_TIMESTAMP)");A.commit()
class h:
	def __init__(A,base_url=e):A.base_url=A._validate_url(base_url);A.session=c.Session();A.session.headers.update({'User-Agent':'Pokemon-Wordle/1.0','Accept':'application/json'})
	def _validate_url(B,url):
		A=b(url)
		if A.scheme!='https'or'pokeapi.co'not in A.netloc:raise L('Invalid PokéAPI URL')
		return url
	def _get(A,endpoint):
		B=endpoint
		try:C=A.session.get(f"{A.base_url}/{B.lstrip("/")}",timeout=10);C.raise_for_status();return C.json()
		except Exception as D:f.error(f"API error on {B}: {D}");return
	def get_pokemon_list(A,limit=2000):return A._get(f"pokemon?limit={limit}")
	def get_pokemon_details(A,name_or_id):return A._get(f"pokemon/{name_or_id}")
class i:
	@staticmethod
	def sanitize_and_check(name,expected_len=Q):
		A=expected_len
		if not isinstance(name,K):raise L('Name must be a string')
		B=''.join(A for A in name if A.isalnum()).upper()
		if not G<=C(B)<=H:raise L(f"Name length must be {G}-{H} letters")
		if A is not Q and C(B)!=A:raise L(f"Guess must be {A} letters long")
		return B
class j:
	def __init__(A,data_dir='data'):A.data_dir=Path(data_dir);A.data_dir.mkdir(exist_ok=E);A.db=g(A.data_dir/W);A.api=h();A.pokemon_data=[];A.dual_type_pokemon=[];A.current_pokemon=Q;A.dual_type_only=I;A.games_played=A.games_won=0
	def _to_pokemon(A,p):return U(name=p[B].upper(),original_name=p[D],types=p[M],is_dual_type=p[N],length=C(p[B]))
	def _filter_names(J,pokes):
		I='url';E=[]
		for A in pokes:
			F=A[B].replace('-','')
			if G<=C(F)<=H:E.append({B:F,D:A[B],I:A[I]})
		return E
	def load_data(A):
		A.db.prune_cache(G,H)
		if A.db.is_cache_valid():
			D=A.db.get_all_pokemon()
			if D:
				D=[A for A in D if G<=C(A[B])<=H];A.pokemon_data=[A._to_pokemon(B)for B in D];A.dual_type_pokemon=[A for A in A.pokemon_data if A.is_dual_type]
				if A.pokemon_data:return E
		return A._fetch_from_api()
	def _fetch_from_api(A):
		H=A.api.get_pokemon_list()
		if not H:return I
		L=A._filter_names(H['results']);F=[]
		for G in L:
			J=A.api.get_pokemon_details(G[D])
			if not J:continue
			K=[A['type'][B].capitalize()for A in J[M]];F.append(U(name=G[B].upper(),original_name=G[D],types=K,is_dual_type=C(K)==2,length=C(G[B])))
		if not F:return I
		A.db.save_pokemon([{B:A.name,D:A.original_name,M:A.types,N:A.is_dual_type}for A in F]);A.db.update_cache_timestamp();A.pokemon_data=F;A.dual_type_pokemon=[A for A in F if A.is_dual_type];return E
	def _valid_length_range(A,p):return G<=p.length<=H
	def select_random(A):
		if not A.pokemon_data and not A.load_data():return I
		C=A.dual_type_pokemon if A.dual_type_only else A.pokemon_data;B=[B for B in C if A._valid_length_range(B)]
		if not B:return I
		A.current_pokemon=X.choice(B);return E
	def check_guess(H,guess):
		B=guess;E=H.current_pokemon.name;F=C(E);D=['✗']*F;G=Y(E)
		for A in V(F):
			if A<C(B)and B[A]==E[A]:D[A]='✓';G[B[A]]-=1
		for A in V(F):
			if A<C(B)and D[A]=='✗'and G.get(B[A],0)>0:D[A]='O';G[B[A]]-=1
		return D
	def play_game(B):
		if not B.select_random():A('Could not load Pokémon data.');return
		C=B.current_pokemon;A('');A('='*50);A(f"Type(s): {"/".join(C.types)} | Length: {C.length} | Mode: {"Dual"if B.dual_type_only else"All"}");A("Commands: 'hint', 'toggle', 'quit'");D=1
		while D<=T:
			G=P(f"Guess {D}/{T}: ").strip();F=G.lower()
			if F=='quit':A(f"The Pokémon was: {C.name}");return
			if F=='toggle':B.dual_type_only=not B.dual_type_only;A(f"Mode switched to: {"Dual-type only"if B.dual_type_only else"All Pokémon"}");return B.play_game()
			if F=='hint':H=sum(1 for A in C.name if A in'AEIOU');A(f"Hint: First letter {C.name[0]}, Vowels: {H}");continue
			try:E=i.sanitize_and_check(G,expected_len=C.length)
			except L as I:A(I);continue
			if E!=C.name and not any(A.name==E for A in B.pokemon_data):A('Not a valid Pokémon name');continue
			J=B.check_guess(E);A('Guess:   '+' '.join(E));A('Result:  '+' '.join(J))
			if E==C.name:A(f"\nCorrect. {C.name} in {D} {"tries"if D!=1 else"try"}.");B.games_played+=1;B.games_won+=1;return
			D+=1
		A(f"Out of guesses. The Pokémon was {C.name}");B.games_played+=1
	def stats(B):
		if B.games_played:C=B.games_won/B.games_played*100;A(f"Stats: {B.games_won}/{B.games_played} wins ({C:.1f}%)")
def k():
	A('\n--- Pokémon Wordle ---\n1. All Pokémon\n2. Dual-type only\n0. Exit');B=j()
	while E:
		C=P('Choose mode: ').strip()
		if C=='1':B.dual_type_only=I;break
		if C=='2':B.dual_type_only=E;break
		if C=='0':return
	while E:
		B.play_game();B.stats()
		if P('\nPlay again? (y/n): ').strip().lower()not in('y','yes'):break
if __name__=='__main__':k()