import os
from flask import Flask, request, jsonify
from hyundai_kia_connect_api import VehicleManager, ClimateRequestOptions
from hyundai_kia_connect_api.exceptions import AuthenticationError

app = Flask(__name__)

# =========================
# Environment Variables
# =========================
USERNAME = os.environ.get("KIA_USERNAME")
PASSWORD = os.environ.get("KIA_PASSWORD")
PIN = os.environ.get("KIA_PIN")
SECRET_KEY = os.environ.get("SECRET_KEY")
VEHICLE_ID = os.environ.get("VEHICLE_ID")  # Optional

missing = []
if not USERNAME:
    missing.append("KIA_USERNAME")
if not PASSWORD:
    missing.append("KIA_PASSWORD")
if not PIN:
    missing.append("KIA_PIN")
if not SECRET_KEY:
    missing.append("SECRET_KEY")

if missing:
    raise ValueError(f"Missing environment variables: {', '.join(missing)}")

# =========================
# Vehicle Manager
# =========================
vehicle_manager = VehicleManager(
    region=1,  # Europe
    brand=1,   # KIA
    username=USERNAME,
    password=PASSWORD,
    pin=str(PIN)
)

# =========================
# Helper Functions
# =========================
def authorize_request():
    return request.headers.get("Authorization") == SECRET_KEY

def ensure_authenticated(force_refresh=False):
    """
    Rafraîchit le token Kia.
    Si force_refresh=True, tente de générer un nouveau token.
    Lève AuthenticationError si Kia exige 2FA.
    """
    try:
        if force_refresh:
            vehicle_manager.logout()  # Déconnecte l’ancien token si possible
        vehicle_manager.check_and_refresh_token()  # Vérifie ou rafraîchit le token
    except AuthenticationError as e:
        raise AuthenticationError(
            "Kia authentication failed. Open the Kia app and complete 2FA, then retry."
        ) from e

def refresh_and_sync():
    ensure_authenticated()
    vehicle_manager.update_all_vehicles_with_cached_state()

def get_vehicle_id():
    if VEHICLE_ID:
        return VEHICLE_ID
    vehicles = vehicle_manager.vehicles
    if not vehicles:
        raise ValueError("No vehicles found on the Kia account.")
    return next(iter(vehicles.keys()))

# =========================
# Logging
# =========================
@app.before_request
def log_request_info():
    print(f"Incoming request: {request.method} {request.path}")

# =========================
# Routes
# =========================
@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "OK", "service": "Kia Vehicle Control API"}), 200

@app.route("/check_token", methods=["GET"])
def check_token():
    """
    Vérifie si le token Kia est valide.
    """
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        ensure_authenticated()
        return jsonify({"status": "token_valid"}), 200
    except AuthenticationError as e:
        return jsonify({
            "status": "token_invalid",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401

@app.route("/refresh_token", methods=["POST"])
def refresh_token():
    """
    Tente de régénérer le token Kia automatiquement.
    """
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        ensure_authenticated(force_refresh=True)
        return jsonify({"status": "token_refreshed"}), 200
    except AuthenticationError as e:
        return jsonify({
            "status": "token_invalid",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401

@app.route("/unlock_car", methods=["POST"])
def unlock_car():
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    _ = request.get_json(silent=True)
    try:
        refresh_and_sync()
        vehicle_id = get_vehicle_id()
        result = vehicle_manager.unlock(vehicle_id)
        return jsonify({"status": "car_unlocked", "result": result}), 200
    except AuthenticationError as e:
        return jsonify({
            "error": "Authentication failed",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/lock_car", methods=["POST"])
def lock_car():
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    _ = request.get_json(silent=True)
    try:
        refresh_and_sync()
        vehicle_id = get_vehicle_id()
        result = vehicle_manager.lock(vehicle_id)
        return jsonify({"status": "car_locked", "result": result}), 200
    except AuthenticationError as e:
        return jsonify({
            "error": "Authentication failed",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/start_climate", methods=["POST"])
def start_climate():
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    _ = request.get_json(silent=True)
    try:
        refresh_and_sync()
        vehicle_id = get_vehicle_id()
        climate_options = ClimateRequestOptions(set_temp=72, duration=10)
        result = vehicle_manager.start_climate(vehicle_id, climate_options)
        return jsonify({"status": "climate_started", "result": result}), 200
    except AuthenticationError as e:
        return jsonify({
            "error": "Authentication failed",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stop_climate", methods=["POST"])
def stop_climate():
    if not authorize_request():
        return jsonify({"error": "Unauthorized"}), 403
    _ = request.get_json(silent=True)
    try:
        refresh_and_sync()
        vehicle_id = get_vehicle_id()
        result = vehicle_manager.stop_climate(vehicle_id)
        return jsonify({"status": "climate_stopped", "result": result}), 200
    except AuthenticationError as e:
        return jsonify({
            "error": "Authentication failed",
            "details": str(e),
            "action": "Open Kia app and complete 2FA"
        }), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# App Entry
# =========================
if __name__ == "__main__":
    print("Starting Kia Vehicle Control API...")
    app.run(host="0.0.0.0", port=8080)
