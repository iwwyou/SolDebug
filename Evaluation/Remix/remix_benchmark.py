"""
Remix IDE Automated Benchmark Script
Measures debugging latency with state slot setup consideration
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import pandas as pd
from pathlib import Path
import sys
import io

# Fix Windows encoding issue
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class RemixBenchmark:
    def __init__(self, headless=False):
        """Initialize Remix IDE in browser"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get("https://remix.ethereum.org")

        # Wait for Remix to load
        WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#fileExplorerView"))
        )
        time.sleep(3)  # Additional wait for full initialization

        # Handle AI and Analytics preference popup if it appears
        self._handle_popups()

        # Wait for Remix FileSystem API to be available (new Remix 1.0.0+)
        print("  [INIT] Waiting for Remix FileSystem API...")
        try:
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script("return typeof window.remixFileSystem !== 'undefined' && window.remixFileSystem !== null")
            )
            time.sleep(2)  # Additional wait for API to stabilize
            print("  [OK] Remix FileSystem API ready")
        except TimeoutException:
            print("  [WARNING] Remix FileSystem API not detected")

        print("Remix IDE loaded successfully")

    def _handle_popups(self):
        """Handle various Remix IDE popups (Analytics, Cookie consent, etc.)"""
        # Try multiple strategies to handle popups
        popup_xpaths = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'OK')]",
            "//button[contains(text(), 'Reject')]",
            "//button[@data-id='matomoModalDialogModalDialogModalFooter-react']//button",
            "//div[@class='modal-footer']//button",
        ]

        for xpath in popup_xpaths:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                button.click()
                time.sleep(1)
                print(f"  [OK] Popup handled: {xpath}")
                break
            except TimeoutException:
                continue

        # Additional check: close any modal dialogs using JavaScript
        try:
            self.driver.execute_script("""
                // Close any visible modal dialogs
                document.querySelectorAll('.modal.show').forEach(modal => {
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) backdrop.remove();
                    modal.style.display = 'none';
                    modal.classList.remove('show');
                });
            """)
        except:
            pass

    def reset(self):
        """Reset workspace for next test"""
        # Delete current file
        try:
            self.driver.execute_script("""
                // Clear workspace
                window.location.reload();
            """)
            time.sleep(3)

            # Handle popups after reload
            self._handle_popups()

            # Wait for Remix FileSystem API to be available after reload
            try:
                WebDriverWait(self.driver, 30).until(
                    lambda d: d.execute_script("return typeof window.remixFileSystem !== 'undefined' && window.remixFileSystem !== null")
                )
                time.sleep(2)
            except TimeoutException:
                pass
        except:
            pass

    def close(self):
        """Close browser"""
        self.driver.quit()

    def _create_contract_file(self, filename, contract_code):
        """Create contract file in Remix workspace using new FileSystem API"""
        try:
            # Verify Remix FileSystem API is available
            api_available = self.driver.execute_script("""
                return typeof window.remixFileSystem !== 'undefined' && window.remixFileSystem !== null;
            """)

            if not api_available:
                raise Exception("Remix FileSystem API not available. window.remixFileSystem is undefined")

            # Escape the contract code for JavaScript
            escaped_code = contract_code.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

            # Create the file using new Remix FileSystem API (Remix 1.0.0 uses workspace structure)
            print(f"  [INFO] Creating file: {filename}")
            result = self.driver.execute_async_script(f"""
                const callback = arguments[arguments.length - 1];
                (async () => {{
                    try {{
                        if (!window.remixFileSystem) {{
                            callback('error: window.remixFileSystem is not defined');
                            return;
                        }}
                        const content = `{escaped_code}`;
                        // Remix 1.0.0 uses /.workspaces/default_workspace/ structure
                        const filepath = '/.workspaces/default_workspace/contracts/{filename}';

                        // Use remixFileSystem to write file
                        await window.remixFileSystem.writeFile(filepath, content);

                        // Wait for file to be created
                        await new Promise(resolve => setTimeout(resolve, 1000));

                        callback('success');
                    }} catch (error) {{
                        callback('error: ' + error.message);
                    }}
                }})();
            """)

            if result and result.startswith('error'):
                raise Exception(result)

            time.sleep(2)

            # First, expand the contracts folder if it's collapsed
            print(f"  [INFO] Expanding contracts folder...")
            try:
                # Click on contracts folder to expand it
                contracts_folder = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-id='treeViewLitreeViewItemcontracts']"))
                )
                contracts_folder.click()
                time.sleep(1)
                print(f"  [OK] Contracts folder expanded")
            except Exception as e:
                print(f"  [WARNING] Could not expand contracts folder: {e}")
                # Try JavaScript method
                try:
                    self.driver.execute_script("""
                        const folder = document.querySelector('[data-id="treeViewLitreeViewItemcontracts"]');
                        if (folder) folder.click();
                    """)
                    time.sleep(1)
                except:
                    pass

            # Click on the file in the file explorer to select it
            print(f"  [INFO] Selecting file in explorer...")
            try:
                # Use the correct selector that works in Remix 1.0.0
                # data-id format: treeViewDivDraggableItemcontracts/{filename}
                file_element = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"[data-id='treeViewDivDraggableItemcontracts/{filename}']"))
                )
                file_element.click()
                time.sleep(2)
                print(f"  [OK] File selected in explorer")
            except Exception as e:
                print(f"  [WARNING] Could not click file in explorer: {e}")
                # Try alternative method using JavaScript
                try:
                    self.driver.execute_script(f"""
                        const fileElement = document.querySelector('[data-id="treeViewDivDraggableItemcontracts/{filename}"]');
                        if (fileElement) {{
                            fileElement.click();
                        }}
                    """)
                    time.sleep(2)
                    print(f"  [OK] File selected via JavaScript")
                except Exception as e2:
                    print(f"  [ERROR] Could not select file: {e2}")

            # Wait for the editor to be ready
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return window.monaco !== undefined")
            )

            time.sleep(1)

            print(f"  [OK] Created contract file: {filename}")
        except Exception as e:
            print(f"  [ERROR] Error creating file: {e}")
            raise

    def _compile_contract(self):
        """Compile the contract"""
        try:
            # Handle any lingering popups before clicking
            self._handle_popups()

            # Click Solidity Compiler tab using JavaScript
            print("  [INFO] Opening Solidity Compiler tab...")
            self.driver.execute_script("""
                const compilerTab = document.querySelector("[plugin='solidity']");
                if (compilerTab) {
                    compilerTab.click();
                }
            """)
            time.sleep(3)
            print("  [OK] Compiler tab opened")

            # Wait for compile button to be enabled (not disabled)
            WebDriverWait(self.driver, 15).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "[data-id='compilerContainerCompileBtn']").is_enabled()
            )
            time.sleep(1)

            # Click compile button using JavaScript to avoid interception
            print("  [INFO] Clicking compile button...")
            self.driver.execute_script("""
                document.querySelector("[data-id='compilerContainerCompileBtn']").click();
            """)

            # Wait for compilation to complete (check for compilation finished indicator)
            # The data-id includes the compiler version, so we use a prefix match
            WebDriverWait(self.driver, 30).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "[data-id^='compilationFinishedWith']")
            )
            time.sleep(1)
            print("  [OK] Compilation successful")
        except Exception as e:
            print(f"  [ERROR] Compilation failed: {e}")
            raise

    def _deploy_contract(self):
        """Deploy contract to JavaScript VM"""
        try:
            # Handle any lingering popups before clicking
            self._handle_popups()

            # Click Deploy & Run Transactions tab using JavaScript (Selenium click is intercepted)
            print("  [INFO] Opening Deploy & Run Transactions tab...")
            self.driver.execute_script("""
                const deployTab = document.querySelector("[plugin='udapp']");
                if (deployTab) {
                    deployTab.click();
                }
            """)
            time.sleep(2)
            print("  [OK] Deploy tab opened")

            # Ensure JavaScript VM is selected (default)
            env_select = self.driver.find_element(By.CSS_SELECTOR, "[data-id='settingsSelectEnvOptions']")
            if "Remix VM" not in env_select.text:
                env_select.click()
                vm_option = self.driver.find_element(By.XPATH, "//option[contains(text(), 'Remix VM')]")
                vm_option.click()

            # Click Deploy button (data-id includes function type, so use prefix match)
            deploy_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-id^='Deploy']")
            deploy_btn.click()

            # Wait for deployment - check for deployed contract instance
            print("  [INFO] Waiting for contract deployment...")
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-shared='universalDappUiInstance']"))
            )

            # Additional wait for contract to fully initialize
            time.sleep(2)

            print("  [INFO] Verifying deployed contracts...")
            deployed_contracts = self.driver.find_elements(By.CSS_SELECTOR, "[data-shared='universalDappUiInstance']")
            if len(deployed_contracts) == 0:
                raise Exception("No deployed contract found")

            # Expand the deployed contract instance to show functions
            print("  [INFO] Expanding deployed contract...")
            try:
                # Use JavaScript to find and click the expander if contract is collapsed
                expanded = self.driver.execute_script("""
                    // Find the deployed contract instance
                    const instance = document.querySelector('[data-shared="universalDappUiInstance"]');
                    if (!instance) {
                        return 'error: no instance found';
                    }

                    // Check if it's collapsed (has udapp_hidesub class)
                    const isCollapsed = instance.classList.contains('udapp_hidesub');

                    if (isCollapsed) {
                        // Find the expander button and click it
                        const expander = instance.querySelector('[data-id^="universalDappUiTitleExpander"]');
                        if (expander) {
                            expander.click();
                            return 'expanded';
                        } else {
                            return 'error: no expander found';
                        }
                    } else {
                        return 'already_expanded';
                    }
                """)

                if expanded == 'expanded':
                    print("  [OK] Contract expanded successfully")
                    time.sleep(1)
                elif expanded == 'already_expanded':
                    print("  [INFO] Contract already expanded")
                else:
                    print(f"  [WARNING] Expansion result: {expanded}")

            except Exception as e:
                print(f"  [WARNING] Could not expand contract: {e}")
                # Try alternative method using Selenium
                try:
                    expander = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "[data-id^='universalDappUiTitleExpander']"
                    )
                    expander.click()
                    time.sleep(1)
                    print("  [OK] Contract expanded via fallback method")
                except:
                    pass

            print("  [OK] Contract deployed")
            return True
        except Exception as e:
            print(f"  [ERROR] Deployment failed: {e}")
            raise

    def _set_state_slots(self, state_slots_data):
        """
        Set state variables before function execution using setter functions
        state_slots_data: dict of {variable_name: value}
        """
        if not state_slots_data or len(state_slots_data) == 0:
            return

        try:
            print(f"  [SETUP] Setting {len(state_slots_data)} state slots...")

            for var_name, value in state_slots_data.items():
                # Setter function pattern: set_{var_name}
                setter_function = f"set_{var_name}"
                print(f"    Setting {var_name} = {value} via {setter_function}")

                try:
                    # Find the wrapper for this setter function
                    wrapper_selector = f"[data-id='{setter_function} - transact (not payable)-wrapper']"
                    wrapper = self.driver.find_element(By.CSS_SELECTOR, wrapper_selector)

                    # Find the parent container (udapp_contractActionsContainerSingle) that contains both wrapper and input
                    parent_container = wrapper.find_element(By.XPATH, "..")

                    # Find input field as sibling within the parent container
                    input_field = parent_container.find_element(
                        By.CSS_SELECTOR,
                        "input[data-id='multiParamManagerBasicInputField']"
                    )

                    # Input value
                    input_field.clear()
                    input_field.send_keys(str(value))
                    time.sleep(0.3)  # Wait for input to register

                    # Wait for button to be enabled
                    button_selector = f"[data-id='{setter_function} - transact (not payable)']"
                    WebDriverWait(self.driver, 5).until(
                        lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
                    )

                    # Click setter button
                    setter_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                    setter_btn.click()
                    time.sleep(0.5)  # Wait for transaction

                    print(f"      [OK] {var_name} set successfully")

                except NoSuchElementException:
                    print(f"      [SKIP] Could not find setter for {var_name}")
                    continue
                except Exception as e:
                    print(f"      [ERROR] Error setting {var_name}: {e}")
                    continue

            print(f"  [OK] State slots configured")
        except Exception as e:
            print(f"  [WARNING] State slot setup partial failure: {e}")

    def _set_state_arrays(self, state_arrays_data):
        """
        Set array state variables using _add*At functions
        state_arrays_data: dict of {array_name: [values]}
        """
        if not state_arrays_data or len(state_arrays_data) == 0:
            return

        try:
            print(f"  [SETUP] Setting {len(state_arrays_data)} state arrays...")

            for array_name, values in state_arrays_data.items():
                if not isinstance(values, list):
                    print(f"    Warning: {array_name} is not a list, skipping")
                    continue

                # Generate function name: _add{ArrayName}At
                # Handle underscore prefix: _tokens -> _addTokensAt
                if array_name.startswith('_'):
                    func_name = f"_add{array_name[1].upper() + array_name[2:]}At"
                else:
                    func_name = f"_add{array_name[0].upper() + array_name[1:]}At"

                print(f"    Setting array {array_name} ({len(values)} elements) via {func_name}")

                for index, value in enumerate(values):
                    try:
                        # Find the wrapper for this function
                        wrapper_selector = f"[data-id='{func_name} - transact (not payable)-wrapper']"
                        wrapper = self.driver.find_element(By.CSS_SELECTOR, wrapper_selector)

                        # Find the parent container (udapp_contractActionsContainerSingle) that contains both wrapper and input
                        parent_container = wrapper.find_element(By.XPATH, "..")

                        # Find input field as sibling within the parent container
                        input_field = parent_container.find_element(
                            By.CSS_SELECTOR,
                            "input[data-id='multiParamManagerBasicInputField']"
                        )

                        # Input: value, index
                        input_str = f"{value},{index}"
                        input_field.clear()
                        input_field.send_keys(input_str)
                        time.sleep(0.3)  # Wait for input to register

                        # Wait for button to be enabled
                        button_selector = f"[data-id='{func_name} - transact (not payable)']"
                        WebDriverWait(self.driver, 5).until(
                            lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
                        )

                        # Click function button
                        func_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                        func_btn.click()
                        time.sleep(0.5)  # Wait for transaction

                        print(f"      [OK] {array_name}[{index}] = {value}")

                    except NoSuchElementException:
                        print(f"      [SKIP] Could not find function {func_name}")
                        break
                    except Exception as e:
                        print(f"      [ERROR] Error setting {array_name}[{index}]: {e}")
                        continue

            print(f"  [OK] State arrays configured")
        except Exception as e:
            print(f"  [WARNING] State array setup partial failure: {e}")

    def _execute_function(self, function_name, inputs):
        """Execute target function and return transaction hash"""
        try:
            # Find the wrapper for this specific function
            wrapper_selector = f"[data-id='{function_name} - transact (not payable)-wrapper']"
            print(f"  [INFO] Looking for function wrapper: {wrapper_selector}")

            wrapper = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wrapper_selector))
            )

            # If function has inputs, fill them
            if inputs:
                # Find the parent container (udapp_contractActionsContainerSingle) that contains both wrapper and input
                parent_container = wrapper.find_element(By.XPATH, "..")

                # Find input field as sibling within the parent container
                function_input = parent_container.find_element(
                    By.CSS_SELECTOR,
                    "input[data-id='multiParamManagerBasicInputField']"
                )

                # Convert inputs to comma-separated string
                input_str = ','.join([str(v) for v in inputs]) if isinstance(inputs, list) else str(inputs)
                print(f"  [INFO] Entering parameters: {input_str}")

                function_input.clear()
                function_input.send_keys(input_str)
                time.sleep(0.3)  # Wait for input to register

            # Wait for button to be enabled (it gets enabled after input)
            button_selector = f"[data-id='{function_name} - transact (not payable)']"
            print(f"  [INFO] Waiting for button to be enabled...")

            WebDriverWait(self.driver, 10).until(
                lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
            )

            # Click function button to execute
            function_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
            function_btn.click()

            # Wait for transaction to complete
            time.sleep(0.5)

            print(f"  [OK] Function '{function_name}' executed")
            return True
        except Exception as e:
            print(f"  [ERROR] Function execution failed: {e}")
            raise

    def _open_debugger(self, expected_button_index=None):
        """
        Open debugger for the target function transaction

        Args:
            expected_button_index: The index where we expect the target function's debug button
                                   (i.e., the number of debug buttons before executing target function)
        """
        try:
            # Inject performance measurement
            self.driver.execute_script("""
                window.debugStartTime = performance.now();
            """)

            # Wait a moment for the debug button to appear
            time.sleep(0.5)

            # Find all debug buttons
            # Use data-shared instead of data-id because data-id includes transaction hash
            debug_btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-shared='txLoggerDebugButton']"
            )

            if len(debug_btns) == 0:
                raise Exception("No debug button found")

            print(f"  [INFO] Found {len(debug_btns)} debug button(s) total")

            # Click the target function's debug button
            # If expected_button_index is provided, use that specific button
            # Otherwise, fall back to the last button
            if expected_button_index is not None and len(debug_btns) > expected_button_index:
                target_button_index = expected_button_index
                print(f"  [INFO] Clicking debug button at index {target_button_index} (target function)")
            else:
                target_button_index = -1
                print(f"  [INFO] Clicking last debug button (fallback)")

            debug_btns[target_button_index].click()

            # Wait for debugger to load (slider appears)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-id='slider']"))
            )

            # Measure time using performance API
            debug_open_time = self.driver.execute_script("""
                return performance.now() - window.debugStartTime;
            """)

            print(f"  [OK] Debugger opened in {debug_open_time:.2f}ms")
            return debug_open_time
        except Exception as e:
            print(f"  [ERROR] Failed to open debugger: {e}")
            raise

    def _get_total_steps(self):
        """Get total number of steps (ByteOp count) from debugger slider"""
        try:
            slider = self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']")
            max_steps = int(slider.get_attribute("max"))
            print(f"  [OK] Total steps (ByteOp): {max_steps}")
            return max_steps
        except Exception as e:
            print(f"  [ERROR] Failed to get total steps: {e}")
            return None

    def _jump_to_end(self):
        """Jump to the last step of execution"""
        try:
            # Inject performance measurement
            self.driver.execute_script("""
                window.jumpStartTime = performance.now();
            """)

            # Click "Jump to the last breakpoint" button
            jump_end_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-id='debuggerTransactionEndButton']"
            )
            jump_end_btn.click()

            # Wait for UI to update
            time.sleep(1)

            # Measure time
            jump_time = self.driver.execute_script("""
                return performance.now() - window.jumpStartTime;
            """)

            print(f"  [OK] Jumped to end in {jump_time:.2f}ms")
            return jump_time
        except Exception as e:
            print(f"  [ERROR] Failed to jump to end: {e}")
            raise

    def _extract_variables(self):
        """Extract all variable values from Solidity State panel"""
        try:
            # Wait for state panel to populate
            time.sleep(1)

            # Inject performance measurement
            self.driver.execute_script("""
                window.extractStartTime = performance.now();
            """)

            # Find Solidity State/Solidity Locals panels
            variables = {}

            # Try to find state variables
            try:
                state_items = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-id='soliditystate'] .sol-item"
                )

                for item in state_items:
                    try:
                        key = item.find_element(By.CSS_SELECTOR, ".key").text
                        value = item.find_element(By.CSS_SELECTOR, ".value").text
                        variables[key] = value
                    except:
                        continue
            except:
                pass

            # Try to find local variables
            try:
                local_items = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-id='soliditylocals'] .sol-item"
                )

                for item in local_items:
                    try:
                        key = item.find_element(By.CSS_SELECTOR, ".key").text
                        value = item.find_element(By.CSS_SELECTOR, ".value").text
                        variables[f"local_{key}"] = value
                    except:
                        continue
            except:
                pass

            # Measure time
            extract_time = self.driver.execute_script("""
                return performance.now() - window.extractStartTime;
            """)

            print(f"  [OK] Extracted {len(variables)} variables in {extract_time:.2f}ms")
            return variables, extract_time
        except Exception as e:
            print(f"  [ERROR] Variable extraction failed: {e}")
            return {}, 0

    def measure_debug_latency(self, contract_filename, contract_code, function_name, inputs=None, state_slots=None, state_arrays=None):
        """
        Measure complete debugging latency for a contract function

        Args:
            contract_filename: Name of the contract file (e.g., "AloeBlend_c.sol")
            contract_code: Solidity source code
            function_name: Function to test
            inputs: Function inputs (optional)
            state_slots: State slot setup data (optional)
            state_arrays: State array setup data (optional)

        Returns:
            dict with timing breakdowns and metrics
        """
        results = {}
        total_start = time.perf_counter()

        try:
            print(f"\n{'='*60}")
            print(f"Testing function: {function_name}")
            print(f"{'='*60}")

            # 1. Create contract file in Remix
            setup_start = time.perf_counter()
            self._create_contract_file(contract_filename, contract_code)
            results['setup_time_ms'] = (time.perf_counter() - setup_start) * 1000

            # 2. Compile
            compile_start = time.perf_counter()
            self._compile_contract()
            results['compile_time_ms'] = (time.perf_counter() - compile_start) * 1000

            # 3. Deploy
            deploy_start = time.perf_counter()
            self._deploy_contract()
            results['deploy_time_ms'] = (time.perf_counter() - deploy_start) * 1000

            # 4. Set state slots if needed
            state_slot_start = time.perf_counter()
            if state_slots:
                self._set_state_slots(state_slots)
            if state_arrays:
                self._set_state_arrays(state_arrays)
            results['state_slot_setup_time_ms'] = (time.perf_counter() - state_slot_start) * 1000
            results['num_state_slots'] = len(state_slots) if state_slots else 0
            results['num_state_arrays'] = len(state_arrays) if state_arrays else 0

            # 5. Execute function
            # Count debug buttons before execution to ensure we debug the target function only
            debug_btns_before = len(self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-shared='txLoggerDebugButton']"
            ))
            print(f"  [INFO] Debug buttons before target function: {debug_btns_before}")

            exec_start = time.perf_counter()
            self._execute_function(function_name, inputs)
            results['execution_time_ms'] = (time.perf_counter() - exec_start) * 1000

            # 6. Open debugger (using performance.now())
            # Pass the count to ensure we only debug the target function
            results['debug_open_time_ms'] = self._open_debugger(expected_button_index=debug_btns_before)

            # 7. Get total steps (ByteOp)
            results['byteop_count'] = self._get_total_steps()

            # 8. Jump to end (using performance.now())
            results['jump_to_end_time_ms'] = self._jump_to_end()

            # 9. Extract variables (using performance.now())
            variables, extract_time = self._extract_variables()
            results['variable_extraction_time_ms'] = extract_time
            results['num_variables_extracted'] = len(variables)
            results['variables'] = variables

            # Calculate total
            results['total_time_ms'] = (time.perf_counter() - total_start) * 1000

            # Calculate "pure debugging time" (what user experiences after setup)
            results['pure_debug_time_ms'] = (
                results['debug_open_time_ms'] +
                results['jump_to_end_time_ms'] +
                results['variable_extraction_time_ms']
            )

            results['success'] = True

            print(f"\n{'-'*60}")
            print(f"[OK] Benchmark completed successfully")
            print(f"  Pure Debug Time: {results['pure_debug_time_ms']:.2f}ms")
            print(f"  Total Time: {results['total_time_ms']:.2f}ms")
            print(f"  ByteOp Count: {results['byteop_count']}")
            print(f"{'-'*60}\n")

        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            print(f"\n[ERROR] Benchmark failed: {e}\n")

        return results


def load_dataset():
    """Load evaluation dataset"""
    # Use relative path from Evaluation/Remix directory
    import os
    dataset_path = os.path.join('..', '..', 'dataset', 'evaluation_Dataset.xlsx')

    df = pd.read_excel(dataset_path, header=0)
    df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
                  'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
                  'Target_Variables']

    # Remove first row if it's the Korean header
    if len(df) > 0 and df.iloc[0]['Size_KB'] == '용량':
        df = df.iloc[1:].reset_index(drop=True)

    return df


def load_input_file(contract_filename):
    """Load input data (state slots, arrays, inputs) from JSON file"""
    import os
    input_filename = contract_filename.replace('.sol', '_input.json')
    input_path = os.path.join('..', '..', 'dataset', 'contraction_remix', input_filename)

    if not os.path.exists(input_path):
        print(f"  [WARNING] Input file not found: {input_filename}")
        return None, None, None

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    state_slots = data.get('state_slots', {})
    state_arrays = data.get('state_arrays', {})
    inputs = data.get('inputs', [])

    return state_slots, state_arrays, inputs


def run_benchmark_suite(num_runs=3, sample_size=None):
    """
    Run benchmark suite on dataset contracts

    Args:
        num_runs: Number of times to run each test (for averaging)
        sample_size: If specified, only test this many contracts (for quick testing)
    """
    # Load dataset
    df = load_dataset()

    if sample_size:
        df = df.head(sample_size)

    print(f"\n{'='*60}")
    print(f"Remix Benchmark Suite")
    print(f"Total contracts: {len(df)}")
    print(f"Runs per contract: {num_runs}")
    print(f"{'='*60}\n")

    # Initialize benchmark
    benchmark = RemixBenchmark(headless=False)

    all_results = []

    for idx, row in df.iterrows():
        contract_name = row['Contract_Name']
        sol_file = row['Sol_File_Name']
        function_name = row['Function_Name']
        annotation_targets = row['Annotation_Targets']
        state_slots_count = row['State_Slots']

        print(f"\n{'#'*60}")
        print(f"Contract {idx + 1}/{len(df)}: {contract_name}")
        print(f"Function: {function_name}")
        print(f"Annotation Targets: {annotation_targets}")
        print(f"State Slots: {state_slots_count}")
        print(f"{'#'*60}")

        # Load contract code from local file system
        import os
        contract_filename = sol_file.replace('.sol', '_c.sol')
        contract_path = os.path.join('..', '..', 'dataset', 'contraction_remix', contract_filename)

        if not os.path.exists(contract_path):
            print(f"[WARNING] Contract file not found: {contract_path}")
            continue

        with open(contract_path, 'r', encoding='utf-8') as f:
            contract_code = f.read()

        # Load input file (state slots, arrays, inputs)
        state_slots, state_arrays, inputs = load_input_file(contract_filename)

        if state_slots is None and state_arrays is None and not inputs:
            print(f"[WARNING] No input data found, skipping contract: {contract_name}")
            continue

        print(f"Input data loaded:")
        print(f"  - State slots: {len(state_slots) if state_slots else 0}")
        print(f"  - State arrays: {len(state_arrays) if state_arrays else 0}")
        print(f"  - Function inputs: {len(inputs) if inputs else 0}")

        # Run multiple times
        for run in range(num_runs):
            print(f"\n--- Run {run + 1}/{num_runs} ---")

            result = benchmark.measure_debug_latency(
                contract_filename=contract_filename,
                contract_code=contract_code,
                function_name=function_name,
                inputs=inputs,
                state_slots=state_slots,
                state_arrays=state_arrays
            )

            # Add metadata
            result['contract_name'] = contract_name
            result['function_name'] = function_name
            result['annotation_targets'] = annotation_targets
            result['expected_state_slots'] = state_slots_count
            result['run_number'] = run + 1

            all_results.append(result)

            # Reset for next run
            if run < num_runs - 1:
                benchmark.reset()
                time.sleep(2)

        # Reset for next contract
        benchmark.reset()
        time.sleep(2)

    # Close browser
    benchmark.close()

    # Save results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv('remix_benchmark_results.csv', index=False)
    results_df.to_json('remix_benchmark_results.json', orient='records', indent=2)

    print(f"\n{'='*60}")
    print(f"[OK] Benchmark suite completed")
    print(f"Results saved to:")
    print(f"  - remix_benchmark_results.csv")
    print(f"  - remix_benchmark_results.json")
    print(f"{'='*60}\n")

    return results_df


if __name__ == "__main__":
    import sys

    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--full':
            # Full benchmark: All 30 contracts, 1 run each
            print("\n>> Running FULL benchmark (30 contracts x 1 run)")
            print("   Estimated time: ~30 minutes")
            print("Press Ctrl+C within 5 seconds to cancel...\n")
            time.sleep(5)
            results = run_benchmark_suite(num_runs=1, sample_size=None)
        elif sys.argv[1] == '--quick':
            # Quick test: 3 contracts, 1 run each
            print("\n>> Running QUICK test (3 contracts x 1 run)")
            results = run_benchmark_suite(num_runs=1, sample_size=3)
        else:
            print("Usage: python remix_benchmark.py [--full|--quick]")
            print("  --full:  Measure all 30 contracts (recommended for final results)")
            print("  --quick: Test with 3 contracts only (for testing)")
            sys.exit(1)
    else:
        # Default: Full benchmark
        print("\n>> Running FULL benchmark (30 contracts x 1 run)")
        print("   Estimated time: ~30 minutes")
        print("   Tip: Use '--quick' for testing with 3 contracts only")
        print("Press Ctrl+C within 5 seconds to cancel...\n")
        time.sleep(5)
        results = run_benchmark_suite(num_runs=1, sample_size=None)

    # Show summary statistics
    if len(results) > 0:
        print("\n" + "="*60)
        print("FINAL SUMMARY STATISTICS")
        print("="*60)
        print(f"Total measurements: {len(results)}")
        print(f"Unique contracts: {results['contract_name'].nunique()}")
        print(f"\nLatency Metrics:")
        print(f"  Average Pure Debug Time: {results['pure_debug_time_ms'].mean():.2f}ms")
        print(f"  Median Pure Debug Time:  {results['pure_debug_time_ms'].median():.2f}ms")
        print(f"  Min Pure Debug Time:     {results['pure_debug_time_ms'].min():.2f}ms")
        print(f"  Max Pure Debug Time:     {results['pure_debug_time_ms'].max():.2f}ms")
        print(f"\nByteOp Metrics:")
        print(f"  Average ByteOp Count: {results['byteop_count'].mean():.0f}")
        print(f"  Median ByteOp Count:  {results['byteop_count'].median():.0f}")
        print(f"  Min ByteOp Count:     {results['byteop_count'].min():.0f}")
        print(f"  Max ByteOp Count:     {results['byteop_count'].max():.0f}")
        print(f"\nSuccess Rate: {results['success'].mean() * 100:.1f}%")
        print("="*60)
