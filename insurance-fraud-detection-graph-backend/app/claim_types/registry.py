from typing import Tuple, Type
from pydantic import BaseModel
import os

from app.claim_types.health.schema import HealthClaim
from app.claim_types.life.schema import LifeClaim
from app.claim_types.motor.schema import MotorClaim
from app.claim_types.mobile.schema import MobileClaim
from app.claim_types.property.schema import PropertyClaim
from app.claim_types.travel.schema import TravelClaim

# Map doc_type string to (SchemaClass, prompt_file_path)
REGISTRY = {
    "health": {
        "schema": HealthClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "health/prompt.txt")
    },
    "life": {
        "schema": LifeClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "life/prompt.txt")
    },
    "motor": {
        "schema": MotorClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "motor/prompt.txt")
    },
    "mobile": {
        "schema": MobileClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "mobile/prompt.txt")
    },
    "property": {
        "schema": PropertyClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "property/prompt.txt")
    },
    "travel": {
        "schema": TravelClaim,
        "prompt_file": os.path.join(os.path.dirname(__file__), "travel/prompt.txt")
    }
}

def load_resources(doc_type: str) -> Tuple[Type[BaseModel], str]:
    if doc_type not in REGISTRY:
        raise ValueError(
            f"Unsupported doc_type '{doc_type}'. Supported: {', '.join(sorted(REGISTRY.keys()))}"
        )
    
    entry = REGISTRY[doc_type]
    with open(entry["prompt_file"], "r") as f:
        prompt_text = f.read()
        
    return entry["schema"], prompt_text