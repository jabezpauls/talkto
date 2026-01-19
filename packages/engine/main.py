#!/usr/bin/env python3
"""
RAG Engine - JSON stdin/stdout interface for Node.js CLI
"""

import sys
import json
import logging
from datetime import datetime

from src.protocol.handler import CommandHandler
from src.protocol.errors import EngineError

# Configure logging to stderr (stdout is for JSON only)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def send_response(response: dict) -> None:
    """Send JSON response to stdout"""
    json.dump(response, sys.stdout)
    sys.stdout.write('\n')
    sys.stdout.flush()


def send_success(request_id: str, action: str, data: dict = None) -> None:
    """Send success response"""
    send_response({
        "id": request_id,
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "data": data or {}
    })


def send_error(request_id: str, code: str, message: str, details: any = None) -> None:
    """Send error response"""
    send_response({
        "id": request_id,
        "status": "error",
        "timestamp": datetime.now().isoformat(),
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    })


def send_stream_chunk(request_id: str, chunk_type: str, content: str = None, source: dict = None) -> None:
    """Send streaming chunk"""
    data = {"type": chunk_type}
    if content is not None:
        data["content"] = content
    if source is not None:
        data["source"] = source

    send_response({
        "id": request_id,
        "status": "streaming",
        "timestamp": datetime.now().isoformat(),
        "data": data
    })


def main():
    logger.info("RAG Engine starting...")

    # Initialize command handler
    handler = CommandHandler()

    # Send ready signal
    send_response({
        "id": "ready",
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "data": {"message": "Engine ready"}
    })

    # Main loop - read JSON lines from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request_id = "unknown"
        action = "unknown"

        try:
            request = json.loads(line)
            request_id = request.get("id", "unknown")
            action = request.get("action", "unknown")

            logger.info(f"Received request: {action} (id={request_id})")

            # Check for streaming request
            options = request.get("options", {})
            stream = options.get("stream", False)

            # Route to handler
            if stream and action == "query":
                # Streaming response
                for chunk in handler.handle_streaming(request):
                    send_stream_chunk(
                        request_id,
                        chunk["type"],
                        chunk.get("content"),
                        chunk.get("source")
                    )
            else:
                # Normal response
                result = handler.handle(request)
                send_success(request_id, action, result)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            send_error(request_id, "INVALID_JSON", str(e))

        except EngineError as e:
            logger.error(f"Engine error: {e}")
            send_error(request_id, e.code, e.message, e.details)

        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            send_error(request_id, "INTERNAL_ERROR", str(e))


if __name__ == "__main__":
    main()
