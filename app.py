import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from werkzeug.security import check_password_hash
import pymysql.cursors
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

from hardware import traffic_controller
from camera import camera_stream, generate_frames

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_development')
app.permanent_session_lifetime = timedelta(minutes=30)

LATEST_CAMERA_PATH = "static/latest_camera.jpg"
CAMERA_UPLOAD_TOKEN = os.environ.get("CAMERA_UPLOAD_TOKEN", "demo_camera_token")


def get_db_connection():
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("DATABASE_URL environment variable not set. Please set it in .env file.")
            return None

        url = urlparse(db_url)
        conn = pymysql.connect(
            host=url.hostname,
            user=url.username,
            password=url.password,
            database=url.path[1:],
            port=url.port or 3306,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as err:
        print(f"Error connecting to database: {err}")
        return None


def log_system_event(event_type, description):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO system_logs (event_type, description) VALUES (%s, %s)",
                (event_type, description)
            )
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Failed to log event: {e}")
        finally:
            conn.close()


def log_decision(counts, selected_lane, priority_score, green_duration, reason):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decision_logs
                (lane_a_count, lane_b_count, lane_c_count, selected_lane, priority_score, green_duration, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                counts.get('A', 0),
                counts.get('B', 0),
                counts.get('C', 0),
                selected_lane,
                priority_score,
                green_duration,
                reason
            ))
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Failed to log decision: {e}")
        finally:
            conn.close()


def update_latest_status(status_data):
    conn = get_db_connection()
    if conn:
        try:
            lanes = status_data["lanes"]
            cursor = conn.cursor()
            cursor.execute("""
                REPLACE INTO latest_status
                (id, active_lane,
                 lane_a_light, lane_a_count, lane_a_wait_time, lane_a_priority,
                 lane_b_light, lane_b_count, lane_b_wait_time, lane_b_priority,
                 lane_c_light, lane_c_count, lane_c_wait_time, lane_c_priority)
                VALUES
                (1, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s, %s,
                 %s, %s, %s, %s)
            """, (
                status_data.get("active_lane"),
                lanes["A"]["light"], lanes["A"]["count"], lanes["A"]["wait_time"], lanes["A"]["priority"],
                lanes["B"]["light"], lanes["B"]["count"], lanes["B"]["wait_time"], lanes["B"]["priority"],
                lanes["C"]["light"], lanes["C"]["count"], lanes["C"]["wait_time"], lanes["C"]["priority"],
            ))
            conn.commit()
            cursor.close()
        except Exception as e:
            print(f"Failed to update latest status: {e}")
        finally:
            conn.close()


def get_latest_status_from_database():
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM latest_status WHERE id = 1")
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        return {
            "active_lane": row["active_lane"],
            "lanes": {
                "A": {
                    "light": row["lane_a_light"],
                    "count": row["lane_a_count"],
                    "wait_time": row["lane_a_wait_time"],
                    "priority": row["lane_a_priority"]
                },
                "B": {
                    "light": row["lane_b_light"],
                    "count": row["lane_b_count"],
                    "wait_time": row["lane_b_wait_time"],
                    "priority": row["lane_b_priority"]
                },
                "C": {
                    "light": row["lane_c_light"],
                    "count": row["lane_c_count"],
                    "wait_time": row["lane_c_wait_time"],
                    "priority": row["lane_c_priority"]
                }
            }
        }

    except Exception as e:
        print(f"Failed to get latest status: {e}")
        return None
    finally:
        conn.close()


def generate_uploaded_camera_frames():
    while True:
        if os.path.exists(LATEST_CAMERA_PATH):
            try:
                with open(LATEST_CAMERA_PATH, "rb") as f:
                    frame = f.read()

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )
            except Exception as e:
                print(f"Failed to stream uploaded camera frame: {e}")

        time.sleep(0.5)


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user['password_hash'], password):
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                log_system_event('LOGIN', f"User {username} logged in")
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
        else:
            flash('Database connection failed', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    username = session.get('username')
    if username:
        log_system_event('LOGOUT', f"User {username} logged out")
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session.get('username'))


@app.route('/video_feed')
def video_feed():
    if 'user_id' not in session:
        return "Unauthorized", 401

    is_render = os.environ.get("RENDER", "false").lower() == "true"

    if is_render:
        return Response(
            generate_uploaded_camera_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/local_camera_frame')
def local_camera_frame():
    is_render = os.environ.get("RENDER", "false").lower() == "true"

    if is_render:
        return "Not available on Render", 503

    frame = camera_stream.get_frame()

    if not frame:
        return "No camera frame yet", 404

    return Response(frame, mimetype="image/jpeg")


@app.route('/api/upload_camera', methods=['POST'])
def upload_camera():
    token = request.headers.get("X-Camera-Token")

    if token != CAMERA_UPLOAD_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    os.makedirs("static", exist_ok=True)

    image = request.files["image"]
    temp_path = LATEST_CAMERA_PATH + ".tmp"
    image.save(temp_path)
    os.replace(temp_path, LATEST_CAMERA_PATH)

    return jsonify({
        "status": "success",
        "message": "Camera snapshot uploaded",
        "timestamp": time.time()
    })


@app.route('/api/status')
def status():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    is_render = os.environ.get("RENDER", "false").lower() == "true"

    if is_render:
        status_data = get_latest_status_from_database()

        if not status_data:
            status_data = {
                "active_lane": None,
                "lanes": {
                    "A": {"light": "red", "count": 0, "wait_time": 0, "priority": 0},
                    "B": {"light": "red", "count": 0, "wait_time": 0, "priority": 0},
                    "C": {"light": "red", "count": 0, "wait_time": 0, "priority": 0}
                }
            }
    else:
        status_data = traffic_controller.get_status()
        update_latest_status(status_data)

    conn = get_db_connection()
    recent_logs = []
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decision_logs ORDER BY timestamp DESC LIMIT 10")
            rows = cursor.fetchall()
            for row in rows:
                recent_logs.append(dict(row))
            cursor.close()
        except Exception as e:
            print(f"Failed to fetch recent logs: {e}")
        finally:
            conn.close()

    status_data['recent_logs'] = recent_logs
    return jsonify(status_data)


if __name__ == '__main__':
    is_render = os.environ.get("RENDER", "false").lower() == "true"

    if not is_render:
        traffic_controller.set_decision_callback(log_decision)
        camera_stream.start()

    print("Starting server...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
