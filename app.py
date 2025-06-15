import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from models import db, Broadcast
import datetime
from flask import send_from_directory

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
# Menentukan lokasi database di dalam folder 'instance'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'radio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'kunci-rahasia-yang-sangat-aman'

# --- Inisialisasi ---
db.init_app(app)
socketio = SocketIO(app)

# Pastikan folder 'rekaman' & 'instance' ada
rekaman_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rekaman')
if not os.path.exists(rekaman_folder):
    os.makedirs(rekaman_folder)
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

# Membuat database jika belum ada
with app.app_context():
    db.create_all()

# --- Variabel Global untuk Siaran ---
current_broadcast_file = None
file_writer = None
active_broadcast_id = None

# --- Rute Halaman (Routing) ---
@app.route('/')
def index():
    return render_template('penyiar.html')

@app.route('/penyiar')
def penyiar_page():
    return render_template('penyiar.html')

@app.route('/client')
def client_page():
    # Ambil semua rekaman yang sudah tidak live
    arsip = Broadcast.query.filter_by(is_live=False).order_by(Broadcast.id.desc()).all()
    # Cek apakah ada siaran live
    live_broadcast = Broadcast.query.filter_by(is_live=True).first()
    return render_template('client.html', arsip=arsip, live_broadcast=live_broadcast)

@app.route('/rekaman/<filename>')
def serve_recording(filename):
    # return app.send_static_file(os.path.join('..', 'rekaman', filename))
    return send_from_directory('rekaman', filename)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        results = Broadcast.query.filter_by(is_live=False).order_by(Broadcast.id.desc()).all()
    else:
        search_term = f"%{query}%"
        results = Broadcast.query.filter(
            (Broadcast.title.like(search_term) | Broadcast.broadcast_date.like(search_term)) & (Broadcast.is_live == False)
        ).order_by(Broadcast.id.desc()).all()
    
    return jsonify([{
        'title': b.title,
        'date': b.broadcast_date,
        'start_time': b.start_time,
        'filename': b.filename
    } for b in results])


# --- Logika WebSocket (SocketIO) ---
@socketio.on('start_broadcast')
def handle_start_broadcast(data):
    """Dipicu dari penyiar untuk memulai siaran."""
    global current_broadcast_file, file_writer, active_broadcast_id
    
    # 1. Buat record baru di database
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"siaran_{timestamp}.webm"
    
    new_broadcast = Broadcast(
        title=data['title'],
        broadcast_date=data['date'],
        start_time=data['startTime'],
        filename=filename,
        is_live=True
    )
    db.session.add(new_broadcast)
    db.session.commit()
    
    active_broadcast_id = new_broadcast.id
    current_broadcast_file = os.path.join(rekaman_folder, filename)
    
    # 2. Buka file untuk merekam
    try:
        file_writer = open(current_broadcast_file, 'wb')
        # 3. Beri tahu semua client bahwa siaran dimulai
        emit('broadcast_started', {'title': new_broadcast.title}, broadcast=True)
        print(f"Siaran '{data['title']}' dimulai, merekam ke {filename}")
    except Exception as e:
        print(f"Gagal memulai rekaman: {e}")

@socketio.on('audio_chunk')
def handle_audio_chunk(chunk):
    """Menerima dan menyiarkan audio, lalu menyimpannya."""
    # Siarkan ke pendengar
    emit('live_audio', chunk, broadcast=True)
    # Simpan ke file
    if file_writer:
        try:
            file_writer.write(chunk)
        except Exception as e:
            print(f"Gagal menulis chunk: {e}")

@socketio.on('stop_broadcast')
def handle_stop_broadcast(data):
    """Menghentikan siaran dan menutup file."""
    global file_writer, active_broadcast_id
    
    if file_writer:
        file_writer.close()
        file_writer = None

    # Update record di database: set is_live = False
    if active_broadcast_id:
        broadcast_to_stop = Broadcast.query.get(active_broadcast_id)
        if broadcast_to_stop:
            broadcast_to_stop.is_live = False
            broadcast_to_stop.end_time = data['endTime']
            db.session.commit()
    
    emit('broadcast_stopped', {}, broadcast=True)
    print("Siaran dihentikan.")
    active_broadcast_id = None


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)