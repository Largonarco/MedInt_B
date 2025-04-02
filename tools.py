import os
import json
import aiohttp
import requests
import logging
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolManager:
    """Handles function tool execution for medical actions."""
    
    def __init__(self):
        """Initialize the tool manager."""
        self.webhook_url = os.getenv("WEBHOOK_URL", "https://webhook.site/91c97f36-0a2d-40f2-a300-cf6d8e768814")
        logger.info(f"Using webhook URL: {self.webhook_url}")
    
    def schedule_follow_up(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a follow-up appointment for a patient.
        
        Args:
            params: Dictionary with parameters:
                - patientName: Name of the patient
                - date: Date for the appointment (YYYY-MM-DD)
                - reason: Reason for the appointment
                
        Returns:
            Dictionary with the result of the appointment scheduling
        """
        try:
            # Validate required parameters
            if not params.get("patientName"):
                raise ValueError("Patient name is required")
            if not params.get("date"):
                raise ValueError("Appointment date is required")
            
            # Default reason if not provided
            reason = params.get("reason", "Follow-up appointment")
                        
            # Send appointment data to webhook
            response = requests.post(
                self.webhook_url,
                json={
                "reason": reason,
                "action": "schedule_follow_up",
                "appointment_date": params["date"],
                "patient_name": params["patientName"],
                "timestamp": datetime.now().isoformat()
                },
                headers={"Content-Type": "application/json"}
            )
            response_status = response.status_code
            
            # Return success response
            return {
                "success": True,
                "message": f"Follow-up appointment scheduled for {params['patientName']} on {params['date']} for {reason}",
                "appointmentId": f"APPT-{datetime.now().timestamp():.0f}",
                "webhookResponse": response_status
            }
        
        except Exception as e:
            logger.error(f"Error scheduling follow-up: {str(e)}")
            raise ValueError(f"Failed to schedule follow-up: {str(e)}")
    
    def send_lab_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a lab order for a patient.
        
        Args:
            params: Dictionary with parameters:
                - patientName: Name of the patient
                - testType: Type of lab test
                - urgency: Urgency level (routine, urgent, stat)
                
        Returns:
            Dictionary with the result of the lab order
        """
        try:
            # Validate required parameters
            if not params.get("patientName"):
                raise ValueError("Patient name is required")
                # Validate required parameters
            if not params.get("testType"):
                raise ValueError("Test type is required")
            # Default urgency if not provided
            urgency = params.get("urgency", "routine")
                        
            # Send lab order data to webhook
            response = requests.post(
                self.webhook_url,
                json={
                "urgency": urgency,
                "action": "send_lab_order",
                "test_type": params["testType"],
                "patient_name": params["patientName"],
                "timestamp": datetime.now().isoformat()
                },
                headers={"Content-Type": "application/json"}
            )
            response_status = response.status_code

            
            # Return success response
            return {
                "success": True,
                "webhookResponse": response_status,
                "orderId": f"LAB-{datetime.now().timestamp():.0f}",
                "message": f"Lab order for {params['testType']} sent for {params['patientName']} with {urgency} urgency",
            }
        
        except Exception as e:
            logger.error(f"Error sending lab order: {str(e)}")
            raise ValueError(f"Failed to send lab order: {str(e)}")