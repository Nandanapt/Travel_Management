from flask import Flask, render_template, request, redirect, session, url_for
import hashlib
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Hardcoded prices (from_city, to_city, transport)
prices = {
    ('Delhi', 'Mumbai', 'flight'): 4500,
    ('Delhi', 'Mumbai', 'train'): 1200,
    ('Delhi', 'Mumbai', 'bus'): 800,
    ('Bangalore', 'Hyderabad', 'flight'): 3500,
    ('Bangalore', 'Hyderabad', 'train'): 900,
    ('Bangalore', 'Hyderabad', 'bus'): 700,
    ('Chennai', 'Kolkata', 'flight'): 5000,
    ('Chennai', 'Kolkata', 'train'): 1500,
    ('Chennai', 'Kolkata', 'bus'): 1000,
    ('Bangalore', 'Kerala', 'flight'): 3500,
    ('Bangalore', 'Kerala', 'train'): 900,
    ('Bangalore', 'Kerala', 'bus'): 700
}

# Initialize database (only users and bookings tables)
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY,
        user TEXT,
        from_city TEXT,
        to_city TEXT,
        transport TEXT,
        price REAL,
        payment_status TEXT DEFAULT 'pending',
        payment_time TEXT
    )''')

    # Check if payment_status column exists, if not, add it
    try:
        c.execute("SELECT payment_status FROM bookings LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE bookings ADD COLUMN payment_status TEXT DEFAULT 'pending'")

    # Check if payment_time column exists, if not, add it
    try:
        c.execute("SELECT payment_time FROM bookings LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE bookings ADD COLUMN payment_time TEXT")

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                return "Username already exists."
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = hash_password(request.form['password'])
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        if cur.fetchone():
            session['user'] = username
            return redirect('/index')
    return "Invalid credentials"

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect('/')
    return render_template('index.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        from_city = request.form['from']
        to_city = request.form['to']
        transport = request.form['transport']

        # Use the hardcoded prices dictionary to get the price
        price = prices.get((from_city, to_city, transport), 0)

        # Save the booking details with the price in the bookings table
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute('''INSERT INTO bookings (user, from_city, to_city, transport, price)
                           VALUES (?, ?, ?, ?, ?)''',
                        (session['user'], from_city, to_city, transport, price))
            conn.commit()

        # Pass the price to the confirm_booking template
        return render_template('confirm_booking.html', from_city=from_city, to_city=to_city, transport=transport, price=price)

    return render_template('book.html')

@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    if 'user' not in session:
        return redirect('/')

    from_city = request.form['from']
    to_city = request.form['to']
    transport = request.form['transport']
    total_price = request.form['total_price'] # Get the total price

    session['booking_details'] = {
        'from_city': from_city,
        'to_city': to_city,
        'transport': transport,
        'price': total_price  # Store the total price in the session
    }

    return redirect('/payment')


@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'booking_details' not in session:
        return redirect('/book')  # If no session data, redirect to the booking page

    # If it's a GET request, render the payment page
    if request.method == 'GET':
        booking = session['booking_details']
        return render_template('payment.html',
                               from_city=booking['from_city'],
                               to_city=booking['to_city'],
                               transport=booking['transport'],
                               total_amount=booking['price'])

    # If it's a POST request, handle the payment confirmation
    if request.method == 'POST':
        # Simulate successful payment
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update payment status in the database
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute('''UPDATE bookings SET payment_status = ?, payment_time = ?
                           WHERE user = ? AND from_city = ? AND to_city = ? AND transport = ?''',
                        ('confirmed', current_time, session['user'],
                         session['booking_details']['from_city'],
                         session['booking_details']['to_city'],
                         session['booking_details']['transport']))
            conn.commit()

        # Redirect to the booking success page, passing the price
        return redirect(url_for('booking_success',
                               from_city=session['booking_details']['from_city'],
                               to_city=session['booking_details']['to_city'],
                               transport=session['booking_details']['transport'],
                               price=session['booking_details']['price']))


@app.route('/booking_success')
def booking_success():
    if 'user' not in session:
        return redirect('/')

    from_city = request.args.get('from_city')
    to_city = request.args.get('to_city')
    transport = request.args.get('transport')
    price = request.args.get('price')
    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return render_template('booking_success.html',
                           from_city=from_city,
                           to_city=to_city,
                           transport=transport,
                           price=price,
                           date_time=date_time)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return redirect('/')
@app.context_processor
def inject_year():
    from datetime import datetime
    return {'current_year': datetime.now().year}


if __name__ == '__main__':
    init_db()
    app.run(debug=True)