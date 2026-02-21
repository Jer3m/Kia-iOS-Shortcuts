import os
import json
from flask import Flask, request, jsonify
from hyundai_kia_connect_api import VehicleManager, ClimateRequestOptions
from hyundai_kia_connect_api.exceptions import (
    AuthenticationError, 
    AuthenticationOptionsRequiredError,
    TokenExpiredError
)
import upstash_redis

# 1. Création de l'instance Flask
index = Flask(__name__)

# 2. Point d'entrée pour Vercel (très important)
app = index 

# 3. Initialisation Redis
kv = upstash_redis.Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

# 4. Variables d'environnement
USERNAME = os.environ.get("KIA_USERNAME")
PASSWORD = os.environ.get("KIA_PASSWORD")
PIN = os.environ.get("KIA_PIN")
SECRET_KEY = os.environ.get("SECRET_KEY")

def get_vehicle_manager():
    vm = VehicleManager(
        region=1, brand=1, 
        username=USERNAME, password=PASSWORD, pin=str(PIN)
    )
    try:
        cached_session = kv.get("kia_session_cache")
        if cached_session:
            vm.set_session_cache(cached_session)
    except Exception as e:
        print(f"Erreur cache Redis: {e}")
    return vm

def save_session(vm):
    try:
        kv.set("kia_session_cache", vm.get_session_cache())
    except Exception as e:
        print(f"Erreur sauvegarde Redis: {e}")

def check_auth(req):
    return req.headers.get("Authorization") == SECRET_KEY

# --- ROUTES ---

@index.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Kia API Ready"}), 200

@index.route("/unlock_car", methods=["POST"])
def unlock():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.unlock(vehicle_id)
        save_session(vm)
        return jsonify({"status": "success", "action": "unlocked"}), 200
    except AuthenticationOptionsRequiredError as e:
        return jsonify({"error": "2FA_REQUIRED", "details": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@index.route("/lock_car", methods=["POST"])
def lock():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.lock(vehicle_id)
        save_session(vm)
        return jsonify({"status": "success", "action": "locked"}), 200
    except AuthenticationOptionsRequiredError as e:
        return jsonify({"error": "2FA_REQUIRED", "details": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@index.route("/start_climate", methods=["POST"])
def start_climate():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        options = ClimateRequestOptions(set_temp=21, duration=10)
        vm.start_climate(vehicle_id, options)
        save_session(vm)
        return jsonify({"status": "success", "action": "climate_started"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    index.run()
