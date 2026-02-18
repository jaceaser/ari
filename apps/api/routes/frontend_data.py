"""
API routes for frontend data persistence (documents, suggestions, votes, messages).

These endpoints replace the SQLite-backed queries.ts in the Next.js frontend,
allowing the web app to run without any local database.
All data is stored in Cosmos DB via the SessionsCosmosClient.
"""

from quart import Blueprint, jsonify, request

from cosmos import SessionsCosmosClient

frontend_data_bp = Blueprint("frontend_data", __name__)


def _get_cosmos():
    """Get Cosmos client or return 503."""
    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return None
    return cosmos


def _user_id():
    """Get authenticated user ID from request context (set by auth middleware)."""
    return getattr(request, "user_id", None)


# ── Messages ──


@frontend_data_bp.route("/data/messages", methods=["POST"])
async def save_messages():
    """Save messages (batch). Body: { chatId, messages: [...] }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    chat_id = body.get("chatId")
    messages = body.get("messages", [])
    if not chat_id or not messages:
        return jsonify({"error": "chatId and messages are required"}), 400

    saved = await cosmos.save_messages(user_id, chat_id, messages)
    return jsonify(saved), 200


@frontend_data_bp.route("/data/messages/<message_id>", methods=["GET"])
async def get_message(message_id):
    """Get a single message by ID."""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    msg = await cosmos.get_message_by_id(user_id, message_id)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(msg), 200


@frontend_data_bp.route("/data/messages/<message_id>", methods=["PATCH"])
async def update_message(message_id):
    """Update a message. Body: { parts: "..." }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    updates = {}
    if "parts" in body:
        updates["parts"] = body["parts"]
        updates["content"] = body["parts"]
    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    msg = await cosmos.update_message(user_id, message_id, updates)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(msg), 200


@frontend_data_bp.route("/data/messages/delete-after", methods=["POST"])
async def delete_messages_after():
    """Delete messages after a timestamp. Body: { chatId, timestamp }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    chat_id = body.get("chatId")
    timestamp = body.get("timestamp")
    if not chat_id or timestamp is None:
        return jsonify({"error": "chatId and timestamp are required"}), 400

    deleted = await cosmos.delete_messages_after_timestamp(user_id, chat_id, timestamp)
    return jsonify({"deleted": deleted}), 200


@frontend_data_bp.route("/data/messages/count", methods=["GET"])
async def message_count():
    """Count user messages in the last N hours. Query: ?hours=24"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"count": 0}), 200
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    hours = int(request.args.get("hours", "24"))
    count = await cosmos.get_message_count(user_id, hours)
    return jsonify({"count": count}), 200


# ── Documents ──


@frontend_data_bp.route("/data/documents", methods=["POST"])
async def save_document():
    """Save a document. Body: { id, title, kind, content }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    doc_id = body.get("id")
    title = body.get("title", "")
    kind = body.get("kind", "text")
    content = body.get("content")
    if not doc_id:
        return jsonify({"error": "id is required"}), 400

    doc = await cosmos.save_document(user_id, doc_id, title, kind, content)
    return jsonify(doc), 200


@frontend_data_bp.route("/data/documents/<doc_id>", methods=["GET"])
async def get_documents(doc_id):
    """Get all versions of a document or latest only (query: ?latest=true)."""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify([]), 200
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    latest = request.args.get("latest", "").lower() == "true"
    if latest:
        doc = await cosmos.get_document_by_id(user_id, doc_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404
        return jsonify(doc), 200

    docs = await cosmos.get_documents_by_id(user_id, doc_id)
    return jsonify(docs), 200


@frontend_data_bp.route("/data/documents/<doc_id>/delete-after", methods=["POST"])
async def delete_documents_after(doc_id):
    """Delete document versions after a timestamp. Body: { timestamp }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    timestamp = body.get("timestamp")
    if timestamp is None:
        return jsonify({"error": "timestamp is required"}), 400

    deleted = await cosmos.delete_documents_after_timestamp(user_id, doc_id, timestamp)
    return jsonify(deleted), 200


# ── Suggestions ──


@frontend_data_bp.route("/data/suggestions", methods=["POST"])
async def save_suggestions():
    """Save suggestions. Body: { suggestions: [...] }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    suggestions = body.get("suggestions", [])
    if not suggestions:
        return jsonify({"error": "suggestions array is required"}), 400

    saved = await cosmos.save_suggestions(user_id, suggestions)
    return jsonify(saved), 200


@frontend_data_bp.route("/data/suggestions", methods=["GET"])
async def get_suggestions():
    """Get suggestions by document ID. Query: ?documentId=<id>"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify([]), 200
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    doc_id = request.args.get("documentId")
    if not doc_id:
        return jsonify({"error": "documentId is required"}), 400

    suggestions = await cosmos.get_suggestions_by_document_id(user_id, doc_id)
    return jsonify(suggestions), 200


# ── Votes ──


@frontend_data_bp.route("/data/votes", methods=["POST"])
async def vote_message():
    """Vote on a message. Body: { chatId, messageId, type: "up"|"down" }"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    body = await request.get_json()
    chat_id = body.get("chatId")
    message_id = body.get("messageId")
    vote_type = body.get("type")
    if not all([chat_id, message_id, vote_type]):
        return jsonify({"error": "chatId, messageId, and type are required"}), 400

    is_upvoted = 1 if vote_type == "up" else 0
    vote = await cosmos.vote_message(user_id, chat_id, message_id, is_upvoted)
    return jsonify(vote), 200


@frontend_data_bp.route("/data/votes", methods=["GET"])
async def get_votes():
    """Get votes by chat ID. Query: ?chatId=<id>"""
    cosmos = _get_cosmos()
    if not cosmos:
        return jsonify([]), 200
    user_id = _user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    chat_id = request.args.get("chatId")
    if not chat_id:
        return jsonify({"error": "chatId is required"}), 400

    votes = await cosmos.get_votes_by_chat_id(user_id, chat_id)
    return jsonify(votes), 200
