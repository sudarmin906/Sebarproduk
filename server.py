import os,sqlite3,uuid,csv,io
from datetime import datetime
from flask import Flask,request,jsonify,render_template,redirect,send_file

app=Flask(__name__)
BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,"sebar.db")

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price REAL DEFAULT 0,url TEXT,description TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,name TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS content(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER,channel TEXT,title TEXT,body TEXT,tracking_code TEXT UNIQUE,clicks INTEGER DEFAULT 0,conversions INTEGER DEFAULT 0,revenue REAL DEFAULT 0,created_at TEXT);
    """); c.commit(); c.close()

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/products")
def get_products():
    c=db(); rows=c.execute("SELECT * FROM products ORDER BY id DESC").fetchall(); c.close()
    return jsonify([dict(x) for x in rows])

@app.post("/api/products")
def add_product():
    d=request.json or {}
    if not d.get("name"): return jsonify(error="Nama produk wajib diisi"),400
    c=db(); cur=c.execute("INSERT INTO products(name,price,url,description,created_at) VALUES(?,?,?,?,?)",
        (d["name"],float(d.get("price") or 0),d.get("url",""),d.get("description",""),datetime.now().isoformat(timespec="seconds")))
    c.commit(); pid=cur.lastrowid; c.close(); return jsonify(id=pid)

@app.post("/api/campaigns")
def add_campaign():
    d=request.json or {}
    c=db(); cur=c.execute("INSERT INTO campaigns(product_id,name,created_at) VALUES(?,?,?)",
        (d["product_id"],d.get("name","Kampanye Baru"),datetime.now().isoformat(timespec="seconds")))
    c.commit(); cid=cur.lastrowid; c.close(); return jsonify(id=cid)

@app.post("/api/generate")
def generate():
    d=request.json or {}; name=d.get("name","Produk"); desc=d.get("description",""); url=d.get("url","#")
    hooks=[f"Kenapa {name} layak dicoba?",f"Sedang mencari solusi praktis? Lihat {name}.",f"Ini produk yang mungkin sedang Anda butuhkan."]
    channels=["TikTok","Instagram","Facebook","YouTube Shorts","X","WhatsApp"]; out=[]
    for ch in channels:
        for i in range(3):
            body=f"{hooks[i]}\n\n{desc}\n\nLihat detail dan harganya:\n{url}\n\n#{name.replace(' ','')[:25]}"
            out.append({"channel":ch,"title":hooks[i],"body":body})
    return jsonify(content=out)

@app.post("/api/content")
def add_content():
    d=request.json or {}; code=uuid.uuid4().hex[:10]
    c=db(); c.execute("INSERT INTO content(campaign_id,channel,title,body,tracking_code,created_at) VALUES(?,?,?,?,?,?)",
        (d["campaign_id"],d["channel"],d.get("title",""),d["body"],code,datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close(); return jsonify(code=code)

@app.get("/go/<code>")
def track(code):
    c=db(); row=c.execute("""SELECT c.*,p.url FROM content c JOIN campaigns ca ON ca.id=c.campaign_id JOIN products p ON p.id=ca.product_id WHERE c.tracking_code=?""",(code,)).fetchone()
    if not row: c.close(); return "Link tidak ditemukan",404
    c.execute("UPDATE content SET clicks=clicks+1 WHERE id=?",(row["id"],)); c.commit(); c.close()
    return redirect(row["url"] or "/")

@app.get("/api/analytics/<int:cid>")
def analytics(cid):
    c=db(); rows=c.execute("SELECT channel,COUNT(*) variants,SUM(clicks) clicks,SUM(conversions) conversions,SUM(revenue) revenue FROM content WHERE campaign_id=? GROUP BY channel ORDER BY clicks DESC",(cid,)).fetchall()
    total=c.execute("SELECT COUNT(*) variants,COALESCE(SUM(clicks),0) clicks,COALESCE(SUM(conversions),0) conversions,COALESCE(SUM(revenue),0) revenue FROM content WHERE campaign_id=?",(cid,)).fetchone(); c.close()
    return jsonify(total=dict(total),channels=[dict(x) for x in rows])

@app.post("/api/conversion")
def conversion():
    d=request.json or {}; c=db(); row=c.execute("SELECT id FROM content WHERE tracking_code=?",(d.get("code"),)).fetchone()
    if not row: c.close(); return jsonify(error="Kode tidak ditemukan"),404
    c.execute("UPDATE content SET conversions=conversions+1,revenue=revenue+? WHERE id=?",(float(d.get("revenue") or 0),row["id"])); c.commit(); c.close(); return jsonify(ok=True)

@app.get("/api/export/<int:cid>")
def export_csv(cid):
    c=db(); rows=c.execute("SELECT channel,title,body,tracking_code,clicks,conversions,revenue FROM content WHERE campaign_id=?",(cid,)).fetchall(); c.close()
    s=io.StringIO(); w=csv.writer(s); w.writerow(["channel","title","body","tracking_code","clicks","conversions","revenue"])
    for r in rows: w.writerow(list(r))
    return send_file(io.BytesIO(s.getvalue().encode("utf-8-sig")),as_attachment=True,download_name=f"kampanye_{cid}.csv",mimetype="text/csv")

@app.get("/health")
def health(): return jsonify(status="ok",app="Sebar Produk 1-Klik")

if __name__=="__main__":
    init(); app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")),debug=False)
