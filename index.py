import os
import json
from flask import Flask, request, jsonify
from hyundai_kia_connect_api import VehicleManager, ClimateRequestOptions
import upstash_redis

app = Flask(__name__)

# Initialisation Redis
kv = upstash_redis.Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

# Variables d'environnement
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
    except:
        pass
    return vm

def save_session(vm):
    try:
        kv.set("kia_session_cache", vm.get_session_cache())
    except:
        pass

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Kia API Ready"}), 200

@app.route("/unlock_car", methods=["POST"])
def unlock():
    if request.headers.get("Authorization") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.unlock(vehicle_id)
        save_session(vm)
        return jsonify({"status": "success", "action": "unlocked"}), 200
    except Exception as e:
        # Si c'est une erreur de 2FA, le message contiendra "MFA" ou "auth"
        error_msg = str(e)
        if "MFA" in error_msg or "auth" in error_msg.lower():
            return jsonify({"error": "2FA_REQUIRED", "details": error_msg}), 401
        return jsonify({"error": error_msg}), 500

@app.route("/lock_car", methods=["POST"])
def lock():
    if request.headers.get("Authorization") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        vm = get_vehicle_manager()
        vm.check_and_refresh_token()
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.lock(vehicle_id)
        save_session(vm)
        return jsonify({"status": "success", "action": "locked"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run()
