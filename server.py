from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from celery.result import AsyncResult
import uvicorn
import asyncio
import orchestrator

app = FastAPI(title="Mitra/UoM Legacy Modernization API", version="3.0")

class ModernizeJob(BaseModel):
    repo_url: str
    job_id: str # User-provided tag
    mode: str = "batch"

# Global mapping to track which Job ID corresponds to which Celery UUID
job_to_task_mapping = {}

@app.post("/api/v1/modernize")
async def trigger_modernization(job: ModernizeJob):
    """REST Endpoint: Drops the job into the Redis Mailbox."""
    
    # Hand off to Celery and get the assigned unique job ID
    task, final_job_id = orchestrator.start_enterprise_pipeline(job.repo_url, job.job_id)
    
    # Map the unique ID to the Celery Task for the WebSocket to find
    job_to_task_mapping[final_job_id] = task.id
    
    return {
        "status": "Accepted",
        "assigned_job_id": final_job_id,
        "celery_task_id": task.id,
        "message": f"Job initiated. Monitor via /ws/progress/{final_job_id}"
    }

@app.websocket("/ws/progress/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """WebSocket Endpoint: Pushes REAL-TIME updates from Redis."""
    await websocket.accept()
    
    celery_task_id = job_to_task_mapping.get(job_id)
    
    if not celery_task_id:
        await websocket.send_json({"error": "Job ID not found or already processed."})
        await websocket.close()
        return
    
    print(f"🌐 Web UI Monitoring Job: {job_id} (Task: {celery_task_id})")
    
    try:
        last_state = None
        while True:
            # Query the ACTUAL state from Redis
            result = AsyncResult(celery_task_id, app=orchestrator.celery_app)
            current_state = result.state
            
            # Only broadcast if the state has actually changed
            if current_state != last_state:
                await websocket.send_json({
                    "status": "processing",
                    "step": current_state,
                    "details": str(result.info) if result.info else "In Queue"
                })
                last_state = current_state
            
            # Exit if the job is finished or failed
            if current_state in ["SUCCESS", "FAILURE", "REVOKED"]:
                break
                
            await asyncio.sleep(1.0) # Poll Redis every second
            
    except WebSocketDisconnect:
        print(f"❌ Web UI Disconnected from Job: {job_id}")
    finally:
        # Cleanup mapping
        if job_id in job_to_task_mapping:
            del job_to_task_mapping[job_id]

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)