from wrappers.open_ai import OpenAIWrapper
from scraper.webvoyager import prompts
from .javascripts import *
from db._utils import process_voyager_update
from config.logger import logger
from seleniumbase import Driver
from config.settings import settings
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import Chrome
from selenium.webdriver.common.action_chains import ActionChains
from models.call import Call
import traceback
import platform
import base64
import json
import time
import shutil
import os
import re


class VoyagerAgent:
    """
    An improved WebVoyager agent that navigates websites using GPT vision model guidance.
    Focuses on preventing action loops and maintaining proper context between iterations.
    """

    def __init__(self, login_url: str, call: Call):
        self.login_url = login_url
        self.open_ai = OpenAIWrapper()
        self.driver = None
        self.call = call
        self.actions_history = []  # Track action history to prevent loops
        self.final_links = None
        self.img_dir = None

        # Initialize components
        self._init_selenium_driver()
        self._init_img_uid()
        self._init_img_dir()

    def _init_selenium_driver(self):
        """Initialize the Selenium WebDriver with appropriate settings."""
        self.driver: Chrome = Driver(
            headless=settings.selenium_headless,
            browser=settings.selenium_browser_type,
            uc=settings.selenium_use_uc,
            chromium_arg=settings.selenium_chromium_arg,
        )
        self.driver.implicitly_wait(10)

    def _init_img_uid(self):
        """Create a unique identifier for the image directory based on the URL."""
        uid = re.sub(r"[^a-zA-Z0-9]", "", self.login_url)
        self.img_dir = f"Logs/{uid}"

    def _init_img_dir(self):
        """Create the directory for storing screenshots if it doesn't exist."""
        if not os.path.exists(self.img_dir):
            os.makedirs(self.img_dir)

    def get_web_element_rect(self):
        """
        Get the rectangular coordinates of all interactive web elements and their text content.
        
        Returns:
            tuple: (rects, web_elements, formatted_element_text)
        """
        rects, items_raw = self.driver.execute_script(JS_SCRIPTS)

        format_ele_text = []
        for web_ele_id in range(len(items_raw)):
            label_text, ele_tag_name, ele_type = None, None, None

            try:
                label_text = items_raw[web_ele_id]["text"]
                ele_tag_name = items_raw[web_ele_id]["element"].tag_name
                ele_type = items_raw[web_ele_id]["element"].get_attribute("type")
                ele_aria_label = items_raw[web_ele_id]["element"].get_attribute("aria-label")

            except Exception as e:
                logger.warning(f"Element with ID {web_ele_id} became stale. Attempting to re-locate.. retrying", self.call.model_dump())
                logger.debug(f"Error message: {e}", self.call.model_dump())

                ele_aria_label = self.driver.get_attribute(
                    f"//*[contains(text(), '{items_raw[web_ele_id]['text']}')]", "aria-label"
                )

            if not label_text:
                if ((ele_tag_name.lower() == "input" and ele_type in ["text", "search", "password", "email", "tel"])
                        or ele_tag_name.lower() == "textarea"
                        or (ele_tag_name.lower() == "button" and ele_type in ["submit", "button"])):
                    label = ele_aria_label if ele_aria_label else label_text
                    format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> '{label}';")

            elif len(label_text) < 200 and not ("<img" in label_text and "src=" in label_text):
                label = f"'{label_text}'"

                if ele_aria_label and ele_aria_label != label_text:
                    label += f", '{ele_aria_label}'"

                if ele_tag_name in ["button", "input", "textarea"]:
                    format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> {label};")
                else:
                    format_ele_text.append(f"[{web_ele_id}]: {label};")

        format_ele_text = "\t".join(format_ele_text)
        return rects, [web_ele["element"] for web_ele in items_raw], format_ele_text

    @staticmethod
    def encode_image(img_path: str):
        """Encode an image file to base64 string."""
        with open(img_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def json_parser(input_str: str):
        """Extract and parse JSON from a string."""
        pattern = r"\{.*\}"
        match = re.search(pattern, input_str, re.DOTALL)
        if match:
            json_string = match.group(0)
            try:
                json_out = json.loads(json_string)
                return json_out
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON: {json_string}")
                return None
        else:
            return None

    def create_message_for_model(self, iteration, screenshot_path, web_text, action_history=None, warning_obs=""):
        """
        Create a properly formatted message for the vision model.
        
        Args:
            iteration: Current iteration number
            screenshot_path: Path to the current screenshot
            web_text: Text representation of web elements
            action_history: History of previous actions
            warning_obs: Any warning observations to include
            
        Returns:
            dict: Properly formatted message for the vision model
        """
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        bs64_img = self.encode_image(screenshot_path)
        
        # Base prompt with task description and enhanced navigation/code guidance
        init_msg = (
            f"Given a task: {prompts.TASK_PROMPT}\n"
            f"Target URL: {self.login_url}\n"
            f"Today's date: {today_str}\n"
            "-----------------------------\n"
            "## Task Details & Navigation Strategy\n"
            "- Your goal is to always find and select the most correct and relevant link for the financial call or web event.\n"
            "- If the site is unclear, generic, or an IR (Investor Relations) portal, follow this robust approach:\n"
            "    1. Carefully scan all visible elements for keywords such as 'webcast', 'conference call', 'audio', 'video', 'livestream', 'listen', 'event', 'join', 'play', 'broadcast', 'earnings', 'presentation', 'register', 'access', 'media', 'replay', 'live', 'Q&A', 'IR', 'investor', 'meeting', 'webinar'.\n"
            "    2. Prioritize elements that are buttons, links, or have strong visual cues (e.g., bold, colored, large, or prominent placement).\n"
            "    3. If multiple candidates exist, prefer those with the closest date/time to today (" + today_str + "), or those that mention 'live' or 'upcoming'.\n"
            "    4. When choosing between multiple webcast/event links, prefer those with a date closest to today (" + today_str + ").\n"
            "    5. Avoid clicking on unrelated links (e.g., 'donate', 'contact', 'about', 'privacy', 'terms', 'careers', 'press', 'subscribe', 'newsletter', 'support').\n"
            "    6. If the page is ambiguous, look for navigation menus, tabs, or dropdowns that may reveal more relevant options.\n"
            "    7. Only scroll if you have thoroughly analyzed all visible content and cannot find a relevant link or element for the call.\n"
            "    8. Never perform random or repeated actions; always reason step-by-step and document your logic.\n"
            "    9. If you encounter a registration or login form, follow the registration-first logic as described in the task prompt.\n"
            "    10. If you see a warning, error, or unclear state, describe it in detail and try to resolve it as a human would.\n"
            "    11. If the site is highly generic, use all available cues (element text, tag, aria-label, context, visual prominence) to make the best possible decision.\n"
            "    12. If you reach a dead end or error, return a detailed answer with your reasoning.\n"
            "    13. Always keep track of your previous actions and avoid loops.\n"
            "-----------------------------\n"
            "## Pseudo-code for Navigation\n"
            "```\n"
            "for element in visible_elements:\n"
            "    if element.text or element.aria_label contains any KEYWORD:\n"
            "        if element is prominent and not unrelated:\n"
            "            select element as candidate\n"
            "if candidates:\n"
            "    pick the most relevant (by date, 'live', or context, especially closest to today: " + today_str + ")\n"
            "    click candidate\n"
            "else if no candidate and not scrolled:\n"
            "    scroll and repeat\n"
            "else:\n"
            "    return answer with detailed reasoning\n"
            "```\n"
            "-----------------------------\n"
        )

        # Add warning observation if any
        if warning_obs:
            init_msg += f"Observation: {warning_obs}\n"

        # Add action history context
        if action_history and len(action_history) > 0:
            history_context = (
                "Previous actions: " + " → ".join(action_history[-3:])
                if len(action_history) > 3
                else " → ".join(action_history)
            )
            init_msg += f"{history_context}\n"

        # Add standard observation prompt
        init_msg += "Please analyze the attached screenshot and give the necessary action.\n"

        # Add explanation about elements
        init_msg += (
            f"I've provided the tag name of each element and the text it contains (if text exists). "
            f"Note that <textarea> or <input> may be textbox, but not exactly. "
            f"Please focus more on the screenshot and then refer to the textual information.\n{web_text}"
        )

        return {
            "role": "user",
            "content": [
                {"type": "text", "text": init_msg},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{bs64_img}"}},
            ],
        }

    def is_action_loop(self, new_action):
        """
        Check if we're stuck in an action loop.
        
        Args:
            new_action: The new action to be performed
            
        Returns:
            bool: True if a loop is detected, False otherwise
        """
        # If we have less than 3 actions, we can't be in a loop yet
        if len(self.actions_history) < 3:
            return False
            
        # Simple loop detection: same action repeated 3 times in a row
        if len(self.actions_history) >= 2 and self.actions_history[-1] == self.actions_history[-2] == new_action:
            return True
            
        # Pattern loop detection (e.g., A → B → A → B)
        if len(self.actions_history) >= 4:
            if (self.actions_history[-2] == self.actions_history[-4] and 
                self.actions_history[-1] == self.actions_history[-3] and
                new_action == self.actions_history[-2]):
                return True
                
        return False

    def exec_action_click(self, web_ele):
        """Execute a click action on a web element."""
        action_str = f"click: {web_ele.tag_name}"
        if web_ele.get_attribute("type"):
            action_str += f" (type={web_ele.get_attribute('type')})"
        if web_ele.text:
            action_str += f" '{web_ele.text[:20]}'"
            
        self.actions_history.append(action_str)
        
        self.driver.execute_script("arguments[0].setAttribute('target', '_self')", web_ele)
        web_ele.click()
        time.sleep(5)

    def exec_action_type(self, info_content, web_ele):
        """
        Execute a type action on a web element.
        
        Returns:
            str: Observation about the typing action
        """
        observation = ""
        type_content = info_content
        ele_tag_name = web_ele.tag_name.lower()
        ele_type = web_ele.get_attribute("type")
        
        action_str = f"type '{type_content[:20]}...' into {ele_tag_name}"
        if ele_type:
            action_str += f" (type={ele_type})"
        self.actions_history.append(action_str)

        if (ele_tag_name != "input" and ele_tag_name != "textarea") or (
                ele_tag_name == "input" and ele_type not in ["text", "search", "password", "email", "tel"]
        ):
            observation = (f"Note: The web element you're trying to type may not be a textbox, and its tag name "
                        f"is <{web_ele.tag_name}>, type is {ele_type}.")
        try:
            web_ele.clear()

            if platform.system() == "Darwin":
                web_ele.send_keys(Keys.COMMAND + "a")
            else:
                web_ele.send_keys(Keys.CONTROL + "a")
            web_ele.send_keys(" ")
            web_ele.send_keys(Keys.BACKSPACE)

        except Exception as e:
            pass

        actions = ActionChains(self.driver)
        actions.click(web_ele).perform()
        actions.pause(1)

        try:
            self.driver.execute_script(
                """window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea' && e.target.type != 'search') {e.preventDefault();}};"""
            )
        except:
            pass

        actions.send_keys(type_content)
        actions.pause(2)
        actions.perform()
        time.sleep(2)

        return observation

    def exec_action_scroll(self, scroll_ele_number, scroll_content, web_elem):
        """Execute a scroll action on the page or a specific element."""
        fixed_scroll_amount = 500

        if scroll_ele_number == "WINDOW":
            action_str = f"scroll {scroll_content} (window)"
            if scroll_content == "down":
                self.driver.execute_script(f"window.scrollBy(0, {fixed_scroll_amount});")
            else:
                self.driver.execute_script(f"window.scrollBy(0, {-fixed_scroll_amount});")
        else:
            # Scroll an individual element
            scroll_ele_number = int(scroll_ele_number)
            web_ele = web_elem[scroll_ele_number]
            
            action_str = f"scroll {scroll_content} (element {scroll_ele_number})"
            
            # Focus on the element before scrolling
            self.driver.execute_script("arguments[0].focus();", web_ele)

            # Scroll the element using arrow keys
            if scroll_content == "down":
                web_ele.send_keys(Keys.ARROW_DOWN)
            else:
                web_ele.send_keys(Keys.ARROW_UP)
                
        self.actions_history.append(action_str)
        time.sleep(3)

    def check_investor_checkbox(self):
        """Check the investor checkbox if present (specific to certain sites)."""
        elements = self.driver.find_elements("#GuestRegistrationInvestorCheckboxLabel")
        if len(elements) > 0:
            checkbox = self.driver.find_element("#GuestRegistrationInvestorCheckboxInput")
            if not checkbox.get_attribute("checked"):
                elements[0].click()
                self.actions_history.append("click: investor checkbox")
                self.driver.sleep(1)
                return True
        return False

    def login(self):
        """
        Main method to navigate and interact with the website to find streaming media links.
        
        Returns:
            list or None: List of media links if found, None otherwise
        """
        # Initial setup
        self.driver.get(self.login_url)
        self.driver.save_screenshot(f"{self.img_dir}/initial_screenshot.png")

        try:
            self.driver.click("body")
        except Exception:
            pass

        self.driver.execute_script(
            """window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea') {e.preventDefault();}};"""
        )

        self.driver.save_screenshot(f"{self.img_dir}/initial_screenshot2.png")
        time.sleep(5)

        warning_observation = ""
        iteration = 0
        success = False
        success_message = ""
        rects = []
        messages = []  # Store messages for the model
        latest_model_message = None  # Track the latest model message

        # Add system prompt as the first message
        messages.append({
            "role": "system",
            "content": prompts.SYSTEM_PROMPT
        })

        while iteration < 20:
            iteration += 1
            
            # Check for investor checkbox - specific to certain sites
            self.check_investor_checkbox()
            
            try:
                rects, web_elem, web_elem_text = self.get_web_element_rect()
            except Exception as e:
                logger.warning("Driver encountered an warning when adding set-of-mark", self.call.model_dump())
                logger.warning(f"Exception: {str(e)}", self.call.model_dump())
                logger.warning(traceback.format_exc(), self.call.model_dump())
                break

            img_path = os.path.join(self.img_dir, f"screenshot{iteration}.png")
            self.driver.save_screenshot(img_path)

            # Create message with latest screenshot only, but with context from previous actions
            user_message = self.create_message_for_model(
                iteration=iteration,
                screenshot_path=img_path,
                web_text=web_elem_text,
                action_history=self.actions_history,
                warning_obs=warning_observation
            )
            
            # Reset messages to just system prompt + current message to save tokens and focus on latest image
            messages = [messages[0], user_message]
            
            # Call the vision model
            openai_response, gpt_call_error = self.open_ai.call(messages=messages)

            if gpt_call_error:
                logger.error(f"Error calling OpenAI: {gpt_call_error}", self.call.model_dump())
                break

            gpt_resp = openai_response.choices[0].message.content
            latest_model_message = gpt_resp  # Save the latest model message
            gpt_resp_json = self.json_parser(gpt_resp)
            
            # Handle invalid JSON response
            if not gpt_resp_json:
                warning_observation = "The previous response wasn't in valid JSON format. Please provide a valid JSON response."
                continue
                
            logger.info(f"Number of interactable elements: {len(rects)}", self.call.model_dump())
            logger.info(f"Action chosen by AI: {json.dumps(gpt_resp_json, indent=4)}", self.call.model_dump())

            # Clean up element markers
            for rect_ele in rects:
                try:
                    self.driver.execute_script("arguments[0].remove()", rect_ele)
                except Exception:
                    pass
            rects = []

            try:
                # Ensure we're on the right window
                window_handle_task = self.driver.current_window_handle
                self.driver.switch_to.window(window_handle_task)
                
                action_key = gpt_resp_json["type"].lower()
                
                # Check for action loop before proceeding
                if self.is_action_loop(action_key):
                    warning_observation = (
                        "Action loop detected! You seem to be repeating the same actions. "
                        "Try a different approach or look for alternative elements to interact with."
                    )
                    continue

                # Handle different action types
                if action_key == "click":
                    action_list = gpt_resp_json["actions"]
                    for action in action_list:
                        click_ele_number = action["element_number"]
                        web_ele = web_elem[click_ele_number]
                        self.exec_action_click(web_ele=web_ele)

                elif action_key == "wait":
                    self.actions_history.append("wait")
                    time.sleep(5)

                elif action_key == "type":
                    action_list = gpt_resp_json["actions"]
                    for action in action_list:
                        type_elem_number = action["element_number"]
                        content = action["content"]
                        web_ele = web_elem[type_elem_number]
                        observation = self.exec_action_type(info_content=content, web_ele=web_ele)
                        if observation:
                            warning_observation = observation
                    
                    # Often we want to submit after typing
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ENTER)
                    actions.perform()

                elif action_key == "scroll":
                    action_list = gpt_resp_json["actions"]
                    for action in action_list:
                        self.exec_action_scroll(
                            scroll_ele_number=action["element_number"],
                            scroll_content=action["content"],
                            web_elem=web_elem
                        )

                elif action_key == "go-back":
                    self.actions_history.append("go-back")
                    self.driver.back()

                elif action_key == "google":
                    self.actions_history.append("google")
                    self.driver.get("https://www.google.com/")
                    time.sleep(5)

                elif action_key == "answer":
                    action_list = gpt_resp_json["actions"]
                    for action in action_list:
                        logger.info(f"FINISHED: {action['content']}", self.call.model_dump())
                        logger.info("AGENT TASK COMPLETE", self.call.model_dump())
                        success_message = action["content"]
                        logger.info(f"Success message: {success_message}", self.call.model_dump())
                    success = True
                    process_voyager_update(call=self.call, call_data_id=self.call.id, voyager_log=success_message)
                    break

                else:
                    warning_observation = f"Unknown action type: {action_key}. Please use one of the allowed action types."
                    continue

                # Reset warning observation after successful action
                warning_observation = ""

            except Exception as e:
                logger.warning(f"Exception during action execution: {str(e)}", self.call.model_dump())
                logger.warning(traceback.format_exc(), self.call.model_dump())

                if "element click intercepted" not in str(e):
                    warning_observation = (
                        "The action you have chosen cannot be executed. "
                        "Please double-check if you have selected the wrong Numerical Label or "
                        "Action or Action format. Then provide the revised Thought and Action."
                    )
                time.sleep(5)

        # Handle success or failure
        if success:
            self.wait_for_media_element()
            try:
                return self.get_network_urls()
            except Exception as e:
                logger.error(f"Error getting network URLs: {str(e)}", self.call.model_dump())
        else:
            logger.error(f"WebVoyager Agent failed login for url {self.login_url}!", self.call.model_dump())
            # If we have a latest model message, save it as a log (like the success case)
            if latest_model_message:
                logger.info(f"Saving latest model message after reaching iteration/message limit: {latest_model_message}", self.call.model_dump())
                process_voyager_update(call=self.call, call_data_id=self.call.id, voyager_log=latest_model_message)
            
        # Cleanup and quit
        try:
            self.cleanup_images()
        except Exception as e:
            logger.error(f"Error cleaning up images: {str(e)}", self.call.model_dump())
            
        self.driver.quit()
        return None

    def cleanup_images(self):
        """Remove all screenshots to save disk space."""
        if os.path.exists(self.img_dir) and os.path.isdir(self.img_dir):
            shutil.rmtree(self.img_dir)
            logger.info(f"Deleted all images in {self.img_dir}", self.call.model_dump())

    def extract_urls(self):
        """Extract network request URLs from browser performance data."""
        try:
            # Execute JavaScript to capture network requests
            requests = self.driver.execute_script("""
            var performance = window.performance || window.webkitPerformance || window.msPerformance || window.mozPerformance;
            if (!performance) {
                return [];
            }
            var entries = performance.getEntriesByType("resource");
            var urls = [];
            for (var i = 0; i < entries.length; i++) {
                urls.push(entries[i].name);
            }
            return urls;
            """)

            return requests
        except Exception as e:
            logger.error(f"Error extracting URLs: {e}", self.call.model_dump())
            return []

    def get_network_urls(self):
        """
        Extract network URLs from browser logs and prioritize media files.
        
        Returns:
            list: A list of extracted URLs with media links prioritized.
        """
        # Use cached results if available
        if self.final_links:
            logger.info(f"Using cached URLs for {self.login_url}: {self.final_links}", self.call.model_dump())
            self.driver.quit()
            return self.final_links

        # Extract network requests
        network_requests = self.extract_urls()
        self.driver.quit()

        # Filter for media file extensions
        allowed_extensions = [r"\.m3u8", r"\.mp3", r"\.mp4", r"\.mpd"]

        # Prioritize m3u8 links (streaming manifests)
        m3u8_links = [req for req in network_requests if re.search(r"\.m3u8", req)]

        # Then get other media links
        other_links = [
            req for req in network_requests
            if any(re.search(ext, req) for ext in allowed_extensions if ext != r"\.m3u8")
        ]

        live_links = m3u8_links + other_links

        if live_links:
            logger.info(f"Final URLs for {self.login_url}: {live_links}", self.call.model_dump())
            logger.info(f"Successful scrape for URL: {self.login_url}", self.call.model_dump())
            return live_links
        else:
            logger.warning(f"No media URLs found for the URL: {self.login_url}", self.call.model_dump())
            raise Exception("No URL found")

    def wait_for_media_element(self, timeout=60):
        """
        Listen to network requests for media links.
        
        Args:
            timeout (int): Maximum time to wait in seconds.
            
        Returns:
            list or None: The media links found, or None.
        """
        logger.info(
            f"Listening for media links for URL: {self.login_url} within {timeout} seconds.",
            self.call.model_dump()
        )

        # Extensions prioritized by order
        prioritized_extensions = ['.m3u8', '.mp3', '.mp4', '.mpd']
        start_time = time.time()

        while time.time() - start_time < timeout:
            network_requests = self.extract_urls()

            for ext in prioritized_extensions:
                filtered_links = [url for url in network_requests if ext in url]
                if filtered_links:
                    logger.info(f"Found {ext} link(s): {filtered_links}", self.call.model_dump())
                    self.final_links = filtered_links
                    return filtered_links

            time.sleep(1)

        logger.warning(
            f"No media links found within {timeout} seconds for URL: {self.login_url}",
            self.call.model_dump()
        )
        return None