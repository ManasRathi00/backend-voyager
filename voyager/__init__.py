from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from config.logger import logger
from config.settings import settings
import base64

from utils import json_parser

from litellm import acompletion
from playwright.async_api import BrowserContext, Page
from .prompts.system_prompt import SYSTEM_PROMPT
from .types import VoyagerTask, VoyagerStep, VoyagerAction  # assume these are defined

from .actions import safe_execute_action

class Voyager:
    """
    High-level wrapper around Playwright for scripted browsing 'tasks'.
    """

    def __init__(
        self,
        max_concurrency: int = 10,
        return_images: bool = True,
    ) -> None:
        with open("voyager/scripts/browser-annotate.js", "r", encoding="utf-8") as f:
            self.annotate_script = f.read()
            
        with open("voyager/scripts/clear-rects.js", "r", encoding="utf-8") as f:
            self.clear_script = f.read()
        
        
        

        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images

        self.system_prompt: Optional[str] = None


    async def start_task(
        self,
        browser_context: BrowserContext, # Accept BrowserContext directly
        task: VoyagerTask
    ) -> None:
        """
        Start a browser session for a task.
        `callback` will be invoked for each step with the VoyagerStep data.
        """
        async with self.concurrency_semaphore:
            task_page = None
            try:
                logger.info(f"Starting task: {task.prompt} at {task.start_url}")
                task_page = await browser_context.new_page()

                self.system_prompt = SYSTEM_PROMPT
                message_history = [{"role" : "developer", "content" : self.system_prompt}, 
                                   {"role" : "user", "content" : f"Task Assigned by the user : {task.prompt}"}
                                   ]
            
                iteration = 0
                await task_page.goto(task.start_url)
                await task_page.wait_for_load_state("domcontentloaded")
                
                execution_log_buffer = ""
                success = False
                stop = False
                while iteration < task.max_iterations:
                    logger.info(f"Iteration {iteration + 1}/{task.max_iterations}")
                    
                    # Wait for the page to be stable after any navigation
                    
                    
                    # Inject and execute annotation script to get element rectangles
                    all_indexes = await task_page.evaluate(self.annotate_script)
                    
                    page_bytes = await task_page.screenshot()
                    
                    screenshot_base_64 = base64.b64encode(page_bytes).decode()
                    
                    # Clear the annotations from the page
                    await task_page.evaluate(self.clear_script)
                    # This is the function to remove all previous base_64 images from the messages object (to manage context)
                    message_history = self.clear_images_from_message_history(message_history=message_history)
                    
                    # This is to create a new message object with the latest base 64 image
                    message_history = self.add_latest_user_message_with_screenshot(screenshot_base_64=screenshot_base_64,message_history=message_history, additional_message=execution_log_buffer)
                    logger.info("Calling AI for next actions...")
                    response = await self.call_ai(message_history=message_history)
                    logger.info("AI response received.")
                    
                    voyager_actions = response[0]
                    raw_response = response[1]
                    
                    # 1) The message from the assistant should be added back to the message history as IS the raw one
                    message_history.append({"role" : "assistant", "content" : raw_response })

                    # Clearing Execution Log Buffer
                    execution_log_buffer = "Logs from the last step : \n"
                    
                    for i, action in enumerate(voyager_actions):
                        logger.info(f"Executing action {i + 1}/{len(voyager_actions)}: {action.type}")
                        logger.info(action.model_dump())
                        
                        action_resp = await safe_execute_action(action,task_page)

                        # wait for stability
                        await task_page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(0.5)

                        if action_resp.success:
                            logger.info(f"Action {action.type} succeeded: {action_resp.success.content}")
                            execution_log_buffer += f"\nTask completed successfully: {action_resp.success.content}"
                            success = True
                            break # Break the loop if task is successful
                        
                        
                        if action_resp.stop:
                            logger.info(f"Action {action.type} stopped: {action_resp.stop.reason}")
                            execution_log_buffer += f"\nTask stopped: {action_resp.stop.reason}"
                            stop = True
                            break # Break the loop if task is stopped
                        
                            
                        if action_resp.error:
                            logger.error(f"Error executing action {action.type}: {action_resp.message_formatted_string}. Details: {action_resp.error}")
                            execution_log_buffer += f"\nError executing action: {action_resp.message_formatted_string}\nError details: {action_resp.error}"
                            continue # Continue to next action if there's an error
                            
                        # Updating the action log buffer
                        logger.info(action_resp.message_formatted_string)
                        execution_log_buffer += f"\n{action_resp.message_formatted_string}"
                    iteration += 1
                    
                    # checking for success or stop
                    if task.callback:
                        await task.callback(VoyagerStep(image_base_64=screenshot_base_64,actions=voyager_actions))
                        
                        
                    if success or stop:
                        break
                    
                    
                    await task_page.wait_for_load_state("load")
                    await asyncio.sleep(1)
                    
            finally:
                if task_page:
                    logger.info(f"Closing page for task: {task.prompt}")
                    await task_page.close()
                    
    async def get_page_web_element_rect(self, page: Page):
        all_indexes = await page.evaluate(self.annotate_script)
        return all_indexes

        
    async def clear_rects(self, page : Page):
        await page.evaluate(self.clear_script)
        
    
        
    def clear_images_from_message_history(
        self,
        message_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Replaces image_url entries in message history with a placeholder message.

        Args:
            message_history: A list of messages following the OpenAI-style structure:
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "..."},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                        ]
                    }
                ]

        Returns:
            A new list of messages where image_url entries are replaced with:
            {"type": "text", "text": "[Placeholder: image was already processed]"}
        """

        cleaned_messages = []

        for message in message_history:
            # Skip malformed messages
            if "content" not in message:
                continue

            content = message["content"]

            # Handle multi-part (list) content
            if isinstance(content, list):
                new_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "image_url":
                            new_content.append({
                                "type": "text",
                                "text": "[Placeholder: image already processed]"
                            })
                        else:
                            new_content.append(part)
                cleaned_messages.append({
                    "role": message["role"],
                    "content": new_content
                })

            # Handle simple string content (legacy format)
            elif isinstance(content, str):
                cleaned_messages.append(message)

            # Skip unexpected types silently
            else:
                continue

        return cleaned_messages
                    
        
    def add_latest_user_message_with_screenshot(
        self,
        screenshot_base_64: str,
        message_history: List[Dict[str, Any]],
        additional_message: Optional[str] = None # New parameter
    ) -> List[Dict[str, Any]]:
        """
        Appends a new user message containing the task prompt and current page screenshot
        to the existing message history.

        Args:
            screenshot_base_64: Base64 string of the current page screenshot.
            message_history: The running list of conversation messages.
            additional_message: An optional string message to prepend to the user's content.

        Returns:
            Updated message history with the new user message appended.
        """

        content: List[Dict[str, Any]] = []

        if additional_message:
            content.append({
                "type": "text",
                "text": additional_message
            })

        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_base_64}"}
        })

        user_message = {
            "role": "user",
            "content": content
        }

        message_history.append(user_message)

        return message_history
    
    
    
    async def call_ai(self, message_history : List) -> List[List[VoyagerAction], str]:
        response = await acompletion(
            model=settings.MODEL,
            messages=message_history,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        

        
        model_output = json_parser(response.choices[0].message.content)
        
        if model_output:
            validated_outputs = []
            for action in model_output["actions"]:
                validated_outputs.append(VoyagerAction.model_validate(action))
            return validated_outputs, response.choices[0].message.content
        else:
            raise AssertionError("Model output failed")
        

    # convenience context manager support (optional)
    async def __aenter__(self) -> "Voyager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # No browser to stop, context is managed externally
        pass
