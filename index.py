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
    # Initialisation sans connexion forcée
    vm = VehicleManager(
        region=1, brand=1, 
        username=USERNAME, password=PASSWORD, pin=str(PIN)
    )
    
    # On vérifie si on a un token en cache
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
    return jsonify({"status": "online", "message": "Ready"}), 200

@app.route("/unlock_car", methods=["POST"])
def unlock():
    if request.headers.get("Authorization") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 403
    
    vm = get_vehicle_manager()
    try:
        # On force la mise à jour du token (indispensable maintenant)
        vm.check_and_refresh_token() 
        vm.update_all_vehicles_with_cached_state()
        
        if not vm.vehicles:
            return jsonify({"error": "No vehicles found"}), 404
            
        vehicle_id = next(iter(vm.vehicles.keys()))
        vm.unlock(vehicle_id)
        
        # On sauvegarde le jeton tout de suite après succès
        kv.set("kia_session_cache", vm.get_session_cache())
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        return jsonify({
            "error": "AUTH_FAILED",
            "details": str(e),
            "hint": "Essayez de vous deconnecter/reconnecter sur l'app Kia mobile"
        }), 401

if __name__ == "__main__":
    app.run()
