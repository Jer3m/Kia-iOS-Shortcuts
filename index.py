import os
from flask import Flask, request, jsonify
from hyundai_kia_connect_api import VehicleManager
import upstash_redis

app = Flask(__name__)

kv = upstash_redis.Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"), 
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

USERNAME = os.environ.get("KIA_USERNAME")
PASSWORD = os.environ.get("KIA_PASSWORD")
PIN = os.environ.get("KIA_PIN")
SECRET_KEY = os.environ.get("SECRET_KEY")

def get_vehicle_manager():
    # On initialise sans forcer la connexion immédiate
    vm = VehicleManager(
        region=1, brand=1, 
        username=USERNAME, password=PASSWORD, pin=str(PIN)
    )
    
    cached_session = kv.get("kia_session_cache")
    if cached_session:
        try:
            vm.set_session_cache(cached_session)
            return vm
        except:
            pass
    return vm

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Ready for Refresh Token"}), 200

@app.route("/unlock_car", methods=["POST"])
def unlock():
    if request.headers.get("Authorization") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    
    vm = get_vehicle_manager()
    try:
        # Cette ligne est cruciale : elle va essayer de transformer 
        # tes identifiants en "Refresh Token"
        vm.check_and_refresh_token() 
        
        vm.update_all_vehicles_with_cached_state()
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.unlock(vehicle_id)
        
        # Sauvegarde immédiate du précieux token dans Redis
        kv.set("kia_session_cache", vm.get_session_cache())
        return jsonify({"status": "success", "action": "unlocked"}), 200
    
    except Exception as e:
        err = str(e)
        # Si Kia demande le token, on capture l'erreur pour voir si un 2FA est proposé
        return jsonify({
            "error": "AUTH_STEP_REQUIRED",
            "message": "Kia refuse le mot de passe direct",
            "details": err
        }), 401

if __name__ == "__main__":
    app.run()
