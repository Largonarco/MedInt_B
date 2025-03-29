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

# Store active connections and conversation history
conversation_history: Dict[str, Dict] = {}
active_connections: Dict[str, WebSocket] = {}
openai_managers: Dict[str, OpenAIRealtimeManager] = {}

# Tool manager instance
tool_manager = ToolManager()

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
                on_text_delta=lambda delta: asyncio.create_task(send_text_delta(session_id, delta)),
                on_text_done=lambda text: asyncio.create_task(send_text_done(session_id, text)),
                on_audio_delta=lambda delta: asyncio.create_task(send_audio_delta(session_id, delta)),
                on_audio_done=lambda: asyncio.create_task(send_audio_done(session_id)),
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

async def send_text_delta(session_id: str, delta: str):
    """Send text delta to client."""
    websocket = active_connections.get(session_id)
    if websocket:
        await websocket.send_json({"type": "text_response_delta", "delta": delta})

async def send_text_done(session_id: str, text: str):
    """Send completed text to client."""
    websocket = active_connections.get(session_id)
    if websocket:
        clean_text = text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]  # Remove ```json
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]  # Remove ```
        clean_text = clean_text.strip()  # Remove any extra whitespace

        # Parse the cleaned JSON string
        parsed_data = json.loads(clean_text)
        role = parsed_data.get("role", "")
        message_text = parsed_data.get("text", "")
        
        await websocket.send_json({"type": "text_response_done", "text": text, "role": role})
        
        # Store in conversation history
        if session_id in conversation_history:
            if role == "doctor":  # Assuming translated text indicates source language
                conversation_history[session_id]["doctor_messages"].append(text)
                conversation_history[session_id]["last_doctor_message"] = text
            elif role == "patient":
                conversation_history[session_id]["patient_messages"].append(text)
                conversation_history[session_id]["last_patient_message"] = text

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

async def handle_function_call(session_id: str, function_name: str, function_args: Dict):
    """Handle function calls from OpenAI."""
    websocket = active_connections.get(session_id)
    openai_manager = openai_managers.get(session_id)
    
    if not websocket or not openai_manager:
        return
    
    try:
        logger.info(f"Function call: {function_name} with arguments: {function_args}")
        
        if function_name == "schedule_follow_up":
            result = await tool_manager.schedule_follow_up(function_args)
        elif function_name == "send_lab_order":
            result = await tool_manager.send_lab_order(function_args)
        else:
            result = {"error": f"Unknown function: {function_name}"}
        
        # Send result back to OpenAI
        await openai_manager.send_function_result(function_name, result)
        
        # Notify client about the action
        await websocket.send_json({
            "type": "action_executed",
            "action": function_name,
            "details": result
        })
        
    except Exception as e:
        logger.error(f"Error executing function {function_name}: {str(e)}")
        await openai_manager.send_function_result(function_name, {"error": str(e)})

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