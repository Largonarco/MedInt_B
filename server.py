import json
import uuid
import logging
import asyncio
from typing import Dict
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Local modules
from tools import ToolManager
from openai_realtime import OpenAIRealtimeManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Medical Interpreter API")
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Tool manager instance
tool_manager = ToolManager()

# Store active connections and conversation history
conversation_history: Dict[str, Dict] = {}
active_connections: Dict[str, WebSocket] = {}
openai_managers: Dict[str, OpenAIRealtimeManager] = {}


async def process_websocket_message(session_id: str, message: Dict):
    """Process incoming WebSocket messages."""
    message_type = message.get("type")
    websocket = active_connections.get(session_id)
    
    if not websocket:
        logger.error(f"WebSocket not found for session {session_id}")
        return
    
    try:
        if message_type == "connect":
            # Initialize OpenAI Realtime connection
            openai_manager = OpenAIRealtimeManager(
                on_audio_done=lambda: asyncio.create_task(send_audio_done(session_id)),
                on_text_done=lambda text: asyncio.create_task(send_text_done(session_id, text)),
                on_audio_delta=lambda delta: asyncio.create_task(send_audio_delta(session_id, delta)),
                on_response_done=lambda response: asyncio.create_task(send_response_done(session_id, response)),
                on_function_call=lambda name, args: asyncio.create_task(handle_function_call(session_id, name, args))
            )
            
            # Store manager instance
            openai_managers[session_id] = openai_manager
            
            # Connect to OpenAI
            await openai_manager.connect()
            
            # Notify client of successful connection
            await websocket.send_json({"type": "openai_connected"})
        
        elif message_type == "begin_conversation":
            # Process speech (language detection and translation)
            audio_base64 = message.get("audio", "")
            if not audio_base64:
                await websocket.send_json({"type": "error", "message": "Audio data is required"})
                return
            
            # Get OpenAI manager
            openai_manager = openai_managers.get(session_id)
            if not openai_manager:
                await websocket.send_json({"type": "error", "message": "OpenAI connection not initialized"})
                return
            
            # Get last doctor message for "repeat that" requests
            last_doctor_message = conversation_history[session_id].get("last_doctor_message", "")
            
            # Send to OpenAI for processing
            await openai_manager.process_speech(audio_base64, last_doctor_message)
        
        elif message_type == "get_summary":
            # Generate conversation summary
            openai_manager = openai_managers.get(session_id)
            if not openai_manager:
                await websocket.send_json({"type": "error", "message": "OpenAI connection not initialized"})
                return
            
            await openai_manager.generate_summary()
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await websocket.send_json({"type": "error", "message": str(e)})


async def send_text_done(session_id: str, text: str):
    """Send completed text to client."""
    websocket = active_connections.get(session_id)
    
    if websocket:        
        await websocket.send_json({"type": "text_done", "text": text})
        
async def send_audio_delta(session_id: str, delta: str):
    """Send audio delta to client."""
    websocket = active_connections.get(session_id)
    if websocket:
        await websocket.send_json({"type": "audio_response_delta", "delta": delta})

async def send_audio_done(session_id: str):
    """Notify client that audio is complete."""
    websocket = active_connections.get(session_id)
    if websocket:
        await websocket.send_json({"type": "audio_response_done"})

async def send_response_done(session_id: str, response: dict):
    """Send completed text to client."""
    response_type = response.get("type")
    websocket = active_connections.get(session_id)

    if not websocket:
        logger.error("Error executing response_done event as websocket conn was not available")

    # Based on the event type calling function or just sending text back
    if response_type == "function_call":
        call_id = response["call_id"]
        function_name = response["name"]
        openai_manager = openai_managers.get(session_id)
        function_args = json.loads(response["arguments"])

        if not openai_manager:
           logger.error("Error executing response_done event as openai_ws conn was not available")
        
        logger.info(f"Function call: {function_name} with arguments: {function_args}")
        
        try:
            if function_name == "schedule_follow_up":
                result = tool_manager.schedule_follow_up(function_args)
            elif function_name == "send_lab_order":
                result = tool_manager.send_lab_order(function_args)
            
            # Send result back to OpenAI
            await openai_manager.send_function_result(call_id, result)
            
            # Notify client about the action
            await websocket.send_json({
                "type": "action_executed",
                "action": function_name,
                "details": result
            })
            
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {str(e)}")
            await openai_manager.send_function_result(call_id, {"error": f"Error executing function {function_name}"})
        
    elif response_type == "message":
        print(response)
        parsed_json = json.loads(response["content"][0]["transcript"])
        msg = parsed_json["text"]
        role = parsed_json["role"]
        
        await websocket.send_json({"type": "response_done", "text": msg, "role": role})
            
        # Store in conversation history
        if session_id in conversation_history:
            if role == "doctor":  # Assuming translated text indicates source language
                conversation_history[session_id]["doctor_messages"].append(msg)
                conversation_history[session_id]["last_doctor_message"] = msg
            elif role == "patient":
                conversation_history[session_id]["patient_messages"].append(msg)
                conversation_history[session_id]["last_patient_message"] = msg


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "online", "service": "Medical Interpreter API"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    
    session_id = str(uuid.uuid4())
    active_connections[session_id] = websocket
    
    conversation_history[session_id] = {
        "doctor_messages": [],
        "patient_messages": [],
        "last_doctor_message": "",
        "last_patient_message": ""
    }
    
    await websocket.send_json({"type": "session", "session_id": session_id})
    
    try:
        async for message in websocket.iter_json():
            await process_websocket_message(session_id, message)
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
    finally:
        if session_id in active_connections:
            del active_connections[session_id]
        if session_id in conversation_history:
            del conversation_history[session_id]
        if session_id in openai_managers:
            await openai_managers[session_id].close()
            del openai_managers[session_id]