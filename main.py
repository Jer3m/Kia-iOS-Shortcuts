import os
import json
from flask import Flask, request, jsonify
from hyundai_kia_connect_api import VehicleManager, ClimateRequestOptions
from hyundai_kia_connect_api.exceptions import AuthenticationError
import upstash_redis

app = Flask(__name__)

# Initialisation du client Redis (Vercel KV)
kv = upstash_redis.Redis.from_env()

# Variables d'environnement
USERNAME = os.environ.get("KIA_USERNAME")
PASSWORD = os.environ.get("KIA_PASSWORD")
PIN = os.environ.get("KIA_PIN")
SECRET_KEY = os.environ.get("SECRET_KEY")

def get_vehicle_manager():
    """Initialise le manager et charge le cache depuis Redis s'il existe."""
    vm = VehicleManager(
        region=1, brand=1, 
        username=USERNAME, password=PASSWORD, pin=str(PIN)
    )
    
    cached_session = kv.get("kia_session_cache")
    if cached_session:
        try:
            # Si le cache est une chaîne (JSON), on le charge
            vm.set_session_cache(cached_session)
        except Exception as e:
            print(f"Erreur chargement cache: {e}")
            
    return vm

def save_session_cache(vm):
    """Sauvegarde l'état actuel de la session dans Redis."""
    try:
        session_data = vm.get_session_cache()
        kv.set("kia_session_cache", session_data)
    except Exception as e:
        print(f"Erreur sauvegarde cache: {e}")

def authorize(req):
    return req.headers.get("Authorization") == SECRET_KEY

# --- ROUTES ---

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "online", "message": "Kia API with KV Cache"}), 200

@app.route("/unlock_car", methods=["POST"])
def unlock():
    if not authorize(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        
        vehicle_id = next(iter(vm.vehicles.keys()))
        result = vm.unlock(vehicle_id)
        
        save_session_cache(vm)
        return jsonify({"status": "unlocked", "result": str(result)}), 200
    except AuthenticationError:
        return jsonify({"error": "2FA_REQUIRED", "action": "Ouvrez l'app Kia Connect"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/lock_car", methods=["POST"])
def lock():
    if not authorize(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        
        vehicle_id = next(iter(vm.vehicles.keys()))
        result = vm.lock(vehicle_id)
        
        save_session_cache(vm)
        return jsonify({"status": "locked", "result": str(result)}), 200
    except AuthenticationError:
        return jsonify({"error": "2FA_REQUIRED"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/start_climate", methods=["POST"])
def start_climate():
    if not authorize(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        
        vehicle_id = next(iter(vm.vehicles.keys()))
        # Réglage par défaut : 21°C (70°F environ)
        options = ClimateRequestOptions(set_temp=21, duration=10)
        result = vm.start_climate(vehicle_id, options)
        
        save_session_cache(vm)
        return jsonify({"status": "climate_started", "result": str(result)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
