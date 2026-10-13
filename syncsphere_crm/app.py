import os, json, sqlite3, hmac, hashlib, base64
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, render_template
import requests

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'syncsphere.db')
app = Flask(__name__)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, city TEXT, segment TEXT, orders_count INTEGER DEFAULT 0, total_spent REAL DEFAULT 0, last_order TEXT, source TEXT DEFAULT 'Demo');
        CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer_id TEXT, customer_name TEXT, email TEXT, date TEXT, total REAL, status TEXT, items TEXT, source TEXT DEFAULT 'Demo');
        CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, kind TEXT, title TEXT, detail TEXT, status TEXT DEFAULT 'Logged');
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS workflows (id TEXT PRIMARY KEY, name TEXT, trigger_name TEXT, channel TEXT, enabled INTEGER, description TEXT, runs INTEGER DEFAULT 0);
        ''')
        if c.execute('SELECT COUNT(*) FROM customers').fetchone()[0] == 0:
            now = datetime.now(timezone.utc)
            people = [
                ('C-1001','Aarav Mehta','aarav.mehta@example.com','+91 98765 43210','Panaji','Loyal',8,18450,now-timedelta(days=2)),
                ('C-1002','Mira Shah','mira.shah@example.com','+91 98220 12345','Mapusa','At risk',2,3290,now-timedelta(days=48)),
                ('C-1003','Kabir Naik','kabir.naik@example.com','+91 97654 22331','Margao','High value',12,42680,now-timedelta(days=1)),
                ('C-1004','Ananya Rao','ananya.rao@example.com','+91 98901 44556','Ponda','New',1,1499,now-timedelta(days=4)),
                ('C-1005','Reyansh Patil','reyansh.patil@example.com','+91 98111 77221','Vasco da Gama','Inactive',3,5680,now-timedelta(days=76)),
                ('C-1006','Sana Fernandes','sana.fernandes@example.com','+91 99220 99887','Calangute','Loyal',6,12740,now-timedelta(days=7)),
                ('C-1007','Ishaan Kulkarni','ishaan.k@example.com','+91 98330 11220','Porvorim','New',1,2199,now-timedelta(days=1)),
                ('C-1008','Tara Desai','tara.desai@example.com','+91 98450 66778','Panjim','High value',10,31500,now-timedelta(days=3)),
            ]
            for p in people:
                c.execute('INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?)',(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8].isoformat(),'Demo'))
            orders = [
                ('WC-8401','C-1001','Aarav Mehta','aarav.mehta@example.com',now-timedelta(hours=2),2499,'processing','Wireless headphones × 1'),
                ('WC-8400','C-1003','Kabir Naik','kabir.naik@example.com',now-timedelta(hours=5),8990,'completed','Smart watch × 1, Charger × 2'),
                ('WC-8399','C-1002','Mira Shah','mira.shah@example.com',now-timedelta(days=1),1299,'on-hold','Everyday backpack × 1'),
                ('WC-8398','C-1004','Ananya Rao','ananya.rao@example.com',now-timedelta(days=1,hours=4),1499,'processing','Bluetooth speaker × 1'),
                ('WC-8397','C-1005','Reyansh Patil','reyansh.patil@example.com',now-timedelta(days=3),3590,'cancelled','Running shoes × 1'),
                ('WC-8396','C-1006','Sana Fernandes','sana.fernandes@example.com',now-timedelta(days=4),2190,'completed','Desk lamp × 1'),
                ('WC-8395','C-1008','Tara Desai','tara.desai@example.com',now-timedelta(days=5),6990,'completed','Mechanical keyboard × 1'),
                ('WC-8394','C-1007','Ishaan Kulkarni','ishaan.k@example.com',now-timedelta(days=6),2199,'refunded','Portable SSD × 1'),
            ]
            for o in orders:
                c.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)',(o[0],o[1],o[2],o[3],o[4].isoformat(),o[5],o[6],o[7],'Demo'))
            for w in [
                ('order-confirm','Order confirmation','Order created','Email',1,'Send a confirmation when a new order is received.',12),
                ('shipping-update','Shipping update','Order completed','Email',1,'Notify the customer when an order is marked completed.',8),
                ('winback','Win-back inactive customers','Customer inactive 45 days','Email',0,'Prepare a friendly re-engagement message for inactive customers.',3),
                ('high-value','High-value customer alert','Order total above ₹5,000','Internal alert',1,'Flag large orders for personal follow-up.',6),
            ]:
                c.execute('INSERT OR IGNORE INTO workflows VALUES (?,?,?,?,?,?,?)',w)
            c.execute('INSERT INTO activity(time,kind,title,detail,status) VALUES (?,?,?,?,?)',(now.isoformat(),'sync','Demo workspace ready','Sample customer and order records loaded. Connect a store to replace demo data.','Demo'))


def activity(kind, title, detail, status='Logged'):
    with db() as c:
        c.execute('INSERT INTO activity(time,kind,title,detail,status) VALUES (?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),kind,title,detail,status))


def setting(key, default=''):
    with db() as c:
        row = c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with db() as c:
        c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))


def wc_request(path):
    base = setting('wc_url').rstrip('/')
    key = setting('wc_key')
    secret = setting('wc_secret')
    if not base or not key or not secret:
        raise ValueError('Add your WooCommerce store URL, consumer key and consumer secret in Integrations first.')
    url = base + '/wp-json/wc/v3/' + path.lstrip('/')
    r = requests.get(url, auth=(key,secret), timeout=15)
    r.raise_for_status()
    return r.json()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/summary')
def summary():
    with db() as c:
        customers = c.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
        orders = c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status NOT IN ('cancelled','refunded','failed')").fetchone()[0]
        open_orders = c.execute("SELECT COUNT(*) FROM orders WHERE status IN ('pending','processing','on-hold')").fetchone()[0]
        recent = [dict(x) for x in c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 6')]
        statuses = [dict(x) for x in c.execute('SELECT status, COUNT(*) AS count FROM orders GROUP BY status')]
        top = [dict(x) for x in c.execute('SELECT name,total_spent,segment FROM customers ORDER BY total_spent DESC LIMIT 4')]
    return jsonify({'customers':customers,'orders':orders,'revenue':round(revenue,2),'open_orders':open_orders,'activity':recent,'statuses':statuses,'top_customers':top,'connected':bool(setting('wc_url') and setting('wc_key') and setting('wc_secret')),'store_url':setting('wc_url')})

@app.route('/api/customers')
def customers():
    q = request.args.get('q','').strip()
    segment = request.args.get('segment','All')
    sql = 'SELECT * FROM customers WHERE (name LIKE ? OR email LIKE ? OR id LIKE ?)'
    params = [f'%{q}%',f'%{q}%',f'%{q}%']
    if segment != 'All': sql += ' AND segment=?'; params.append(segment)
    sql += ' ORDER BY total_spent DESC'
    with db() as c: rows = [dict(x) for x in c.execute(sql,params)]
    return jsonify(rows)

@app.route('/api/customers/<customer_id>')
def customer_detail(customer_id):
    with db() as c:
        cust = c.execute('SELECT * FROM customers WHERE id=?',(customer_id,)).fetchone()
        if not cust: return jsonify({'error':'Customer not found'}),404
        orders = [dict(x) for x in c.execute('SELECT * FROM orders WHERE customer_id=? ORDER BY date DESC',(customer_id,))]
    return jsonify({'customer':dict(cust),'orders':orders})

@app.route('/api/orders')
def orders():
    q = request.args.get('q','').strip()
    status = request.args.get('status','All')
    sql = 'SELECT * FROM orders WHERE (id LIKE ? OR customer_name LIKE ? OR email LIKE ?)'
    params=[f'%{q}%',f'%{q}%',f'%{q}%']
    if status!='All': sql+=' AND status=?'; params.append(status)
    sql+=' ORDER BY date DESC'
    with db() as c: rows=[dict(x) for x in c.execute(sql,params)]
    return jsonify(rows)

@app.route('/api/orders/<order_id>/status',methods=['POST'])
def update_order(order_id):
    status=request.json.get('status','')
    allowed={'pending','processing','on-hold','completed','cancelled','refunded','failed'}
    if status not in allowed: return jsonify({'error':'Invalid status'}),400
    with db() as c:
        row=c.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if not row: return jsonify({'error':'Order not found'}),404
        source=row['source']
    if source=='WooCommerce' and order_id.isdigit():
        try:
            base=setting('wc_url').rstrip('/'); r=requests.put(base+'/wp-json/wc/v3/orders/'+order_id,auth=(setting('wc_key'),setting('wc_secret')),json={'status':status},timeout=15); r.raise_for_status()
        except Exception as e: return jsonify({'error':f'WooCommerce update failed: {e}'}),502
    with db() as c: c.execute('UPDATE orders SET status=? WHERE id=?',(status,order_id))
    activity('order',f'Order {order_id} updated',f'Status changed to {status}.','Synced' if source=='WooCommerce' else 'Demo')
    return jsonify({'ok':True})

@app.route('/api/workflows')
def workflows():
    with db() as c: rows=[dict(x) for x in c.execute('SELECT * FROM workflows ORDER BY name')]
    return jsonify(rows)

@app.route('/api/workflows/<wid>',methods=['POST'])
def toggle_workflow(wid):
    enabled=1 if request.json.get('enabled') else 0
    with db() as c:
        r=c.execute('SELECT name FROM workflows WHERE id=?',(wid,)).fetchone()
        if not r:return jsonify({'error':'Workflow not found'}),404
        c.execute('UPDATE workflows SET enabled=? WHERE id=?',(enabled,wid))
    activity('workflow',f'Workflow {"enabled" if enabled else "paused"}',r['name'],'Configured')
    return jsonify({'ok':True})

@app.route('/api/workflows/<wid>/test',methods=['POST'])
def test_workflow(wid):
    with db() as c:
        w=c.execute('SELECT * FROM workflows WHERE id=?',(wid,)).fetchone()
        if not w:return jsonify({'error':'Workflow not found'}),404
        c.execute('UPDATE workflows SET runs=runs+1 WHERE id=?',(wid,))
    activity('workflow',f'Test run: {w["name"]}','Demo execution recorded. Connect an email provider to deliver real messages.','Simulated')
    return jsonify({'ok':True,'message':'Test event recorded. No email was sent in demo mode.'})

@app.route('/api/integration',methods=['GET','POST'])
def integration():
    if request.method=='GET':
        return jsonify({'url':setting('wc_url'),'configured':bool(setting('wc_url') and setting('wc_key') and setting('wc_secret')),'connected':setting('wc_connected')=='1','last_sync':setting('wc_last_sync')})
    data=request.json or {}
    url=data.get('url','').strip().rstrip('/')
    key=data.get('key','').strip(); secret=data.get('secret','').strip()
    if url and not url.startswith(('https://','http://')): return jsonify({'error':'Store URL must start with https:// or http://'}),400
    set_setting('wc_url',url); set_setting('wc_key',key); set_setting('wc_secret',secret)
    set_setting('wc_connected','0')
    activity('integration','WooCommerce settings saved','Credentials are stored locally in the app SQLite database.','Configured')
    return jsonify({'ok':True})

@app.route('/api/sync',methods=['POST'])
def sync():
    try:
        wc_customers=wc_request('customers?per_page=100')
        wc_orders=wc_request('orders?per_page=100')
        now=datetime.now(timezone.utc)
        with db() as c:
            # WooCommerce customers
            for x in wc_customers:
                cid='WC-C-'+str(x.get('id'))
                name=(x.get('first_name','')+' '+x.get('last_name','')).strip() or x.get('username') or x.get('email') or cid
                orders_for=c.execute('SELECT COUNT(*),COALESCE(SUM(total),0),MAX(date) FROM orders WHERE customer_id=?',(cid,)).fetchone()
                c.execute('''INSERT INTO customers(id,name,email,phone,city,segment,orders_count,total_spent,last_order,source) VALUES(?,?,?,?,?,?,?,?,?, 'WooCommerce') ON CONFLICT(id) DO UPDATE SET name=excluded.name,email=excluded.email,phone=excluded.phone,city=excluded.city,source='WooCommerce' ''',(cid,name,x.get('email',''),x.get('billing',{}).get('phone',''),x.get('billing',{}).get('city',''),'WooCommerce',orders_for[0],orders_for[1],orders_for[2] or '',))
            # Guest orders are also represented as customer profiles; order IDs remain numeric for write-back.
            for o in wc_orders:
                bill=o.get('billing') or {}
                cid='WC-C-'+str(o.get('customer_id')) if o.get('customer_id') else 'WC-G-'+str(o.get('id'))
                name=(bill.get('first_name','')+' '+bill.get('last_name','')).strip() or bill.get('email') or cid
                if not c.execute('SELECT 1 FROM customers WHERE id=?',(cid,)).fetchone():
                    c.execute('INSERT INTO customers(id,name,email,phone,city,segment,orders_count,total_spent,last_order,source) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,name,bill.get('email',''),bill.get('phone',''),bill.get('city',''),'New',0,0,o.get('date_created',''),'WooCommerce'))
                items=', '.join(str(i.get('name','Item'))+' × '+str(i.get('quantity',1)) for i in o.get('line_items',[]))
                c.execute('''INSERT INTO orders(id,customer_id,customer_name,email,date,total,status,items,source) VALUES(?,?,?,?,?,?,?,?, 'WooCommerce') ON CONFLICT(id) DO UPDATE SET customer_id=excluded.customer_id,customer_name=excluded.customer_name,email=excluded.email,date=excluded.date,total=excluded.total,status=excluded.status,items=excluded.items,source='WooCommerce' ''',(str(o.get('id')),cid,name,bill.get('email',''),o.get('date_created',''),float(o.get('total') or 0),o.get('status','pending'),items))
            # Recompute aggregates from synced orders
            for row in c.execute("SELECT id FROM customers WHERE source='WooCommerce'").fetchall():
                agg=c.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN status NOT IN ('cancelled','refunded','failed') THEN total ELSE 0 END),0),MAX(date) FROM orders WHERE customer_id=?",(row['id'],)).fetchone()
                spent=agg[1]; count=agg[0]; last=agg[2] or ''
                segment='High value' if spent>=20000 else ('Loyal' if count>=4 else ('At risk' if last and (now-datetime.fromisoformat(last.replace('Z','+00:00'))).days>=45 else 'New'))
                c.execute('UPDATE customers SET orders_count=?,total_spent=?,last_order=?,segment=? WHERE id=?',(count,spent,last,segment,row['id']))
        set_setting('wc_connected','1'); set_setting('wc_last_sync',now.isoformat())
        activity('sync','WooCommerce sync completed',f'Imported/updated {len(wc_customers)} customers and {len(wc_orders)} orders.','Success')
        return jsonify({'ok':True,'customers':len(wc_customers),'orders':len(wc_orders),'last_sync':now.isoformat()})
    except requests.HTTPError as e:
        msg=f'WooCommerce returned HTTP {e.response.status_code}. Check the store URL, REST API keys and permissions.'
        activity('sync','WooCommerce sync failed',msg,'Error'); return jsonify({'error':msg}),502
    except Exception as e:
        msg=str(e); activity('sync','WooCommerce sync failed',msg,'Error'); return jsonify({'error':msg}),400

@app.route('/api/webhook/woocommerce',methods=['POST'])
def woo_webhook():
    secret=setting('wc_webhook_secret')
    signature=request.headers.get('X-WC-Webhook-Signature','')
    if secret:
        expected=base64.b64encode(hmac.new(secret.encode(),request.get_data(),hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(signature,expected): return jsonify({'error':'Invalid webhook signature'}),401
    topic=request.headers.get('X-WC-Webhook-Topic','unknown')
    payload=request.get_json(silent=True) or {}
    activity('webhook',f'WooCommerce event received: {topic}',f'Payload ID: {payload.get("id","unknown")}. Run Sync to refresh stored records.','Received')
    return jsonify({'ok':True,'topic':topic})

@app.route('/api/activity')
def get_activity():
    with db() as c: rows=[dict(x) for x in c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 40')]
    return jsonify(rows)

init_db()
if __name__ == '__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
