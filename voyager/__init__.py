from __future__ import annotations
import asyncio
import base64
from typing import Optional, List, Dict, Any

from litellm import acompletion
from playwright.async_api import BrowserContext, Page

from config.logger import logger
from config.settings import settings
from utils import json_parser
from .prompts.system_prompt import SYSTEM_PROMPT
from .types import VoyagerTask, VoyagerStep, VoyagerAction
from .actions import safe_execute_action


class Voyager:
    """
    High-level wrapper around Playwright for AI-driven browser automation tasks.
    Manages iterative task execution with screenshot analysis and action execution.
    """

    def __init__(
        self,
        max_concurrency: int = 10,
        return_images: bool = True,
    ) -> None:
        self.annotate_script = self._load_script("voyager/scripts/browser-annotate.js")
        self.clear_script = self._load_script("voyager/scripts/clear-rects.js")
        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images
        self.system_prompt = SYSTEM_PROMPT

    @staticmethod
    def _load_script(path: str) -> str:
        """Load JavaScript file with proper error handling."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Script file not found: {path}")
            raise
        except Exception as e:
            logger.error(f"Error loading script {path}: {e}")
            raise

    async def start_task(
        self,
        browser_context: BrowserContext,
        task: VoyagerTask
    ) -> None:
        """
        Execute a browser automation task with AI-driven decision making.
        
        Args:
            browser_context: Playwright browser context for the task
            task: VoyagerTask containing prompt, URL, and configuration
        """
        async with self.concurrency_semaphore:
            task_page = None
            try:
                logger.info(f"Starting task: '{task.prompt}' at {task.start_url}")
                task_page = await browser_context.new_page()

                message_history = [
                    {"role": "developer", "content": self.system_prompt},
                    {"role": "user", "content": f"Task Assigned by the user: {task.prompt}"}
                ]

                await task_page.goto(task.start_url, wait_until="domcontentloaded")
                
                execution_log = ""
                iteration = 0
                task_completed = False

                while iteration < task.max_iterations:
                    iteration += 1
                    logger.info(f"Iteration {iteration}/{task.max_iterations}")

                    # Capture page state
                    screenshot_base64 = await self._capture_annotated_screenshot(task_page)
                    
                    # Update message history with latest state
                    message_history = self._clear_images_from_history(message_history)
                    message_history = self._add_screenshot_message(
                        screenshot_base64,
                        message_history,
                        execution_log if execution_log else None
                    )

                    # Get AI decision
                    logger.info("Requesting AI decision...")
                    try:
                        actions, raw_response = await self._call_ai(message_history)
                        logger.info(f"AI returned {len(actions)} action(s)")
                    except Exception as e:
                        logger.error(f"AI call failed: {e}")
                        break

                    message_history.append({"role": "assistant", "content": raw_response})

                    # Execute actions
                    execution_log = "Logs from the last step:\n"
                    should_stop, task_completed = await self._execute_actions(
                        actions, task_page, execution_log
                    )

                    # Invoke callback if provided
                    if task.callback:
                        await task.callback(VoyagerStep(
                            image_base_64=screenshot_base64,
                            actions=actions
                        ))

                    if should_stop or task_completed:
                        logger.info(f"Task {'completed' if task_completed else 'stopped'}")
                        break

                    # Wait for page stability before next iteration
                    await task_page.wait_for_load_state("load")
                    await asyncio.sleep(1)

                if iteration >= task.max_iterations:
                    logger.warning(f"Task reached max iterations ({task.max_iterations})")

            except Exception as e:
                logger.error(f"Task execution failed: {e}", exc_info=True)
                raise
            finally:
                if task_page and not task_page.is_closed():
                    logger.info(f"Closing page for task: '{task.prompt}'")
                    await task_page.close()

    async def _capture_annotated_screenshot(self, page: Page) -> str:
        """Annotate page elements, capture screenshot, then clear annotations."""
        try:
            await page.evaluate(self.annotate_script)
            page_bytes = await page.screenshot()
            await page.evaluate(self.clear_script)
            return base64.b64encode(page_bytes).decode()
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            raise

    async def _execute_actions(
        self,
        actions: List[VoyagerAction],
        page: Page,
        execution_log: str
    ) -> tuple[bool, bool]:
        """
        Execute a list of actions and return (should_stop, task_completed).
        
        Returns:
            tuple: (should_stop, task_completed) - booleans indicating task state
        """
        should_stop = False
        task_completed = False

        for i, action in enumerate(actions, 1):
            logger.info(f"Executing action {i}/{len(actions)}: {action.type}")
            logger.debug(action.model_dump())

            action_resp = await safe_execute_action(action, page)

            # Wait for stability after action
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(0.5)

            if action_resp.success:
                logger.info(f"Action {action.type} succeeded: {action_resp.success.content}")
                execution_log += f"\n✓ Task completed successfully: {action_resp.success.content}"
                task_completed = True
                break

            if action_resp.stop:
                logger.info(f"Action {action.type} stopped: {action_resp.stop.reason}")
                execution_log += f"\n⊗ Task stopped: {action_resp.stop.reason}"
                should_stop = True
                break

            if action_resp.error:
                logger.error(
                    f"Error executing action {action.type}: {action_resp.message_formatted_string}. "
                    f"Details: {action_resp.error}"
                )
                execution_log += (
                    f"\n✗ Error executing action: {action_resp.message_formatted_string}\n"
                    f"  Error details: {action_resp.error}"
                )
                continue

            # Log successful action execution
            logger.info(action_resp.message_formatted_string)
            execution_log += f"\n{action_resp.message_formatted_string}"

        return should_stop, task_completed

    @staticmethod
    def _clear_images_from_history(
        message_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Replace image_url entries with placeholder text to manage context size.
        
        Args:
            message_history: List of OpenAI-style messages
            
        Returns:
            Cleaned message history with images replaced by placeholders
        """
        cleaned_messages = []

        for message in message_history:
            if "content" not in message:
                continue

            content = message["content"]

            if isinstance(content, list):
                new_content = [
                    {"type": "text", "text": "[Placeholder: image already processed]"}
                    if isinstance(part, dict) and part.get("type") == "image_url"
                    else part
                    for part in content
                ]
                cleaned_messages.append({
                    "role": message["role"],
                    "content": new_content
                })
            elif isinstance(content, str):
                cleaned_messages.append(message)

        return cleaned_messages

    @staticmethod
    def _add_screenshot_message(
        screenshot_base64: str,
        message_history: List[Dict[str, Any]],
        additional_message: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Append a new user message with screenshot and optional text.
        
        Args:
            screenshot_base64: Base64-encoded screenshot
            message_history: Existing message history
            additional_message: Optional text to include before the image
            
        Returns:
            Updated message history
        """
        content: List[Dict[str, Any]] = []

        if additional_message:
            content.append({"type": "text", "text": additional_message})

        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
        })

        message_history.append({"role": "user", "content": content})
        return message_history

    async def _call_ai(
        self,
        message_history: List[Dict[str, Any]]
    ) -> tuple[List[VoyagerAction], str]:
        """
        Call AI model to get next actions.
        
        Returns:
            tuple: (List of validated VoyagerActions, raw response string)
        """
        response = await acompletion(
            model=settings.MODEL,
            messages=message_history,
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        raw_response = response.choices[0].message.content
        model_output = json_parser(raw_response)

        if not model_output or "actions" not in model_output:
            raise ValueError("AI response missing 'actions' field")

        validated_actions = [
            VoyagerAction.model_validate(action)
            for action in model_output["actions"]
        ]

        return validated_actions, raw_response

    async def get_page_web_element_rect(self, page: Page) -> Any:
        """Get annotated element rectangles from the page."""
        return await page.evaluate(self.annotate_script)

    async def clear_rects(self, page: Page) -> None:
        """Clear annotation rectangles from the page."""
        await page.evaluate(self.clear_script)

    async def __aenter__(self) -> "Voyager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass