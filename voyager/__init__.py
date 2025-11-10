from __future__ import annotations
import asyncio
import base64
import json
import random
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from urllib.parse import urlparse

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
        save_images_for_debugging: bool = False,
        save_message_history_for_debugging: bool = False,
        mimic_human_behaviour: bool = False,
        max_images_to_include: int = 1
    ) -> None:
        self.annotate_script = self._load_script("voyager/scripts/browser-annotate.js")
        self.clear_script = self._load_script("voyager/scripts/clear-rects.js")
        self.clear_element_tags_script = self._load_script("voyager/scripts/clear-elements.js")
        self.concurrency_semaphore = asyncio.Semaphore(max_concurrency)
        self.return_images = return_images
        self.save_images_for_debugging = save_images_for_debugging
        self.save_message_history_for_debugging = save_message_history_for_debugging
        self.mimic_human_behaviour = mimic_human_behaviour
        self.max_images_to_include = max_images_to_include
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

    @staticmethod
    def _get_sanitized_task_url_for_path(url: str) -> str:
        """Sanitize a URL to be used as a valid path segment."""
        parsed_url = urlparse(url)
        # Combine netloc (domain) and path, then replace invalid characters
        sanitized = (parsed_url.netloc + parsed_url.path).replace('/', '_').replace(':', '_').replace('.', '_').replace('-', '_')
        # Remove any leading/trailing underscores and ensure it's not empty
        return sanitized.strip('_') or "default_task"

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
                await task_page.evaluate("document.body.style.zoom='0.8'")

                sanitized_task_url = self._get_sanitized_task_url_for_path(task.start_url)

                screenshots_dir: Optional[Path] = None
                if self.save_images_for_debugging:
                    screenshots_dir = Path("screenshots") / sanitized_task_url
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Screenshots will be saved to: {screenshots_dir}")

                message_history_dir: Optional[Path] = None
                if self.save_message_history_for_debugging:
                    message_history_dir = Path("Messages") / sanitized_task_url
                    message_history_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Message history will be saved to: {message_history_dir}")

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

                    # Capture page state with retry logic for navigation handling
                    screenshot_base64 = await self._capture_annotated_screenshot(
                        task_page,
                        max_retries=3,
                        retry_delay=0.5
                    )

                    if self.save_images_for_debugging and screenshots_dir:
                        image_path = screenshots_dir / f"image_{iteration}.png"
                        with open(image_path, "wb") as f:
                            f.write(base64.b64decode(screenshot_base64))
                        logger.debug(f"Saved screenshot to {image_path}")
                    
                    # Update message history with latest state
                    message_history = self._clear_images_from_history(message_history)
                    execution_log = f"You are currently on the page : {task_page.url}\n" + execution_log  + "\n Please make sure to double check the element tag you are clicking on in the next image, cross check again and again and valdiate which element you are interacting with. Please do not mess up and select a wrong element index"
                    message_history = self._add_screenshot_message(
                        screenshot_base64,
                        message_history,
                        execution_log if execution_log else None
                    )

                    if self.save_message_history_for_debugging and message_history_dir:
                        message_path = message_history_dir / f"message_{iteration}.json"
                        with open(message_path, "w", encoding="utf-8") as f:
                            json.dump(message_history, f, indent=2)
                        logger.debug(f"Saved message history to {message_path}")

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
                    should_stop, task_completed, execution_log = await self._execute_actions(
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
                        logger.info(f"Final URL : {task_page.url}")
                        break

                    # Wait for page stability before next iteration
                    
                    await task_page.wait_for_load_state("load")
                    await asyncio.sleep(1)
                    await task_page.evaluate(self.clear_element_tags_script)

                if iteration >= task.max_iterations:
                    logger.warning(f"Task reached max iterations ({task.max_iterations})")

            except Exception as e:
                logger.error(f"Task execution failed: {e}", exc_info=True)
                raise
            finally:
                if task_page and not task_page.is_closed():
                    logger.info(f"Closing page for task: '{task.prompt}'")
                    await task_page.close()

    async def _capture_annotated_screenshot(
        self, 
        page: Page,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ) -> str:
        """
        Annotate page elements, capture screenshot, then clear annotations.
        Implements retry logic to handle navigation-induced execution context destruction.
        """
        for attempt in range(max_retries):
            try:
                # Wait for page to be stable (but not full networkidle)
                await page.wait_for_load_state("domcontentloaded")
                
                # Small delay to let any immediate navigations settle
                await asyncio.sleep(0.3)
                
                # Check if page is still valid before evaluating
                if page.is_closed():
                    raise RuntimeError("Page was closed during screenshot capture")
                
                # Execute operations in sequence with context checks
                await page.evaluate(self.annotate_script)
                page_bytes = await page.screenshot()
                await page.evaluate(self.clear_script)
                
                return base64.b64encode(page_bytes).decode()
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check if it's a navigation/context error
                if "execution context was destroyed" in error_msg or "navigation" in error_msg:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Navigation detected during screenshot (attempt {attempt + 1}/{max_retries}). "
                            f"Retrying in {retry_delay}s..."
                        )
                        await asyncio.sleep(retry_delay)
                        # Increase delay for next attempt
                        retry_delay *= 1.5
                        continue
                    else:
                        logger.error(
                            f"Failed to capture screenshot after {max_retries} attempts due to navigation"
                        )
                        raise RuntimeError(
                            "Page navigation interrupted screenshot capture. "
                            "Consider waiting longer after actions or adjusting retry settings."
                        ) from e
                else:
                    # Different error, don't retry
                    logger.error(f"Screenshot capture failed: {e}")
                    raise
        
        raise RuntimeError("Unexpected: exited retry loop without return or raise")

    async def _mimic_human_behavior(self, page: Page) -> None:
        """Simulate human-like interaction with random mouse movements and scrolling."""
        try:
            viewport_size = page.viewport_size
            if not viewport_size:
                logger.warning("Could not get viewport size to mimic human behavior.")
                return

            width, height = viewport_size['width'], viewport_size['height']

            # Random mouse movements
            # for _ in range(random.randint(3, 7)):
            #     random_x = random.randint(0, width - 1)
            #     random_y = random.randint(0, height - 1)
            #     await page.mouse.move(random_x, random_y, steps=random.randint(5, 10))
            #     await asyncio.sleep(random.uniform(0.05, 0.15))

            # Random scrolls
            for _ in range(random.randint(1, 3)):
                scroll_amount_y = random.randint(-200, 200)
                scroll_amount_x = random.randint(-50, 50)
                await page.mouse.wheel(delta_x=scroll_amount_x, delta_y=scroll_amount_y)
                await asyncio.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            logger.warning(f"Could not mimic human behavior: {e}")

    async def _execute_actions(
        self,
        actions: List[VoyagerAction],
        page: Page,
        execution_log: str
    ) -> tuple[bool, bool, str]:
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

            if self.mimic_human_behaviour:
                await self._mimic_human_behavior(page)

            action_resp = await safe_execute_action(action, page)

            if self.mimic_human_behaviour:
                await self._mimic_human_behavior(page)

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

        return should_stop, task_completed, execution_log

    def _clear_images_from_history(
        self,
        message_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Replace image_url entries with placeholder text to manage context size,
        keeping the last `max_images_to_include` images.
        
        Args:
            message_history: List of OpenAI-style messages
            
        Returns:
            Cleaned message history with old images replaced by placeholders.
        """
        # Find indices of messages containing images
        image_message_indices = []
        for i, message in enumerate(message_history):
            if "content" in message and isinstance(message["content"], list):
                if any(part.get("type") == "image_url" for part in message["content"]):
                    image_message_indices.append(i)

        # Determine which images to replace
        images_to_replace_indices = set(image_message_indices[:-self.max_images_to_include])

        if not images_to_replace_indices:
            return message_history

        # Create a new list with old images replaced
        cleaned_messages = []
        for i, message in enumerate(message_history):
            if i in images_to_replace_indices:
                new_content = [
                    {"type": "text", "text": "[Placeholder: image already processed]"}
                    if part.get("type") == "image_url"
                    else part
                    for part in message["content"]
                ]
                cleaned_messages.append({
                    "role": message["role"],
                    "content": new_content
                })
            else:
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
