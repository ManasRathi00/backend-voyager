from pydantic import BaseModel
from typing import Optional, List, Dict
    
# Voyager Task
class VoyagerTask(BaseModel):
    start_url : str
    prompt : str
    max_iterations : int = 100
    
# "actions" : [{
#             "element_number" : [numerical element] -- element number of the element that needs to be scrolled. 
#                 "WINDOW" by default if you wanna scroll the entire screen
#             "content" : ["up" or "down"] -- Direction being scrolled in
#             "Thought" - A "" A step-by-step breakdown of your thought and the action you chose to take. 
#                 Make sure do step by step here, and think clearly before taking an action.
#        }]


class VoyagerAction(BaseModel):
    type : str
    element_number : int
    content : Optional[str]
    reasoning : str
    
class VoyagerStep(BaseModel):
    image_base_64 : Optional[str] = None
    actions : List[VoyagerAction]
    
class EndExecution(BaseModel):
    status : bool
    content : str
    reason : str
class StepExecution(BaseModel):
    message_formatted_string : str
    message_json_string : str
    error : Optional[str] = None
    success : Optional[EndExecution] = None
    stop : Optional[EndExecution] = None