from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import pickle
import sqlite3
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from groq import Groq
import os

app = Flask(__name__)
app.secret_key = "secret123"

model = pickle.load(open('model.pkl', 'rb')) #rb->read in binary mode 

client = Groq(api_key="API-KEY")   # <-- REPLACE WITH YOUR KEY


def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fname TEXT,
            lname TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            login_time TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        visual REAL,
        auditory REAL,
        reading REAL,
        kinesthetic REAL,
        result TEXT,
        date TEXT
)
''')
    
    conn.commit()
    conn.close()

init_db()


# ================= ROUTES =================

@app.route('/')
def index():
    return render_template('index.html')


# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ""

    if request.method == 'POST':
        fname = request.form['fname'].strip()
        lname = request.form['lname'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()

        # ✅ CHECK DUPLICATE EMAIL
        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        existing = cur.fetchone()

        if existing:
            message = "Email already exists ❌"
        else:
            cur.execute(
                "INSERT INTO users (fname, lname, email, password) VALUES (?, ?, ?, ?)",
                (fname, lname, email, password)
            )
            conn.commit()
            message = "Registration successful ✅"

        conn.close()

    return render_template('register.html', message=message)


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ""

    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()
        conn.close()

        if user:
            # ✅ STORE NAME (NOT EMAIL)
            session['user'] = user[1]

            conn = sqlite3.connect('users.db')
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO login_history (email, login_time) VALUES (?, ?)",
                (email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()

            return redirect(url_for('predict_page'))
        else:
            message = "Invalid login ❌"

    return render_template('login.html', message=message)


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


# ---------- QUIZ PAGE ----------
@app.route('/predict_page')
def predict_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('predict_page.html')


# ---------- LEARNING STYLES PAGE ----------
@app.route('/learning_style')
def learning_styles():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('learning_style.html')


# ---------- PREDICTION ----------
@app.route('/predict', methods=['POST'])
def predict():
    try:
        v = sum([float(request.form[f'v{i}']) for i in range(1,5)])
        a = sum([float(request.form[f'a{i}']) for i in range(1,5)])
        r = sum([float(request.form[f'r{i}']) for i in range(1,5)])
        k = sum([float(request.form[f'k{i}']) for i in range(1,5)])
    except Exception as e:
        return f"Error: {e}"

    total = v + a + r + k

    scores = {
        "Visual": round((v/total)*100, 2),
        "Auditory": round((a/total)*100, 2),
        "Reading": round((r/total)*100, 2),
        "Kinesthetic": round((k/total)*100, 2)
    }

    result = max(scores, key=scores.get)

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute(
    "INSERT INTO results (name, visual, auditory, reading, kinesthetic, result, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (
        session.get('user'),
        scores["Visual"],
        scores["Auditory"],
        scores["Reading"],
        scores["Kinesthetic"],
        result,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
)

    conn.commit()
    conn.close()

    # 📊 GRAPH
    labels = list(scores.keys())
    values = list(scores.values())

    plt.figure()
    plt.bar(labels, values)
    plt.savefig("static/graph.png")
    plt.close()

    return render_template(
        'predict_page.html',
        result=result,
        scores=scores,
        graph='graph.png',
        name=session.get('user')
    )
    

# ---------- CHATBOT ----------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "you are a helpful chatbot."},
                {"role": "user", "content": user_msg}
            ]
        )

        return jsonify({
            "reply": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({"error": str(e)})
    
@app.route('/history')
def history():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM results")
    data = cur.fetchall()

    conn.close()

    return render_template('history.html', data=data)

# ---------- VIEW USERS (OPTIONAL DEBUG) ----------
@app.route('/view_users')
def view_users():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("SELECT fname, lname, email FROM users")
    users = cur.fetchall()

    conn.close()

    return str(users)


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)