from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import requests
import os
import logging
from auth import get_current_admin_user

router = APIRouter(prefix="/deployment", tags=["Deployment"])

# Jenkins Configuration
JENKINS_URL = os.getenv("JENKINS_URL", "http://jenkins.lb-automotive.internal:8080")
JENKINS_USER = os.getenv("JENKINS_USER")
JENKINS_TOKEN = os.getenv("JENKINS_TOKEN")
JENKINS_JOB = os.getenv("JENKINS_JOB", "lb-automotive-deploy")

logger = logging.getLogger(__name__)

class TriggerResponse(BaseModel):
    message: str
    queue_item_url: str

@router.post("/trigger", response_model=TriggerResponse)
async def trigger_deployment(current_user: dict = Depends(get_current_admin_user)):
    """
    Trigger a new deployment build on Jenkins.
    """
    if not JENKINS_USER or not JENKINS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jenkins credentials not configured"
        )

    try:
        # Trigger build
        crumb_response = requests.get(
            f"{JENKINS_URL}/crumbIssuer/api/json",
            auth=(JENKINS_USER, JENKINS_TOKEN)
        )
        
        headers = {}
        if crumb_response.status_code == 200:
            crumb = crumb_response.json()
            headers[crumb["crumbRequestField"]] = crumb["crumb"]

        response = requests.post(
            f"{JENKINS_URL}/job/{JENKINS_JOB}/build",
            auth=(JENKINS_USER, JENKINS_TOKEN),
            headers=headers
        )

        if response.status_code == 201:
            return {
                "message": "Deployment triggered successfully",
                "queue_item_url": response.headers.get("Location")
            }
        else:
            logger.error(f"Failed to trigger Jenkins build: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to trigger deployment: {response.status_code}"
            )

    except requests.RequestException as e:
        logger.error(f"Jenkins connection error: {str(e)}")
        # MED-6: Do not leak internal network/Jenkins details to clients
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deployment service temporarily unavailable. Check server logs."
        )

@router.get("/status")
async def get_deployment_status(current_user: dict = Depends(get_current_admin_user)):
    """
    Get the status of the latest build.
    """
    if not JENKINS_USER or not JENKINS_TOKEN:
        return {"status": "unknown", "detail": "Credentials missing"}

    try:
        # Get job info to find last build
        response = requests.get(
            f"{JENKINS_URL}/job/{JENKINS_JOB}/api/json",
            auth=(JENKINS_USER, JENKINS_TOKEN)
        )
        
        if response.status_code != 200:
             raise HTTPException(status_code=500, detail="Failed to fetch job info")

        job_info = response.json()
        last_build = job_info.get("lastBuild")
        
        if not last_build:
            return {"status": "idle", "build_number": None}

        # Get build details
        build_number = last_build["number"]
        build_response = requests.get(
            f"{JENKINS_URL}/job/{JENKINS_JOB}/{build_number}/api/json",
            auth=(JENKINS_USER, JENKINS_TOKEN)
        )
        
        if build_response.status_code != 200:
            return {"status": "unknown", "build_number": build_number}

        build_info = build_response.json()
        
        return {
            "status": "building" if build_info["building"] else build_info["result"],
            "build_number": build_number,
            "timestamp": build_info["timestamp"],
            "duration": build_info["duration"],
            "estimated_duration": build_info["estimatedDuration"]
        }

    except requests.RequestException as e:
        logger.error(f"Jenkins connection error: {str(e)}")
        return {"status": "error", "detail": str(e)}

@router.get("/logs/{build_number}")
async def get_build_logs(build_number: int, start: int = 0, current_user: dict = Depends(get_current_admin_user)):
    """
    Get progressive logs for a build.
    """
    try:
        response = requests.get(
            f"{JENKINS_URL}/job/{JENKINS_JOB}/{build_number}/logText/progressiveText",
            params={"start": start},
            auth=(JENKINS_USER, JENKINS_TOKEN)
        )
        
        more_data = response.headers.get("X-More-Data") == "true"
        new_start = response.headers.get("X-Text-Size")
        
        return {
            "logs": response.text,
            "more_data": more_data,
            "next_start": new_start
        }
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
