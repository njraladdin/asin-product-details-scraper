import json
import os
from pathlib import Path
from .logger import setup_logger

logger = setup_logger('Utils')

def load_config():
    """
    Load configuration from config.json file
    """
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            logger.info(f"Loaded configuration")
            return config
    except Exception as e:
        logger.error(f"Error loading config.json: {e}")
        # Return default configuration
        return {
            "initial_session_pool_size": 5,
            "allow_proxy": False,
            "concurrent_requests_control": {
                "initial_concurrent": 3,
                "scale_up_delay": 0.0005,
                "scale_increment": 2
            }
        } 