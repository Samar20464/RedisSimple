import os

import redis
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    decode_responses=True,
)
ITEMS_KEY = "items"
SEQUENCE_KEY = "item:next_id"


def item_key(item_id):
    return f"item:{item_id}"


def serialize(item_id, data):
    return {
        "id": item_id,
        "name": data.get("name", ""),
        "description": data.get("description", ""),
    }


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/items", methods=["GET"])
def list_items():
    ids = redis_client.smembers(ITEMS_KEY)
    items = []
    for item_id in ids:
        data = redis_client.hgetall(item_key(item_id))
        if data:
            items.append(serialize(int(item_id), data))
    items.sort(key=lambda item: item["id"])
    return jsonify(items)


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    data = redis_client.hgetall(item_key(item_id))
    if not data:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(serialize(item_id, data))


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    item_id = redis_client.incr(SEQUENCE_KEY)
    pipeline = redis_client.pipeline()
    pipeline.hset(item_key(item_id), mapping={"name": name, "description": description})
    pipeline.sadd(ITEMS_KEY, item_id)
    pipeline.execute()
    return jsonify({"id": item_id, "name": name, "description": description}), 201


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not redis_client.exists(item_key(item_id)):
        return jsonify({"error": "Item not found"}), 404

    redis_client.hset(item_key(item_id), mapping={"name": name, "description": description})
    return jsonify({"id": item_id, "name": name, "description": description})


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    if not redis_client.exists(item_key(item_id)):
        return jsonify({"error": "Item not found"}), 404

    pipeline = redis_client.pipeline()
    pipeline.delete(item_key(item_id))
    pipeline.srem(ITEMS_KEY, item_id)
    pipeline.execute()
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
