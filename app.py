from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
import uuid
from datetime import datetime
from functools import wraps
from collections import Counter

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

PRICE_FILE = 'prices.json'
CODE_FILE = 'code.json'


# --- Helper Functions ---
def load_data(filename):
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump([], f)
    with open(filename, 'r') as f:
        return json.load(f)

        
def load_user_data(filename):
    user = session.get('username')
    filepath = os.path.join('data', user, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r') as f:
        return json.load(f)
        
def save_user_data(filename, data):
    user = session.get('username')
    filepath = os.path.join('data', user, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)


def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_users():
    with open('users.json', 'r') as f:
        return json.load(f)

def get_code_file():
    user = session.get('username')
    return f"data/codes_{user}.json"


def get_voucher_file():
    user = session.get('username')
    return f"data/vouchers_{user}.json"


    
def load_prices():
    if not os.path.exists(PRICE_FILE):
        return {}
    with open(PRICE_FILE, 'r') as f:
        return json.load(f)

def save_prices(prices):
    with open(PRICE_FILE, 'w') as f:
        json.dump(prices, f, indent=2)

# --- Login Management ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        users = load_users()

        for user in users:
            if user['username'] == username and user['password'] == password:
                session['logged_in'] = True
                session['username'] = username

                # Create user-specific files if not exist
                for file in [get_code_file(), get_voucher_file()]:
                    if not os.path.exists(file):
                        save_data(file, [])

                flash('Login berhasil!', 'success')
                return redirect(url_for('index'))

        flash('Username atau password salah.', 'danger')
    return render_template('login.html')
    
@app.route('/statistic')
@login_required
def statistic():
    vouchers = load_data(get_voucher_file())
    sold = sum(1 for v in vouchers if v['status'].strip().lower() in ['sold', 'terjual'])
    unsold = sum(1 for v in vouchers if v['status'].strip().lower() in ['unsold', 'belum terjual'])

    type_counter = Counter(v['tipe'] for v in vouchers)

    return render_template(
        'statistic.html',
        sold=sold,
        unsold=unsold,
        type_labels=list(type_counter.keys()),
        type_values=list(type_counter.values())
    )

 
   
@app.route('/logout')
def logout():
    session.clear()
    flash('Berhasil logout.', 'info')
    return redirect(url_for('login'))

# --- Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/redeem', methods=['GET', 'POST'])
@login_required
def redeem():
    if request.method == 'POST':
        input_code = request.form['code'].strip().upper()
        codes = load_data(get_code_file())

        for code_entry in codes:
            if code_entry.get('code', '').strip().upper() == input_code:
                if code_entry['status'] == 'used':
                    flash('Kode sudah digunakan.', 'warning')
                else:
                    code_entry['status'] = 'used'
                    save_data(get_code_file(), codes)
                    flash('Kode berhasil diredeem!', 'success')
                break
        else:
            # Tambah jika tidak ditemukan
            codes.append({"code": input_code, "status": "used"})
            save_data(get_code_file(), codes)
            flash('Kode berhasil diredeem (kode baru ditambahkan).', 'success')

        return redirect(url_for('redeem'))

    return render_template('redeem.html')

@app.route('/codes')
@app.route('/code_list')
@login_required
def code_list():
    codes = load_data(get_code_file())
    return render_template('code_list.html', codes=codes)


@app.route('/update_code_status/<code>', methods=['POST'])
@login_required
def update_code_status(code):
    codes = load_data(get_code_file())
    for item in codes:
        if item['code'] == code:
            item['status'] = 'used' if item['status'] == 'unused' else 'unused'
            break
    save_data(get_code_file(), codes)
    flash('Status kode berhasil diperbarui.', 'success')
    return redirect(url_for('code_list'))

@app.route('/delete_code/<code>', methods=['POST'])
@login_required
def delete_code(code):
    codes = load_data(get_code_file())
    codes = [c for c in codes if c['code'] != code]
    save_data(get_code_file(), codes)
    flash('Kode berhasil dihapus.', 'success')
    return redirect(url_for('code_list'))
    
@app.route('/vouchers')
@app.route('/voucher_list')
@login_required
def voucher_list():
    vouchers = load_data(get_voucher_file())
    prices = load_data('prices.json')
    tipe_options = list(set(v['tipe'] for v in vouchers))
    return render_template('voucher_list.html', vouchers=vouchers, prices=prices, tipe_options=tipe_options)

@app.route('/add_voucher', methods=['POST'])
@login_required
def add_voucher():
    vouchers = load_data(get_voucher_file())
    new_voucher = request.form['voucher'].strip()
    tipe = request.form.get('tipe', '').strip()
    if not new_voucher or not tipe:
        flash('Voucher dan tipe harus diisi.', 'danger')
        return redirect(url_for('voucher_list'))
    vouchers.append({
        "id": str(uuid.uuid4()),
        "code": new_voucher,
        "tipe": tipe,
        "status": "unsold",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    save_data(get_voucher_file(), vouchers)
    flash('Voucher berhasil ditambahkan.', 'success')
    return redirect(url_for('voucher_list'))

@app.route('/update_voucher_status/<voucher_id>', methods=['POST'])
@login_required
def update_voucher_status(voucher_id):
    vouchers = load_data(get_voucher_file())
    for voucher in vouchers:
        if voucher['id'] == voucher_id:
            voucher['status'] = 'sold' if voucher['status'] == 'unsold' else 'unsold'
            break
    save_data(get_voucher_file(), vouchers)
    flash('Status voucher berhasil diperbarui.', 'success')
    return redirect(url_for('voucher_list'))

@app.route('/delete_voucher/<voucher_id>', methods=['POST'])
@login_required
def delete_voucher(voucher_id):
    vouchers = load_data(get_voucher_file())
    vouchers = [v for v in vouchers if v['id'] != voucher_id]
    save_data(get_voucher_file(), vouchers)
    flash('Voucher berhasil dihapus.', 'success')
    return redirect(url_for('voucher_list'))
    
@app.route('/edit_price/<tipe>', methods=['GET', 'POST'])
@login_required
def edit_price(tipe):
    prices = load_prices()
    if request.method == 'POST':
        new_price = request.form.get('price')
        if new_price and new_price.isdigit():
            prices[tipe] = int(new_price)
            save_prices(prices)
            flash(f'Harga untuk tipe \"{tipe}\" berhasil diperbarui.', 'success')
            return redirect(url_for('voucher_list'))
        else:
            flash('Harga harus berupa angka.', 'danger')
    current_price = prices.get(tipe, 0)
    return render_template('edit_price.html', tipe=tipe, price=current_price)

@app.route('/update_price', methods=['POST'])
@login_required
def update_price():
    tipe = request.form['tipe']
    price = request.form['price']

    try:
        price_int = int(price)
    except ValueError:
        flash("Harga harus berupa angka.", "danger")
        return redirect(url_for('voucher_list'))

    prices = load_data('prices.json')
    prices[tipe] = price_int
    save_data('prices.json', prices)

    flash(f"Harga untuk voucher '{tipe}' berhasil diperbarui ke Rp{price_int:,}.", "success")
    return redirect(url_for('voucher_list'))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
