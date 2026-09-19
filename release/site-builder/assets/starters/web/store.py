"""Owner-scoped SQLite access with atomic imports and retry-safe creation."""
import contextlib
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from domain import digest_record,import_preview,normalize_record


class Conflict(ValueError): pass


class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1): raise ValueError('unsupported database schema; preserve database and migrate explicitly')
            db.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,salt TEXT NOT NULL,password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,owner TEXT NOT NULL,csrf TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,owner TEXT NOT NULL,external_id TEXT NOT NULL,payload TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,external_id));
CREATE TABLE IF NOT EXISTS operations(owner TEXT NOT NULL,key TEXT NOT NULL,input_hash TEXT NOT NULL,record_id TEXT NOT NULL,PRIMARY KEY(owner,key));
PRAGMA user_version=1;''')
    @contextlib.contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=10); db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()
    def add_user(self,name,password):
        if not isinstance(name,str) or not name.strip() or len(name)>80 or not isinstance(password,str) or not 12<=len(password)<=1024: raise ValueError('username required; password must have 12 to 1024 characters')
        salt=secrets.token_hex(16); hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()
        with self.connection() as db: db.execute('INSERT INTO users VALUES(?,?,?)',(name,salt,hashed))
    def login(self,name,password):
        with self.connection() as db:
            user=db.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
            salt=bytes.fromhex(user['salt']) if user else b'\0'*16
            hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000).hex()
            if not user or not hmac.compare_digest(hashed,user['password']): return None
            token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),name,csrf,int(time.time())+28800))
            return {'token':token,'owner':name,'csrf':csrf}
    def session(self,token):
        if not token or len(token)>100: return None
        with self.connection() as db:
            row=db.execute('SELECT owner,csrf FROM sessions WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
            return dict(row) if row else None
    def logout(self,token):
        with self.connection() as db: db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    @staticmethod
    def record(row): return {'id':row['id'],'external_id':row['external_id'],**json.loads(row['payload'])}
    def list(self,owner):
        with self.connection() as db: return [self.record(r) for r in db.execute('SELECT * FROM records WHERE owner=? ORDER BY created DESC,id',(owner,))]
    def create(self,owner,payload,key):
        normalized=normalize_record(payload)
        if not isinstance(key,str) or not 1<=len(key)<=160: raise ValueError('bounded idempotency_key required')
        digest=digest_record(normalized)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT * FROM operations WHERE owner=? AND key=?',(owner,key)).fetchone()
            if prior:
                if prior['input_hash']!=digest: raise Conflict('idempotency_key already used for different content')
                row=db.execute('SELECT * FROM records WHERE owner=? AND id=?',(owner,prior['record_id'])).fetchone()
                if not row: raise Conflict('original record deleted; start a new operation')
                return self.record(row)
            rid=secrets.token_hex(16)
            db.execute('INSERT INTO records VALUES(?,?,?,?,?)',(rid,owner,rid,json.dumps(normalized),time.time_ns()))
            db.execute('INSERT INTO operations VALUES(?,?,?,?)',(owner,key,digest,rid))
            return {'id':rid,'external_id':rid,**normalized}
    def update(self,owner,rid,payload):
        if not isinstance(payload,dict): raise ValueError('update must be an object')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE'); row=db.execute('SELECT * FROM records WHERE owner=? AND id=?',(owner,rid)).fetchone()
            if not row: return None
            normalized=normalize_record({**json.loads(row['payload']),**payload})
            db.execute('UPDATE records SET payload=? WHERE owner=? AND id=?',(json.dumps(normalized),owner,rid))
            return {'id':rid,'external_id':row['external_id'],**normalized}
    def delete(self,owner,rid):
        with self.connection() as db: return db.execute('DELETE FROM records WHERE owner=? AND id=?',(owner,rid)).rowcount==1
    def export(self,owner): return {'schema_version':1,'records':self.list(owner)}
    def import_data(self,owner,text,format_name,mapping=None,strategy='skip'):
        preview=import_preview(text,format_name,mapping)
        if not preview['valid']: raise ValueError('invalid rows; nothing written')
        if strategy not in ('skip','replace','reject'): raise ValueError('invalid duplicate strategy')
        written,skipped=0,0
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for record in preview['records']:
                external=record['external_id']; prior=db.execute('SELECT id FROM records WHERE owner=? AND external_id=?',(owner,external)).fetchone()
                payload=json.dumps(normalize_record(record))
                if prior:
                    if strategy=='reject': raise Conflict('duplicate; entire import rolled back')
                    if strategy=='skip': skipped+=1; continue
                    db.execute('UPDATE records SET payload=? WHERE owner=? AND external_id=?',(payload,owner,external))
                else: db.execute('INSERT INTO records VALUES(?,?,?,?,?)',(secrets.token_hex(16),owner,external,payload,time.time_ns()))
                written+=1
        return {'written':written,'skipped':skipped}
    def backup(self,destination):
        destination=Path(destination)
        if destination.exists(): raise ValueError('backup destination exists')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as source:
            target=sqlite3.connect(destination)
            try: source.backup(target)
            finally: target.close()
