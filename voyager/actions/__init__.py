from .click import execute_click
from .extract_data import execute_extract_data
from .go_back import execute_go_back
from .google import execute_google
from .scroll import execute_scroll
from .success import execute_success
from .type import execute_type
from .wait import execute_wait
from .hover import execute_hover
from .go_to import execute_go_to
from ..types import VoyagerAction, StepExecution, EndExecution
from playwright.async_api import Page
from typing import List, Dict
import json # Import json for model_dump_json if needed, but model_dump returns dict

def map_voyager_action_to_string(action : VoyagerAction) -> str:
    return f"""
Executed : {action.type}
Reasoning : {action.reasoning}
Content ; {action.content}
Element : {action.element_number}
Success : True
"""

async def safe_execute_action(action : VoyagerAction, page : Page) -> StepExecution:
    """
    This function safely executes a Voyager Action
    and returns a message instance you can then append to the message history object.
    
    Accepts a Voyager instance, returns a message object and an optional Error Object as well
    """
    action_map = {
        "click" : execute_click,
        "hover" : execute_hover,
        "extract_data" : execute_extract_data,
        "go_to" : execute_go_to,
        "go_back" : execute_go_back,
        "google" : execute_google,
        "scroll" : execute_scroll,
        "success" : execute_success,
        "type" : execute_type,
        "wait" : execute_wait,
    }
    

    success_obj = None
    stop_obj = None

    try:
        element_to_pass = None
        if action.element_number is not None and action.element_number != "WINDOW":
            element_to_pass = page.locator(f'[data-voyager-element-index="{action.element_number}"]')
        
        # Call the action function with all three parameters
        await action_map[action.type](page=page, element=element_to_pass, content=action.content)

        if action.type == "success":
            success_obj = EndExecution(status=True, content=action.content, reason=action.reasoning)
        elif action.type == "stop":
            stop_obj = EndExecution(status=True, content=action.content, reason=action.reasoning)

        return StepExecution(
            message_formatted_string=map_voyager_action_to_string(action),
            message_json_string=json.dumps(action.model_dump(), indent=2),
            success=success_obj,
            stop=stop_obj
        )
    except Exception as e:
        return StepExecution(
            message_formatted_string=map_voyager_action_to_string(action),
            message_json_string=json.dumps(action.model_dump(), indent=2),
            error=str(e)
        )
