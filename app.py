import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client, Client
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import datetime
import pytz
import json

# Muat variabel lingkungan dari file .env
load_dotenv()

# Inisialisasi aplikasi Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-default-ganti-ini')
app.config['SESSION_COOKIE_NAME'] = 'supabase_session'

# Inisialisasi Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Login dulu, ya Bestiee"
login_manager.login_message_category = "info"

# Konfigurasi Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Variabel lingkungan SUPABASE_URL atau SUPABASE_KEY tidak ditemukan.")
    print("Pastikan Anda telah mengatur variabel-variabel ini atau membuat file .env.")
    supabase: Client = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabes sukses terkoneksi.")
    except Exception as e:
        print(f"Error, aduhh: {e}")
        supabase: Client = None

# Kelas Pengguna untuk Flask-Login
class User(UserMixin):
    def __init__(self, id_, username):
        self.id = id_
        self.username = username

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    if supabase:
        try:
            profile_response = supabase.table('profiles').select('username').eq('user_id', user_id).single().execute()
            username = profile_response.data['username']
            return User(user_id, username)
        except Exception as e:
            print(f"Gagal memuat pengguna dengan ID {user_id}: {e}")
            return None
    return None

# --- Filter Jinja2 Kustom untuk Formatting Datetime ---
@app.template_filter('format_datetime')
def format_datetime_filter(value):
    if not value:
        return ""
    dt_utc = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    wib_timezone = pytz.timezone('Asia/Jakarta')
    dt_wib = dt_utc.astimezone(wib_timezone)
    return dt_wib.strftime('%d %B %Y %H:%M:%S WIB')

def get_checkout_status_id():
    if supabase:
        try:
            # Mengambil ID status 'proses' yang selesai = false
            response = supabase.table('status').select('id').eq('nama', 'proses').eq('selesai', False).limit(1).execute()
            if response.data:
                return response.data[0]['id']
            else:
                print("Peringatan: Status 'proses' tidak ditemukan di tabel 'status'.")
                return None
        except Exception as e:
            print(f"Error fetching checkout status ID: {e}")
            return None
    return None

def get_products_with_images():
    products = []
    if supabase:
        try:
            response = supabase.table('products').select('*, product_images(product_url)').execute()
            products = response.data
        except Exception as e:
            print(f"Gagal mengambil produk dan gambar: {e}")
            flash(f"yahh, nunggu lebih lama: {e}", "error")
    return products

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        username = request.form.get('username')
        nama_lengkap = request.form.get('nama_lengkap')

        if not email or not password or not username or not nama_lengkap:
            flash('Semua kolom harus diisi.', 'error')
            return render_template('signup.html')

        if supabase:
            try:
                user_response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })

                user_data = user_response.user
                if user_data:
                    profile_data = {
                        "user_id": user_data.id,
                        "username": username,
                        "nama_lengkap": nama_lengkap,
                        "avatar_url": None
                    }
                    supabase.table('profiles').insert(profile_data).execute()

                    flash('Yeay! pendaftaran berhasil', 'success')
                    return redirect(url_for('login'))
                else:
                    flash(f'Maaf gagal: {user_response.error.message if user_response.error else "Unknown error"}', 'error')
            except Exception as e:
                flash(f'ada salah nih: {e}', 'error')
        else:
            flash("udah terkoneksi sama db.", "error")

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email dan password harus diisi.', 'error')
            return render_template('login.html')

        if supabase:
            try:
                user_response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                user_data = user_response.user
                if user_data:
                    user = User(user_data.id, username=None)
                    login_user(user)
                    flash('Login berhasil!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash(f'Login gagal: {user_response.error.message if user_response.error else "Kredensial tidak valid."}', 'error')
            except Exception as e:
                flash(f'Maaf, ada kesalahan: {e}', 'error')
        else:
            flash("db belum berjalan euy.", "error")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    if supabase:
        try:
            supabase.auth.sign_out()
            logout_user()
            flash('Terimakasi udah mampir', 'info')
        except Exception as e:
            print(f"Waduh, ada hal tak terduga: {e}")
            flash(f"Coba lagi ya: {e}", "error")
    else:
        logout_user()
        flash("kamu lepas dari server, maaf ya", "info")
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_data = None
    if supabase:
        try:
            if request.method == 'POST':
                username = request.form.get('username')
                nama_lengkap = request.form.get('nama_lengkap')
                avatar_url = request.form.get('avatar_url')

                update_data = {
                    "username": username,
                    "nama_lengkap": nama_lengkap,
                    "avatar_url": avatar_url if avatar_url else None
                }
                supabase.table('profiles').update(update_data).eq('user_id', current_user.id).execute()
                flash('Profil keren kamu udah jadi', 'success')
                return redirect(url_for('profile'))

            profile_response = supabase.table('profiles').select('*').eq('user_id', current_user.id).single().execute()
            profile_data = profile_response.data
        except Exception as e:
            print(f"Gagal ambil foto kamu: {e}")
            flash(f"Udah ada masalah: {e}", "error")
    return render_template('profile.html', profile=profile_data)

# --- Rute Aplikasi E-commerce ---

@app.route('/dashboard')
@login_required
def dashboard():
    products = get_products_with_images()
    return render_template('dashboard.html', products=products)

@app.route('/get-product-detail/<string:product_id>')
@login_required
def get_product_detail(product_id):
    if not supabase:
        return jsonify({'success': False, 'message': 'Koneksi database gagal.'}), 500
    try:
        product_response = supabase.table('products').select('*, product_images(product_url)').eq('id', product_id).single().execute()
        product_data = product_response.data
        if not product_data:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan.'}), 404
        return jsonify({'success': True, 'product': product_data})
    except Exception as e:
        print(f"Gagal mengambil detail produk: {e}")
        return jsonify({'success': False, 'message': f'Gagal mengambil detail produk: {e}'}), 500

@app.route('/keranjang')
@login_required
def keranjang():
    return render_template('keranjang.html')

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_items_json = request.form.get('cart_items')
    catatan = request.form.get('catatan', '')
    
    if not cart_items_json:
        flash("Keranjang kosong. Tambahkan produk terlebih dahulu.", "error")
        return redirect(url_for('keranjang'))

    cart_items = json.loads(cart_items_json)
    if not cart_items:
        flash("Pilih produk yang ingin dibeli.", "error")
        return redirect(url_for('keranjang'))
    
    if not supabase:
        flash("Koneksi Supabase tidak diinisialisasi.", "error")
        return redirect(url_for('keranjang'))

    checkout_status_id = get_checkout_status_id()
    if not checkout_status_id:
        flash("Gagal membuat pesanan: Status 'proses' tidak ditemukan. Pastikan ada status 'proses' dengan `selesai` = `false` di database.", 'error')
        return redirect(url_for('keranjang'))

    try:
        # 1. Ambil nama lengkap pengguna dari tabel 'profiles'
        profile_response = supabase.table('profiles').select('nama_lengkap').eq('user_id', current_user.id).single().execute()
        pemesan = profile_response.data['nama_lengkap']

        # Hitung total harga dari item yang dipilih di keranjang
        # PERBAIKAN: Ubah nilai string menjadi integer sebelum perhitungan
        total_harga = sum(int(item['product_price']) * int(item['jumlah']) for item in cart_items)

        # Buat entri baru di tabel 'pesanan'
        nomor_pesanan = f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id[:4]}"
        new_pesanan_data = {
            "user_id": current_user.id,
            "status_id": checkout_status_id,
            "total_harga": total_harga,
            "catatan": catatan,
            "nomor": nomor_pesanan,
            "pemesan": pemesan
        }
        new_pesanan_response = supabase.table('pesanan').insert(new_pesanan_data).execute()
        pesanan_id = new_pesanan_response.data[0]['id']

        # Siapkan data untuk dimasukkan ke tabel 'dipesan'
        dipesan_to_insert = []
        for item in cart_items:
            dipesan_to_insert.append({
                'pesanan_id': pesanan_id,
                'products_id': item['product_id'],
                'jumlah': int(item['jumlah']), # Pastikan jumlah juga integer
                'harga': int(item['product_price']), # Pastikan harga juga integer
                'user_id': current_user.id
            })
        
        if dipesan_to_insert:
            supabase.table('dipesan').insert(dipesan_to_insert).execute()
        
        flash("Pesanan berhasil dibuat!", "success")
        return redirect(url_for('order_confirmation', order_id=pesanan_id))

    except Exception as e:
        print(f"Checkout error: {e}")
        flash(f"Terjadi kesalahan saat melakukan checkout: {e}", "error")
        return redirect(url_for('keranjang'))

@app.route('/order_confirmation/<string:order_id>')
@login_required
def order_confirmation(order_id):
    order = None
    ordered_items = []
    if supabase:
        try:
            order_response = supabase.table('pesanan').select('*, status(nama, selesai)').eq('id', order_id).eq('user_id', current_user.id).single().execute()
            order = order_response.data
            
            items_response = supabase.table('dipesan').select('*, products(nama, harga, product_images(product_url))').eq('pesanan_id', order_id).execute()
            ordered_items = items_response.data
            
        except Exception as e:
            print(f"Gagal mengambil konfirmasi pesanan: {e}")
            flash(f"Detail pesanan tidak ditemukan: {e}", "error")

    return render_template('order_confirmation.html', order=order, ordered_items=ordered_items)

@app.route('/pesanan_saya')
@login_required
def pesanan_saya():
    my_orders = []
    if supabase:
        try:
            # Ambil semua pesanan milik user
            response = supabase.table('pesanan').select('*, status(nama, selesai)').eq('user_id', current_user.id).order('created_at', desc=True).execute()
            orders_data = response.data

            # Untuk setiap pesanan, ambil jumlah produk yang dipesan
            for order in orders_data:
                items_response = supabase.table('dipesan').select('jumlah').eq('pesanan_id', order['id']).execute()
                total_items = sum(item['jumlah'] for item in items_response.data)
                order['total_items'] = total_items
                my_orders.append(order)

        except Exception as e:
            print(f"Error fetching user orders: {e}")
            flash(f"Gagal memuat daftar pesanan Anda: {e}", "error")
    return render_template('pesanan_saya.html', orders=my_orders)

if __name__ == '__main__':
    print("Menjalankan aplikasi Flask...")
    app.run(debug=False, port=5001)