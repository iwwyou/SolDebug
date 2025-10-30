"""
Remix IDE Automated Benchmark Script
Measures debugging latency with state slot setup consideration
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import pandas as pd
from pathlib import Path
import sys
import io

# Fix Windows encoding issue and enable real-time output (unbuffered)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)


class RemixBenchmark:
    def __init__(self, headless=False):
        """Initialize Remix IDE in browser"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")  # Maximize window on startup

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
            print("  [INFO] Resetting Remix workspace...")
            self.driver.execute_script("""
                // Clear workspace
                window.location.reload();
            """)
            #time.sleep(3)

            # Handle popups after reload
            self._handle_popups()

            # Wait for Remix FileSystem API to be available after reload
            print("  [INFO] Waiting for Remix to reload...")
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return typeof window.remixFileSystem !== 'undefined' && window.remixFileSystem !== null")
                )
                #time.sleep(2)
                print("  [OK] Remix FileSystem API ready")
            except TimeoutException:
                print("  [WARNING] Remix FileSystem API not detected after reset")

            # Wait for essential plugins to load (especially Solidity Compiler)
            print("  [INFO] Waiting for Solidity Compiler plugin...")
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[plugin='solidity']"))
                )
                #time.sleep(1)
                print("  [OK] Solidity Compiler plugin loaded")
            except TimeoutException:
                print("  [WARNING] Solidity Compiler plugin not detected after reset")

            print("  [OK] Reset completed")
        except Exception as e:
            print(f"  [WARNING] Reset had issues: {e}")

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

            #time.sleep(2)

            # First, expand the contracts folder if it's collapsed
            print(f"  [INFO] Expanding contracts folder...")
            try:
                # Click on contracts folder to expand it
                contracts_folder = WebDriverWait(self.driver, 0.1).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-id='treeViewLitreeViewItemcontracts']"))
                )
                contracts_folder.click()
                #time.sleep(1)
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
                file_element = WebDriverWait(self.driver, 0.1).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"[data-id='treeViewDivDraggableItemcontracts/{filename}']"))
                )
                file_element.click()
                #time.sleep(2)
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
                    #time.sleep(2)
                    print(f"  [OK] File selected via JavaScript")
                except Exception as e2:
                    print(f"  [ERROR] Could not select file: {e2}")

            # Wait for the editor to be ready
            #WebDriverWait(self.driver, 10).until(
            #    lambda d: d.execute_script("return window.monaco !== undefined")
            #)

            #time.sleep(1)

            print(f"  [OK] Created contract file: {filename}")
        except Exception as e:
            print(f"  [ERROR] Error creating file: {e}")
            raise

    def _compile_contract(self):
        """Compile the contract using header Compile button (faster, no tab switching)"""
        try:
            # Handle any lingering popups before clicking
            self._handle_popups()

            # Click the header Compile button directly (no need to switch to Solidity Compiler tab)
            print("  [INFO] Clicking header Compile button...")
            self.driver.execute_script("""
                const compileBtn = document.querySelector("[data-id='compile-action']");
                if (compileBtn) {
                    compileBtn.click();
                }
            """)

            # Wait for compilation to complete (check for compilation finished indicator)
            # The data-id includes the compiler version, so we use a prefix match
            print("  [INFO] Waiting for compilation to complete...")
            WebDriverWait(self.driver, 15).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "[data-id^='compilationFinishedWith']")
            )
            print("  [OK] Compilation successful")
        except Exception as e:
            print(f"  [ERROR] Compilation failed: {e}")
            raise

    def _get_current_account(self):
        """Get currently selected account address from Remix"""
        default_account = "0x5B38Da6a701c568545dCfcB03FcB875f56beddC4"  # Remix default Account 1

        try:
            # Try multiple methods to get the account address
            current_account = self.driver.execute_script("""
                try {
                    // Method 1: Try copy button content attribute
                    const accountLabel = document.querySelector('label.udapp_settingsLabel');
                    if (accountLabel) {
                        const copyIcon = accountLabel.querySelector('i.fa-copy[content]');
                        if (copyIcon) {
                            const content = copyIcon.getAttribute('content');
                            if (content) return content;
                        }
                    }

                    // Method 2: Try to get from the select element value
                    const accountSelect = document.querySelector('[data-id="settingsSelectEnvOptions"]');
                    if (accountSelect) {
                        const selectedOption = accountSelect.options[accountSelect.selectedIndex];
                        if (selectedOption && selectedOption.value) {
                            // Extract address from value if it contains one
                            const match = selectedOption.value.match(/(0x[a-fA-F0-9]{40})/);
                            if (match) return match[1];
                        }
                    }

                    // Method 3: Try to get from runTabView account select
                    const runAccountSelect = document.querySelector('select[data-id="runTabSelectAccount"]');
                    if (runAccountSelect) {
                        const value = runAccountSelect.value;
                        if (value && value.startsWith('0x') && value.length >= 42) {
                            return value.substring(0, 42);
                        }
                    }

                    // Method 4: Look for account text in the UI
                    const accountTexts = Array.from(document.querySelectorAll('*')).filter(el => {
                        const text = el.textContent || '';
                        return text.match(/0x[a-fA-F0-9]{40}/);
                    });

                    for (const el of accountTexts) {
                        const match = el.textContent.match(/(0x[a-fA-F0-9]{40})/);
                        if (match) {
                            // Verify it's likely an account (not a contract address)
                            const context = el.textContent.toLowerCase();
                            if (context.includes('account') || el.closest('[data-id*="account"]')) {
                                return match[1];
                            }
                        }
                    }

                    return null;
                } catch (e) {
                    console.error('[ACCOUNT] JavaScript error:', e);
                    return null;
                }
            """)

            if current_account:
                print(f"  [INFO] Current Remix account: {current_account}")
                return current_account
            else:
                print(f"  [WARNING] Could not get current account, using Remix default: {default_account}")
                return default_account
        except Exception as e:
            # Simplify error message - just show the error type, not the full stacktrace
            error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
            print(f"  [WARNING] Error getting current account: {error_msg}")
            print(f"  [INFO] Using default account: {default_account}")
            return default_account

    def _deploy_contract(self, deploy_value=None):
        """Deploy contract to JavaScript VM

        Args:
            deploy_value: Amount of Wei to send with deployment (for payable constructors)
        """
        try:
            # Handle any lingering popups before clicking
            self._handle_popups()

            # Click Deploy & Run Transactions tab using JavaScript (instant)
            print("  [INFO] Opening Deploy & Run Transactions tab...")
            self.driver.execute_script("""
                const deployTab = document.querySelector("[plugin='udapp']");
                if (deployTab) {
                    deployTab.click();
                }
            """)
            print("  [OK] Deploy tab opened")

            # Ensure JavaScript VM is selected (default)
            env_select = self.driver.find_element(By.CSS_SELECTOR, "[data-id='settingsSelectEnvOptions']")
            if "Remix VM" not in env_select.text:
                env_select.click()
                vm_option = self.driver.find_element(By.XPATH, "//option[contains(text(), 'Remix VM')]")
                vm_option.click()

            # Set Value field if deploy_value is provided
            if deploy_value is not None and deploy_value != "0":
                print(f"  [INFO] Setting deploy value: {deploy_value} Wei")
                value_input = self.driver.find_element(By.CSS_SELECTOR, "[data-id='dandrValue']")
                value_input.clear()
                value_input.send_keys(str(deploy_value))
                time.sleep(0.3)
                print(f"  [OK] Deploy value set to {deploy_value} Wei")

            # Click Deploy button (data-id includes function type, so use prefix match)
            deploy_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-id^='Deploy']")
            deploy_btn.click()

            # Wait for deployment - check for deployed contract instance
            print("  [INFO] Waiting for contract deployment...")
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-shared='universalDappUiInstance']"))
            )

            # Additional wait for contract to fully initialize
            #time.sleep(2)

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

            # Expand the bottom panel (terminal area) to make debug buttons more visible
            print("  [INFO] Expanding bottom panel for better visibility...")
            try:
                self.driver.execute_script("""
                    // Find the terminal panel using the correct selector
                    const terminalView = document.querySelector('#terminal-view');
                    const terminalWrap = document.querySelector('.terminal-wrap');

                    if (terminalView) {
                        // Increase the height to make debug buttons more visible
                        terminalView.style.height = '500px';
                        terminalView.style.minHeight = '500px';
                        console.log('Terminal view height set to 500px');
                    }

                    if (terminalWrap) {
                        terminalWrap.style.height = '500px';
                        terminalWrap.style.minHeight = '500px';
                        console.log('Terminal wrap height set to 500px');
                    }

                    // Find the draggable separator and adjust it
                    const separator = document.querySelector('.gutter.gutter-vertical');
                    if (separator) {
                        // Adjust separator position to expand bottom panel
                        separator.style.top = 'calc(100% - 500px)';
                        console.log('Separator adjusted');
                    }

                    // Force a window resize event to update the layout
                    window.dispatchEvent(new Event('resize'));
                """)
                time.sleep(1)  # Wait for panel to resize
                print("  [OK] Bottom panel expanded")
            except Exception as e:
                print(f"  [WARNING] Could not expand bottom panel: {e}")

            print("  [OK] Contract deployed")
            return True
        except Exception as e:
            print(f"  [ERROR] Deployment failed: {e}")
            raise

    def _set_state_slots(self, state_slots_data):
        """
        Set state variables before function execution using setter functions
        state_slots_data: dict of {variable_name: value or dict}

        For simple variables: {"_totalSupply": 500}
        For mapping variables: {"_balances": {"0xAddress": 1000}}
        For nested mapping: {"allowance": {"0xAddr1": {"0xAddr2": 100}}}
        """
        if not state_slots_data or len(state_slots_data) == 0:
            return

        try:
            # Get current Remix account to replace msg.sender in mappings
            current_account = self._get_current_account()

            # 1. Handle nested mappings: allowed[_from][msg.sender] or allowance[_from][msg.sender]
            # Replace msg.sender (inner key) with current account
            for mapping_name in ["allowed", "allowance"]:
                if mapping_name in state_slots_data:
                    value = state_slots_data[mapping_name]
                    # Check if it's a nested mapping (dict of dict)
                    if isinstance(value, dict):
                        first_value = next(iter(value.values()), None)
                        if isinstance(first_value, dict):
                            # Nested mapping detected
                            print(f"  [INFO] Adjusting nested '{mapping_name}' mapping for msg.sender = {current_account}")
                            adjusted_mapping = {}
                            for from_addr, inner_mapping in value.items():
                                # Replace all inner keys with current account (msg.sender)
                                adjusted_mapping[from_addr] = {}
                                for _, allowance_value in inner_mapping.items():
                                    adjusted_mapping[from_addr][current_account] = allowance_value
                                    print(f"    → {mapping_name}[{from_addr}][{current_account}] = {allowance_value}")
                            state_slots_data[mapping_name] = adjusted_mapping

            # 2. Handle single-level mappings that check msg.sender: governorMap[msg.sender]
            # Replace address keys with current account if the key is an address
            for mapping_name in ["governorMap"]:
                if mapping_name in state_slots_data:
                    value = state_slots_data[mapping_name]
                    # Check if it's a single-level mapping with address keys
                    if isinstance(value, dict):
                        first_key = next(iter(value.keys()), None)
                        # Check if first key is an address (starts with 0x and length 42)
                        if first_key and isinstance(first_key, str) and first_key.startswith("0x") and len(first_key) == 42:
                            print(f"  [INFO] Adjusting '{mapping_name}' mapping for msg.sender = {current_account}")
                            adjusted_mapping = {}
                            for old_key, mapping_value in value.items():
                                # Replace address key with current account
                                adjusted_mapping[current_account] = mapping_value
                                print(f"    → {mapping_name}[{old_key}] -> {mapping_name}[{current_account}] = {mapping_value}")
                            state_slots_data[mapping_name] = adjusted_mapping

            # Count total slots (including mapping entries)
            total_slots = sum(
                len(v) if isinstance(v, dict) else 1
                for v in state_slots_data.values()
            )
            print(f"  [SETUP] Setting {total_slots} state slots...")

            for var_name, value in state_slots_data.items():
                # Check if value is a dict (mapping type)
                if isinstance(value, dict):
                    # Handle mapping type
                    self._set_mapping_variable(var_name, value)
                else:
                    # Handle simple type
                    self._set_simple_variable(var_name, value)

            print(f"  [OK] State slots configured")
        except Exception as e:
            print(f"  [WARNING] State slot setup partial failure: {e}")

    def _set_simple_variable(self, var_name, value):
        """Set a simple (non-mapping) state variable"""
        setter_function = f"set_{var_name}"
        print(f"    Setting {var_name} = {value} via {setter_function}")

        try:
            # Find the wrapper for this setter function
            wrapper_selector = f"[data-id='{setter_function} - transact (not payable)-wrapper']"
            wrapper = self.driver.find_element(By.CSS_SELECTOR, wrapper_selector)

            # Find the parent container
            parent_container = wrapper.find_element(By.XPATH, "..")

            # Find input field
            input_field = parent_container.find_element(
                By.CSS_SELECTOR,
                "input[data-id='multiParamManagerBasicInputField']"
            )

            # Input value - convert Python bool to Solidity bool
            if isinstance(value, bool):
                formatted_value = 'true' if value else 'false'
            else:
                formatted_value = str(value)

            input_field.clear()
            input_field.send_keys(formatted_value)
            time.sleep(0.3)

            # Wait for button to be enabled
            button_selector = f"[data-id='{setter_function} - transact (not payable)']"
            WebDriverWait(self.driver, 5).until(
                lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
            )

            # Click setter button
            setter_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
            setter_btn.click()
            time.sleep(0.5)

            print(f"      [OK] {var_name} set successfully")

        except NoSuchElementException:
            print(f"      [SKIP] Could not find setter for {var_name}")
        except Exception as e:
            print(f"      [ERROR] Error setting {var_name}: {e}")

    def _set_mapping_variable(self, var_name, mapping_data):
        """
        Set a mapping state variable
        mapping_data: dict of {key: value} or {key: {nested_key: value}}
        """
        setter_function = f"set_{var_name}"

        for key, value in mapping_data.items():
            if isinstance(value, dict):
                # Check if this is a nested mapping or a struct
                # Decision logic:
                # 1. If all values in the dict are primitives (int/str/bool) AND
                #    all keys look like mapping keys (numeric or address-like),
                #    then it's a nested mapping
                # 2. If values are mixed types or keys look like struct field names,
                #    then it's a struct

                first_value = next(iter(value.values()), None)
                all_values_primitive = all(
                    not isinstance(v, (dict, list))
                    for v in value.values()
                )

                # Check if keys look like mapping keys (numeric strings or addresses)
                keys_look_like_mapping = True
                for k in value.keys():
                    if isinstance(k, str):
                        # Check if it's a numeric string or an address
                        if not (k.isdigit() or (k.startswith("0x") and len(k) >= 10)):
                            keys_look_like_mapping = False
                            break

                # Nested mapping: all values are primitives and keys look like mapping keys
                is_nested_mapping = all_values_primitive and keys_look_like_mapping

                if not is_nested_mapping:
                    # This is a struct (mapping to struct type)
                    print(f"    Setting {var_name}[{key}] = {value} (struct) via {setter_function}")
                    try:
                        self._call_setter_with_params(setter_function, [key, value])
                        print(f"      [OK] {var_name}[{key}] setter called")
                    except NoSuchElementException:
                        print(f"      [SKIP] Could not find setter for {var_name}")
                        break
                    except Exception as e:
                        print(f"      [ERROR] Error setting {var_name}[{key}]: {e}")
                    continue

                # Nested mapping: iterate over nested keys
                for nested_key, nested_value in value.items():
                    print(f"    Setting {var_name}[{key}][{nested_key}] = {nested_value} via {setter_function}")
                    try:
                        self._call_setter_with_params(setter_function, [key, nested_key, nested_value])
                        print(f"      [OK] {var_name}[{key}][{nested_key}] set successfully")
                    except NoSuchElementException:
                        print(f"      [SKIP] Could not find setter for {var_name}")
                        break
                    except Exception as e:
                        print(f"      [ERROR] Error setting {var_name}[{key}][{nested_key}]: {e}")
            else:
                # Simple mapping
                print(f"    Setting {var_name}[{key}] = {value} via {setter_function}")
                try:
                    self._call_setter_with_params(setter_function, [key, value])
                    print(f"      [OK] {var_name}[{key}] setter called")

                    # Verify the value was set by calling the getter
                    self._verify_mapping_value(var_name, key, value)
                except NoSuchElementException:
                    print(f"      [SKIP] Could not find setter for {var_name}")
                    break
                except Exception as e:
                    print(f"      [ERROR] Error setting {var_name}[{key}]: {e}")

    def _verify_mapping_value(self, var_name, key, expected_value):
        """Verify that a mapping value was set correctly by calling the getter"""
        try:
            # Find the getter button for this mapping (public mappings have auto-generated getters)
            getter_selector = f"[data-id='{var_name} - call-wrapper']"

            try:
                getter_wrapper = self.driver.find_element(By.CSS_SELECTOR, getter_selector)

                # Find the parent container
                parent_container = getter_wrapper.find_element(By.XPATH, "..")

                # Find input field
                input_field = parent_container.find_element(
                    By.CSS_SELECTOR,
                    "input[data-id='multiParamManagerBasicInputField']"
                )

                # Input the key to query
                input_field.clear()
                input_field.send_keys(str(key))
                time.sleep(0.2)

                # Click getter button
                button_selector = f"[data-id='{var_name} - call']"
                getter_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                getter_btn.click()
                time.sleep(0.3)

                # Try to read the result
                try:
                    result_element = parent_container.find_element(
                        By.CSS_SELECTOR,
                        "[data-id='udappNotify']"
                    )
                    result_text = result_element.text

                    # Check if result matches expected value
                    if str(expected_value).lower() in result_text.lower():
                        print(f"      [VERIFIED] {var_name}[{key}] = {expected_value}")
                    else:
                        print(f"      [WARNING] {var_name}[{key}] verification failed! Expected: {expected_value}, Got: {result_text}")
                except:
                    print(f"      [INFO] Could not read getter result for {var_name}[{key}]")

            except NoSuchElementException:
                print(f"      [INFO] No getter found for {var_name} (verification skipped)")
        except Exception as e:
            print(f"      [INFO] Verification skipped: {e}")

    def _call_setter_with_params(self, setter_function, params):
        """Call a setter function with multiple parameters"""
        # Find the wrapper for this setter function
        wrapper_selector = f"[data-id='{setter_function} - transact (not payable)-wrapper']"
        wrapper = self.driver.find_element(By.CSS_SELECTOR, wrapper_selector)

        # Find the parent container
        parent_container = wrapper.find_element(By.XPATH, "..")

        # Find input field
        input_field = parent_container.find_element(
            By.CSS_SELECTOR,
            "input[data-id='multiParamManagerBasicInputField']"
        )

        # Input parameters as comma-separated string
        # IMPORTANT: Convert Python types to Solidity format
        formatted_params = []
        for i, p in enumerate(params):
            if isinstance(p, bool):
                # Convert Python bool to Solidity bool (lowercase)
                formatted_params.append('true' if p else 'false')
            elif isinstance(p, dict):
                # Convert dict (struct) to array format for Remix
                # Remix accepts structs as arrays of values in field order
                # Example: {"lpToken":"0x...","isEnabled":true,...} -> ["0x...",true,...]
                struct_values = list(p.values())
                formatted_struct_values = []
                for v in struct_values:
                    if isinstance(v, bool):
                        formatted_struct_values.append('true' if v else 'false')
                    elif isinstance(v, str):
                        # For address (starts with 0x), no quotes needed
                        # For other strings, quotes needed
                        if v.startswith("0x"):
                            formatted_struct_values.append(v)
                        else:
                            formatted_struct_values.append(f'"{v}"')
                    else:
                        formatted_struct_values.append(str(v))
                # Create array string without outer quotes
                array_str = '[' + ','.join(formatted_struct_values) + ']'
                formatted_params.append(array_str)
                print(f"      [INFO] Converted struct to array: {array_str}")
            elif isinstance(p, str) and p.startswith("0x"):
                # Check if this might need bytes4 conversion
                # If it's an address-length hex string (42 chars) and this is a known bytes4 parameter
                if len(p) == 42 and setter_function == "set__quorums" and i == 1:
                    # Convert address to bytes4 (first 4 bytes = 10 chars including 0x)
                    bytes4_value = p[:10]
                    formatted_params.append(bytes4_value)
                    print(f"      [INFO] Converted address to bytes4: {p} -> {bytes4_value}")
                else:
                    formatted_params.append(str(p))
            else:
                formatted_params.append(str(p))

        input_str = ','.join(formatted_params)
        print(f"      [DEBUG] Input: {input_str}")
        input_field.clear()
        input_field.send_keys(input_str)
        time.sleep(0.3)

        # Wait for button to be enabled
        button_selector = f"[data-id='{setter_function} - transact (not payable)']"
        WebDriverWait(self.driver, 5).until(
            lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
        )

        # Click setter button
        setter_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
        setter_btn.click()
        time.sleep(0.5)

        # Check if transaction was reverted by looking at terminal
        try:
            revert_detected = self.driver.execute_script("""
                const terminal = document.querySelector('#terminal-view');
                if (terminal) {
                    const lastLog = terminal.textContent;
                    return lastLog.includes('revert') || lastLog.includes('reverted');
                }
                return false;
            """)
            if revert_detected:
                print(f"      [WARNING] Transaction may have reverted!")
        except:
            pass

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
                        # Use _call_setter_with_params to handle both primitive and struct types
                        # The function signature is: _add{ArrayName}At(value, index)
                        print(f"      Setting {array_name}[{index}] = {value}")
                        self._call_setter_with_params(func_name, [value, index])
                        print(f"      [OK] {array_name}[{index}] set successfully")

                    except NoSuchElementException:
                        print(f"      [SKIP] Could not find function {func_name}")
                        break
                    except Exception as e:
                        print(f"      [ERROR] Error setting {array_name}[{index}]: {e}")
                        continue

            print(f"  [OK] State arrays configured")
        except Exception as e:
            print(f"  [WARNING] State array setup partial failure: {e}")

    def _set_state_mapping_arrays(self, state_arrays_data):
        """
        Set mapping to array state variables using _add*At functions
        state_arrays_data: dict of {mapping_name: {key: [struct_values]}}

        Example:
        {
            "depositsOf": {
                "0xAddress": [
                    {"amount": 100, "start": 1000, "end": 2000},
                    {"amount": 200, "start": 1500, "end": 2500}
                ]
            }
        }

        Calls: _addDepositsOfAt(address, amount, start, end, index)
        """
        if not state_arrays_data or len(state_arrays_data) == 0:
            return

        try:
            print(f"  [SETUP] Setting mapping to array state variables...")

            for mapping_name, mapping_data in state_arrays_data.items():
                # Check if this is a mapping to array structure (dict of lists)
                if not isinstance(mapping_data, dict):
                    continue

                # Check if first value is a list (indicating mapping to array)
                first_value = next(iter(mapping_data.values()), None)
                if not isinstance(first_value, list):
                    continue

                # Generate function name: _add{MappingName}At
                if mapping_name.startswith('_'):
                    func_name = f"_add{mapping_name[1].upper() + mapping_name[2:]}At"
                else:
                    func_name = f"_add{mapping_name[0].upper() + mapping_name[1:]}At"

                print(f"    Setting mapping array {mapping_name} via {func_name}")

                # Iterate over each key (e.g., address)
                for key, array_values in mapping_data.items():
                    print(f"      Setting {mapping_name}[{key}] ({len(array_values)} elements)")

                    for index, struct_value in enumerate(array_values):
                        try:
                            # struct_value is a dict like {"amount": 100, "start": 1000, "end": 2000}
                            # Convert to parameter list: [key, amount, start, end, index]
                            if isinstance(struct_value, dict):
                                # Extract struct fields in order
                                params = [key] + list(struct_value.values()) + [index]
                            else:
                                # Simple value
                                params = [key, struct_value, index]

                            print(f"        Setting {mapping_name}[{key}][{index}] = {struct_value}")
                            self._call_setter_with_params(func_name, params)
                            print(f"        [OK] {mapping_name}[{key}][{index}] set successfully")

                        except NoSuchElementException:
                            print(f"        [SKIP] Could not find function {func_name}")
                            break
                        except Exception as e:
                            print(f"        [ERROR] Error setting {mapping_name}[{key}][{index}]: {e}")
                            continue

            print(f"  [OK] Mapping arrays configured")
        except Exception as e:
            print(f"  [WARNING] Mapping array setup partial failure: {e}")

    def _execute_function(self, function_name, inputs):
        """Execute target function and return transaction hash"""
        try:
            # Try to detect function button type automatically
            # Possible types: transact (not payable), call, transact (payable)
            button_types = [
                ('transact (not payable)', 'transact'),
                ('call', 'call'),
                ('transact (payable)', 'transact')
            ]

            wrapper = None
            button_type_found = None

            print(f"  [INFO] Detecting button type for function: {function_name}")

            for button_type, action_type in button_types:
                wrapper_selector = f"[data-id='{function_name} - {button_type}-wrapper']"
                try:
                    wrapper = self.driver.find_element(By.CSS_SELECTOR, wrapper_selector)
                    button_type_found = button_type
                    print(f"  [OK] Found function button type: {button_type}")
                    break
                except NoSuchElementException:
                    continue

            if wrapper is None:
                # If no specific wrapper found, try to find any button with function name
                print(f"  [WARNING] Standard button types not found, searching for any button...")
                all_buttons = self.driver.find_elements(By.CSS_SELECTOR, f"[data-id*='{function_name}']")
                if all_buttons:
                    print(f"  [INFO] Found {len(all_buttons)} potential buttons:")
                    for btn in all_buttons:
                        print(f"    - {btn.get_attribute('data-id')}")
                raise Exception(f"Could not find button for function '{function_name}'")

            # If function has inputs, fill them
            if inputs:
                # Find the parent container (udapp_contractActionsContainerSingle) that contains both wrapper and input
                parent_container = wrapper.find_element(By.XPATH, "..")

                # Find input field as sibling within the parent container
                function_input = parent_container.find_element(
                    By.CSS_SELECTOR,
                    "input[data-id='multiParamManagerBasicInputField']"
                )

                # Format inputs (handle bytes4 conversion if needed)
                formatted_inputs = []
                if isinstance(inputs, list):
                    for i, v in enumerate(inputs):
                        # Check if this is a bytes4 parameter for quorums function
                        if function_name == "quorums" and i == 1 and isinstance(v, str) and v.startswith("0x"):
                            # Ensure it's bytes4 format (10 chars)
                            if len(v) != 10:
                                v = v[:10]
                                print(f"  [INFO] Truncated to bytes4: {v}")
                        formatted_inputs.append(str(v))
                    input_str = ','.join(formatted_inputs)
                else:
                    input_str = str(inputs)

                print(f"  [INFO] Entering parameters: {input_str}")

                function_input.clear()
                function_input.send_keys(input_str)
                time.sleep(0.3)  # Wait for input to register

            # Wait for button to be enabled (it gets enabled after input)
            button_selector = f"[data-id='{function_name} - {button_type_found}']"
            print(f"  [INFO] Waiting for button to be enabled...")

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: not d.find_element(By.CSS_SELECTOR, button_selector).get_attribute('disabled')
                )
            except TimeoutException:
                print(f"  [WARNING] Button enable timeout, attempting to click anyway...")

            # Scroll button into view and click using JavaScript (more reliable)
            function_btn = self.driver.find_element(By.CSS_SELECTOR, button_selector)
            print(f"  [INFO] Scrolling button into view and clicking...")
            self.driver.execute_script("""
                arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});
                arguments[0].click();
            """, function_btn)

            # Wait for transaction to complete
            time.sleep(0.5)

            print(f"  [OK] Function '{function_name}' executed (type: {button_type_found})")
            return True
        except Exception as e:
            print(f"  [ERROR] Function execution failed: {e}")
            import traceback
            print(f"  [ERROR] Traceback:")
            traceback.print_exc()
            raise

    def _is_debugger_loaded(self):
        """Check if debugger has loaded successfully"""
        try:
            slider = self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']")
            max_val = int(slider.get_attribute('max') or '0')
            return max_val > 0
        except:
            return False

    def _open_debugger(self, expected_button_index=None, manual_click_timeout=60):
        """
        Open debugger for the target function transaction using MANUAL click

        Args:
            expected_button_index: The index where we expect the target function's debug button
                                   (i.e., the number of debug buttons before executing target function)
            manual_click_timeout: Maximum time to wait for manual click (seconds)
        """
        try:
            # Inject performance measurement and click detection
            self.driver.execute_script("""
                window.debugStartTime = performance.now();
                window.manualClickDetected = false;
                window.manualClickTime = null;
            """)

            # Wait for debug button to appear and for event handlers to be attached
            time.sleep(1)  # Initial wait for button to appear

            # Find all debug buttons
            # Use data-shared instead of data-id because data-id includes transaction hash
            debug_btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-shared='txLoggerDebugButton']"
            )

            if len(debug_btns) == 0:
                raise Exception("No debug button found")

            print(f"  [INFO] Found {len(debug_btns)} debug button(s) total", flush=True)

            # CRITICAL: Wait for debug button event handlers to be attached
            # Debug buttons are dynamically created and event handlers may not be immediately ready
            print(f"  [INFO] Waiting for debug button event handlers to be attached...", flush=True)
            time.sleep(2)  # Give time for event handlers to be attached to debug buttons
            print(f"  [OK] Event handlers should be ready", flush=True)

            # Click the target function's debug button
            # If expected_button_index is provided, use that specific button
            # Otherwise, fall back to the last button
            if expected_button_index is not None and len(debug_btns) > expected_button_index:
                target_button_index = expected_button_index
                print(f"  [INFO] Target debug button at index {target_button_index}", flush=True)
            else:
                target_button_index = -1
                print(f"  [INFO] Target debug button at last index (fallback)", flush=True)

            # Validate the index
            actual_index = target_button_index if target_button_index >= 0 else len(debug_btns) + target_button_index
            if actual_index < 0 or actual_index >= len(debug_btns):
                raise Exception(f"Invalid button index: {actual_index} (total buttons: {len(debug_btns)})")

            # Inject manual click event listener BEFORE attempting automatic clicks
            print(f"  [INFO] Setting up manual click detection...", flush=True)
            self.driver.execute_script("""
                const targetButton = arguments[0];
                targetButton.addEventListener('click', function() {
                    window.manualClickDetected = true;
                    window.manualClickTime = performance.now();
                    console.log('[MANUAL CLICK] Detected at:', window.manualClickTime);
                }, true);  // Use capture phase to ensure we catch the event
            """, debug_btns[actual_index])

            # Scroll the debug button into view to ensure it's visible
            print(f"  [INFO] Scrolling debug button into view...", flush=True)
            self.driver.execute_script("""
                arguments[0].scrollIntoView({behavior: 'instant', block: 'center', inline: 'nearest'});
            """, debug_btns[actual_index])
            time.sleep(0.5)

            # Skip automatic clicking - request manual click immediately
            print(f"\n{'='*60}", flush=True)
            print(f"  [MANUAL] Please manually click the Debug button now", flush=True)
            print(f"  [MANUAL] (Look for the 'Debug' button in the terminal area)", flush=True)
            print(f"  [MANUAL] The button is highlighted in YELLOW with RED border", flush=True)
            print(f"  [MANUAL] Waiting for your click (timeout: {manual_click_timeout}s)...", flush=True)
            print(f"{'='*60}\n", flush=True)

            # Highlight the button to make it easier to find
            try:
                self.driver.execute_script("""
                    const btn = arguments[0];
                    btn.style.border = '5px solid red';
                    btn.style.backgroundColor = 'yellow';
                    btn.style.fontWeight = 'bold';
                    btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                """, debug_btns[actual_index])
            except:
                pass

            # Wait for manual click with progress indicator
            wait_start = time.time()
            clicked = False
            last_progress_time = wait_start

            while time.time() - wait_start < manual_click_timeout:
                manual_clicked = self.driver.execute_script("return window.manualClickDetected;")

                if manual_clicked:
                    print(f"  [OK] Manual click detected!", flush=True)
                    clicked = True
                    break

                # Also check if debugger loaded (in case event listener missed it)
                if self._is_debugger_loaded():
                    print(f"  [OK] Debugger loaded (manual click detected indirectly)", flush=True)
                    clicked = True
                    break

                # Show progress every 5 seconds
                elapsed = time.time() - wait_start
                if time.time() - last_progress_time >= 5:
                    remaining = manual_click_timeout - elapsed
                    print(f"  [WAITING] Still waiting for manual click... ({remaining:.0f}s remaining)", flush=True)
                    last_progress_time = time.time()

                time.sleep(0.5)

            if not clicked:
                raise Exception(f"Manual click timeout ({manual_click_timeout}s)")

            # Remove highlight
            try:
                self.driver.execute_script("""
                    const btn = arguments[0];
                    btn.style.border = '';
                    btn.style.backgroundColor = '';
                    btn.style.fontWeight = '';
                """, debug_btns[actual_index])
            except:
                pass

            # Wait for debugger to actually start (check for slider or debugView content)
            # Debug button automatically opens debugger tab and loads the transaction
            print(f"  [INFO] Waiting for debugger to load...", flush=True)
            time.sleep(4)  # Give Remix time to process the debug button click, open debugger tab, and load transaction

            # Wait for debugger tab to open and debugger to start
            # Check multiple conditions to ensure debugging actually started:
            # 1. Slider appears
            # 2. Transaction hash is loaded in txinput field
            # 3. Slider has a valid max value (> 0)

            # Wait for slider to appear
            print(f"  [INFO] Waiting for slider to appear...", flush=True)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-id='slider']"))
            )
            print(f"  [INFO] Slider appeared", flush=True)

            # Wait for transaction hash to be loaded in txinput field
            # The debugger automatically fills this field when debugging starts
            max_auto_retries = 3
            tx_hash_loaded = False

            for retry in range(max_auto_retries):
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: len(d.find_element(By.CSS_SELECTOR, "[data-id='debuggerTransactionInput']").get_attribute('value') or '') > 0
                    )
                    loaded_tx_hash = self.driver.find_element(By.CSS_SELECTOR, "[data-id='debuggerTransactionInput']").get_attribute('value')
                    print(f"  [INFO] Transaction hash loaded in debugger: {loaded_tx_hash}", flush=True)
                    tx_hash_loaded = True
                    break
                except TimeoutException:
                    # Check if transaction hash is actually empty
                    try:
                        current_tx_hash = self.driver.find_element(By.CSS_SELECTOR, "[data-id='debuggerTransactionInput']").get_attribute('value') or ''
                        if current_tx_hash:
                            # Hash exists but timeout occurred, consider it loaded
                            print(f"  [INFO] Transaction hash loaded (via retry check): {current_tx_hash}", flush=True)
                            tx_hash_loaded = True
                            break
                    except:
                        pass

                    # If not the last retry, click debug button again automatically
                    if retry < max_auto_retries - 1:
                        print(f"  [RETRY] Transaction hash not loaded, clicking debug button automatically (retry {retry + 1}/{max_auto_retries - 1})...", flush=True)
                        try:
                            # Click debug button using JavaScript
                            self.driver.execute_script("""
                                arguments[0].click();
                            """, debug_btns[actual_index])

                            # Wait for debugger to process the click
                            time.sleep(4)
                            print(f"  [INFO] Auto-click completed, checking result...", flush=True)
                        except Exception as e:
                            print(f"  [ERROR] Auto-click failed: {e}", flush=True)
                    else:
                        print(f"  [WARNING] Transaction hash not loaded after {max_auto_retries} automatic attempts", flush=True)

            # If auto-clicks failed, request manual click
            if not tx_hash_loaded:
                # Enhanced visual highlighting with animation
                print(f"\n{'='*80}", flush=True)
                print(f"{'='*80}", flush=True)
                print(f"  ⚠️  MANUAL ACTION REQUIRED  ⚠️", flush=True)
                print(f"{'='*80}", flush=True)
                print(f"  Automatic debug button clicks failed!", flush=True)
                print(f"  ", flush=True)
                print(f"  Please MANUALLY CLICK the Debug button:", flush=True)
                print(f"  → The button is in the TERMINAL area at the bottom", flush=True)
                print(f"  → Look for a button with YELLOW background and RED pulsing border", flush=True)
                print(f"  → The button text says 'Debug'", flush=True)
                print(f"  ", flush=True)
                print(f"  Waiting for your click (timeout: 60 seconds)...", flush=True)
                print(f"{'='*80}", flush=True)
                print(f"{'='*80}\n", flush=True)

                # Enhanced highlighting with pulsing animation
                try:
                    self.driver.execute_script("""
                        const btn = arguments[0];

                        // Enhanced styling
                        btn.style.border = '5px solid red';
                        btn.style.backgroundColor = 'yellow';
                        btn.style.fontWeight = 'bold';
                        btn.style.fontSize = '16px';
                        btn.style.padding = '8px 16px';
                        btn.style.boxShadow = '0 0 20px rgba(255, 0, 0, 0.8)';
                        btn.style.zIndex = '10000';
                        btn.style.position = 'relative';

                        // Add pulsing animation
                        btn.style.animation = 'pulse 1s infinite';

                        // Inject animation keyframes if not already present
                        if (!document.getElementById('pulse-animation-style')) {
                            const style = document.createElement('style');
                            style.id = 'pulse-animation-style';
                            style.textContent = `
                                @keyframes pulse {
                                    0% { box-shadow: 0 0 20px rgba(255, 0, 0, 0.8); transform: scale(1); }
                                    50% { box-shadow: 0 0 40px rgba(255, 0, 0, 1); transform: scale(1.05); }
                                    100% { box-shadow: 0 0 20px rgba(255, 0, 0, 0.8); transform: scale(1); }
                                }
                            `;
                            document.head.appendChild(style);
                        }

                        // Scroll button into view
                        btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                    """, debug_btns[actual_index])
                except Exception as e:
                    print(f"  [WARNING] Could not apply enhanced highlighting: {e}", flush=True)

                # Wait for manual click with countdown
                manual_wait_start = time.time()
                manual_timeout = 60
                manual_clicked = False
                last_countdown_time = manual_wait_start

                while time.time() - manual_wait_start < manual_timeout:
                    # Check if transaction hash loaded
                    try:
                        current_tx_hash = self.driver.find_element(By.CSS_SELECTOR, "[data-id='debuggerTransactionInput']").get_attribute('value') or ''
                        if current_tx_hash:
                            print(f"\n  ✅ [OK] Manual click successful!", flush=True)
                            print(f"  [INFO] Transaction hash loaded: {current_tx_hash}", flush=True)
                            tx_hash_loaded = True
                            manual_clicked = True
                            break
                    except:
                        pass

                    # Also check if debugger loaded
                    if self._is_debugger_loaded():
                        print(f"\n  ✅ [OK] Manual click successful - debugger loaded!", flush=True)
                        manual_clicked = True
                        break

                    # Show countdown every 10 seconds
                    elapsed = time.time() - manual_wait_start
                    if time.time() - last_countdown_time >= 10:
                        remaining = manual_timeout - elapsed
                        print(f"  ⏳ Still waiting for manual click... ({remaining:.0f}s remaining)", flush=True)
                        last_countdown_time = time.time()

                    time.sleep(0.5)

                if not manual_clicked:
                    print(f"\n  ❌ [ERROR] Manual click timeout (60s exceeded)", flush=True)
                    print(f"  [ERROR] Please check if the Debug button is visible in the terminal area", flush=True)
                else:
                    time.sleep(2)  # Wait for debugger to stabilize

                # Remove highlight and animation
                try:
                    self.driver.execute_script("""
                        const btn = arguments[0];
                        btn.style.border = '';
                        btn.style.backgroundColor = '';
                        btn.style.fontWeight = '';
                        btn.style.fontSize = '';
                        btn.style.padding = '';
                        btn.style.boxShadow = '';
                        btn.style.zIndex = '';
                        btn.style.animation = '';
                        btn.style.position = '';
                    """, debug_btns[actual_index])
                except:
                    pass

            # Wait for slider to have a valid max value (debugging actually started)
            # When debugging starts, slider max is set to the total number of steps
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: int(d.find_element(By.CSS_SELECTOR, "[data-id='slider']").get_attribute('max') or '0') > 0
                )
                slider_max = int(self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']").get_attribute('max'))
                print(f"  [INFO] Slider initialized with max value: {slider_max}", flush=True)
            except TimeoutException:
                print(f"  [WARNING] Slider max value not set within timeout", flush=True)
                # Try to get current max value anyway
                try:
                    slider_max = int(self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']").get_attribute('max') or '0')
                    print(f"  [INFO] Current slider max: {slider_max}", flush=True)
                except:
                    pass

            # Additional wait to ensure UI is fully ready
            time.sleep(1)

            # Measure time using performance API
            # If manual click was used, use the manual click time; otherwise use current time
            debug_open_time = self.driver.execute_script("""
                if (window.manualClickTime !== null) {
                    console.log('[TIME] Using manual click time:', window.manualClickTime);
                    return window.manualClickTime - window.debugStartTime;
                } else {
                    console.log('[TIME] Using automatic click time');
                    return performance.now() - window.debugStartTime;
                }
            """)

            print(f"  [OK] Debugger opened and debugging started in {debug_open_time:.2f}ms", flush=True)
            return debug_open_time
        except Exception as e:
            print(f"  [ERROR] Failed to open debugger: {e}")
            raise

    def _get_vm_trace_step(self):
        """Get current vm trace step from Step details panel"""
        try:
            # Try multiple methods to read vm trace step from Step details
            vm_trace_step = self.driver.execute_script("""
                try {
                    // Method 1: Parse from JSON (most reliable if available)
                    const rawContent = document.querySelector('.dropdownrawcontent');
                    if (rawContent) {
                        const data = JSON.parse(rawContent.textContent);
                        if (data["vm trace step"] !== undefined) {
                            console.log('[VM TRACE] Read from JSON:', data["vm trace step"]);
                            return data["vm trace step"];
                        }
                    }

                    // Method 2: Read from DOM - try multiple selectors
                    // Based on HTML structure: <li data-id="treeViewLivm trace step">...<span class="m-0 label_value">260</span>
                    const selectors = [
                        '[data-id="treeViewLivm trace step"] .label_value span',
                        '[data-id="treeViewLivm trace step"] span.label_value',
                        '[data-id="treeViewDivvm trace step"] .label_value span'
                    ];

                    for (const selector of selectors) {
                        const element = document.querySelector(selector);
                        if (element && element.textContent.trim()) {
                            const value = parseInt(element.textContent.trim());
                            if (!isNaN(value)) {
                                console.log('[VM TRACE] Read from DOM selector:', selector, '=', value);
                                return value;
                            }
                        }
                    }

                    console.warn('[VM TRACE] Could not find vm trace step in Step details');
                    return null;
                } catch (e) {
                    console.error('[VM TRACE] Error reading vm trace step:', e);
                    return null;
                }
            """)

            if vm_trace_step is not None:
                return vm_trace_step
            else:
                raise Exception("Could not read vm trace step from Step details")

        except Exception as e:
            # Fallback to slider value if Step details not available
            print(f"  [WARNING] Could not read vm trace step, using slider value: {e}")
            try:
                slider = self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']")
                return int(slider.get_attribute("value"))
            except:
                return None

    def _jump_to_end(self):
        """Jump to the last step of execution by clicking step over forward until end
        Only counts steps where vm trace step changes (actual ByteOp execution)

        Returns:
            tuple: (jump_time_ms, start_vm_step, end_vm_step, byteop_step_count)
        """
        try:
            # Inject performance measurement
            self.driver.execute_script("""
                window.jumpStartTime = performance.now();
            """)

            print(f"  [INFO] Starting step-by-step execution to end...", flush=True)

            # Get initial vm trace step (START point - only once!)
            start_vm_step = self._get_vm_trace_step()
            print(f"  [INFO] Start vm trace step: {start_vm_step}", flush=True)

            # Get initial slider position and max value
            slider = self.driver.find_element(By.CSS_SELECTOR, "[data-id='slider']")
            max_steps = int(slider.get_attribute('max'))

            print(f"  [INFO] Total trace steps (slider max): {max_steps}", flush=True)

            # Track vm trace step changes (actual ByteOp execution)
            prev_vm_step = start_vm_step
            byteop_step_count = 0
            total_ui_steps = 0
            max_iterations = max_steps + 10  # Safety limit

            while total_ui_steps < max_iterations:
                try:
                    # Get current slider value
                    current_step = int(slider.get_attribute('value'))

                    # Check if we've reached the end
                    if current_step >= max_steps:
                        print(f"  [OK] Reached end of execution at UI step {current_step}", flush=True)
                        break

                    # Enable pointer-events and click the step over forward button
                    # Target the container div (buttonNavigatorOverForwardContainer)
                    clicked = self.driver.execute_script("""
                        const container = document.querySelector('[data-id="buttonNavigatorOverForward"]');
                        const button = document.querySelector('#overforward');

                        if (container) {
                            // Enable pointer events on button if disabled
                            if (button) {
                                button.style.pointerEvents = 'auto';
                            }
                            // Click the container div
                            container.click();
                            return true;
                        } else {
                            return false;
                        }
                    """)

                    if not clicked:
                        print(f"  [WARNING] Could not find step over forward button", flush=True)
                        break

                    # Small wait for UI to update
                    time.sleep(0.05)  # 50ms between steps

                    total_ui_steps += 1

                    # Check if vm trace step changed (every 10 UI steps to reduce overhead)
                    if total_ui_steps % 10 == 0:
                        current_vm_step = self._get_vm_trace_step()
                        if current_vm_step is not None and current_vm_step != prev_vm_step:
                            byteop_step_count += (current_vm_step - prev_vm_step)
                            prev_vm_step = current_vm_step

                except Exception as e:
                    print(f"  [WARNING] Error during step execution: {e}", flush=True)
                    break

            if total_ui_steps >= max_iterations:
                print(f"  [WARNING] Reached max iterations limit", flush=True)

            print(f"  [INFO] Executed {total_ui_steps} UI steps (trace detail steps)", flush=True)

            # Get final vm trace step (END point - only once!)
            # Wait longer for Step details panel to update after many steps
            time.sleep(2)  # Increased from 0.5s to 2s for UI to fully stabilize

            # Retry logic to ensure we get vm trace step from Step details (not slider)
            end_vm_step = None
            for retry in range(3):
                end_vm_step = self._get_vm_trace_step()
                if end_vm_step is not None:
                    # Verify it's from Step details, not slider fallback
                    # If it's close to max_steps, it's likely a slider value (incorrect)
                    if abs(end_vm_step - max_steps) > 10:
                        print(f"  [INFO] End vm trace step: {end_vm_step} (retry {retry})", flush=True)
                        break
                    else:
                        print(f"  [WARNING] Got slider-like value {end_vm_step}, retrying...", flush=True)
                        time.sleep(1)
                        end_vm_step = None
                else:
                    print(f"  [WARNING] Could not read vm trace step (retry {retry}), waiting...", flush=True)
                    time.sleep(1)

            if end_vm_step is None:
                print(f"  [ERROR] Failed to read end vm trace step after retries", flush=True)
                # Fallback: use start + byteop_step_count as estimate
                end_vm_step = start_vm_step + byteop_step_count if start_vm_step is not None else None
                if end_vm_step is not None:
                    print(f"  [FALLBACK] Estimated end vm trace step: {end_vm_step} (start + byteop_step_count)", flush=True)

            # Calculate final byteop count including any remaining steps
            if end_vm_step is not None and prev_vm_step is not None:
                byteop_step_count += (end_vm_step - prev_vm_step)

            # Measure time
            jump_time = self.driver.execute_script("""
                return performance.now() - window.jumpStartTime;
            """)

            print(f"  [OK] Stepped to end in {jump_time:.2f}ms", flush=True)
            print(f"      UI steps executed: {total_ui_steps} (trace detail)", flush=True)
            print(f"      ByteOp steps: {byteop_step_count} (actual instructions)", flush=True)
            return jump_time, start_vm_step, end_vm_step, byteop_step_count
        except Exception as e:
            print(f"  [ERROR] Failed to jump to end: {e}", flush=True)
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

    def measure_debug_latency(self, contract_filename, contract_code, function_name, inputs=None, state_slots=None, state_arrays=None, deploy_value=None):
        """
        Measure complete debugging latency for a contract function

        Args:
            contract_filename: Name of the contract file (e.g., "AloeBlend_c.sol")
            contract_code: Solidity source code
            function_name: Function to test
            inputs: Function inputs (optional)
            state_slots: State slot setup data (optional)
            state_arrays: State array setup data (optional)
            deploy_value: Amount of Wei to send with deployment (optional)

        Returns:
            dict with timing breakdowns and metrics
        """
        # Initialize results with None for all fields (in case of failure)
        results = {
            'setup_time_ms': None,
            'compile_time_ms': None,
            'deploy_time_ms': None,
            'state_slot_setup_time_ms': None,
            'num_state_slots': None,
            'num_state_arrays': None,
            'execution_time_ms': None,
            'debug_open_time_ms': None,
            'byteop_count': None,
            'jump_to_end_time_ms': None,
            'total_time_ms': None,
            'pure_debug_time_ms': None,
            'success': False,
            'error': None
        }

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
            self._deploy_contract(deploy_value=deploy_value)
            results['deploy_time_ms'] = (time.perf_counter() - deploy_start) * 1000

            # 4. Set state slots if needed
            state_slot_start = time.perf_counter()
            if state_slots:
                self._set_state_slots(state_slots)
            if state_arrays:
                self._set_state_arrays(state_arrays)
                # Also handle mapping to array structures
                self._set_state_mapping_arrays(state_arrays)
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

            # 7. Jump to end (using performance.now()) and get vm trace steps
            jump_time, start_vm_step, end_vm_step, byteop_step_count = self._jump_to_end()
            results['jump_to_end_time_ms'] = jump_time

            # 8. Store ByteOp count (actual instruction count during stepping)
            # Use the tracked count from _jump_to_end(), which counts vm trace step changes
            if byteop_step_count is not None and byteop_step_count > 0:
                results['byteop_count'] = byteop_step_count
                print(f"  [INFO] ByteOp count (from stepping): {byteop_step_count} instructions")
            elif start_vm_step is not None and end_vm_step is not None:
                # Fallback: calculate from start and end
                results['byteop_count'] = end_vm_step - start_vm_step
                print(f"  [INFO] ByteOp count calculated: {start_vm_step} → {end_vm_step} = {results['byteop_count']} steps")
            else:
                print(f"  [WARNING] Could not calculate ByteOp count (start: {start_vm_step}, end: {end_vm_step})")
                results['byteop_count'] = None

            # Note: Variable extraction removed - users can see variables directly in browser
            # No need to extract them via Selenium (slow and unnecessary)

            # Calculate total
            results['total_time_ms'] = (time.perf_counter() - total_start) * 1000

            # Calculate "pure debugging time" (what user experiences after setup)
            results['pure_debug_time_ms'] = (
                results['debug_open_time_ms'] +
                results['jump_to_end_time_ms']
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
    """Load input data (state slots, arrays, inputs, deploy_value) from JSON file"""
    import os
    input_filename = contract_filename.replace('.sol', '_input.json')
    input_path = os.path.join('..', '..', 'dataset', 'contraction_remix', input_filename)

    if not os.path.exists(input_path):
        print(f"  [WARNING] Input file not found: {input_filename}")
        return None, None, None, None

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    state_slots = data.get('state_slots', {})
    state_arrays = data.get('state_arrays', {})
    inputs = data.get('inputs', [])
    deploy_value = data.get('deploy_value', None)

    return state_slots, state_arrays, inputs, deploy_value


def save_result_to_file(result, csv_file='remix_benchmark_results.csv', json_file='remix_benchmark_results.json'):
    """
    Save a single result to CSV and JSON files (append mode)
    This ensures results are preserved even if the script is interrupted
    """
    import os

    # Create DataFrame from single result
    result_df = pd.DataFrame([result])

    # Append to CSV
    if os.path.exists(csv_file):
        # Append to existing file
        result_df.to_csv(csv_file, mode='a', header=False, index=False)
    else:
        # Create new file with header
        result_df.to_csv(csv_file, mode='w', header=True, index=False)

    # For JSON, we need to read, append, and write
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                all_data = []
    else:
        all_data = []

    all_data.append(result)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2)

    print(f"  [SAVED] Result saved to {csv_file} and {json_file}")


def run_single_contract(contract_filename, num_runs=1):
    """
    Run benchmark for a single contract

    Args:
        contract_filename: Contract file to test (e.g., "BEP20_c.sol")
        num_runs: Number of times to run the test

    Returns:
        DataFrame with results
    """
    import os

    # Load dataset to get contract info
    df = load_dataset()

    # Normalize: dataset uses .sol, but actual files use _c.sol
    # So if user provides "GovStakingStorage_c.sol", we search for "GovStakingStorage.sol" in dataset
    dataset_filename = contract_filename.replace('_c.sol', '.sol')

    # Find the contract in dataset
    contract_row = None
    for idx, row in df.iterrows():
        if row['Sol_File_Name'] == dataset_filename:
            contract_row = row
            break

    if contract_row is None:
        print(f"[ERROR] Contract not found in dataset: {contract_filename}")
        print(f"        (searched for: {dataset_filename})")
        print("\nAvailable contracts in dataset (add _c before .sol for actual files):")
        for name in df['Sol_File_Name'].unique():
            actual_name = name.replace('.sol', '_c.sol')
            print(f"  - {actual_name}")
        return pd.DataFrame()

    # Get contract info
    contract_name = contract_row['Contract_Name']
    function_name = contract_row['Function_Name']
    annotation_targets = contract_row['Annotation_Targets']
    state_slots_count = contract_row['State_Slots']

    print(f"\n{'='*60}")
    print(f"SINGLE CONTRACT BENCHMARK")
    print(f"{'='*60}")
    print(f"File: {contract_filename}")
    print(f"Contract: {contract_name}")
    print(f"Function: {function_name}")
    print(f"Runs: {num_runs}")
    print(f"{'='*60}\n")

    # Results files
    csv_file = 'remix_benchmark_results.csv'
    json_file = 'remix_benchmark_results.json'

    # Create benchmark instance
    benchmark = RemixBenchmark(headless=False)
    all_results = []

    try:
        # Load contract code - use actual filename with _c.sol
        actual_filename = contract_filename if contract_filename.endswith('_c.sol') else contract_filename.replace('.sol', '_c.sol')
        contract_path = os.path.join('..', '..', 'dataset', 'contraction_remix', actual_filename)

        if not os.path.exists(contract_path):
            print(f"[ERROR] Contract file not found: {contract_path}")
            return pd.DataFrame()

        with open(contract_path, 'r', encoding='utf-8') as f:
            contract_code = f.read()

        # Load input file (state slots, arrays, inputs, deploy_value)
        state_slots, state_arrays, inputs, deploy_value = load_input_file(contract_filename)

        if state_slots is None and state_arrays is None and not inputs:
            print(f"[WARNING] No input data found for contract: {contract_name}")

        print(f"Input data loaded:")
        print(f"  - State slots: {len(state_slots) if state_slots else 0}")
        print(f"  - State arrays: {len(state_arrays) if state_arrays else 0}")
        print(f"  - Function inputs: {len(inputs) if inputs else 0}")
        print(f"  - Deploy value: {deploy_value if deploy_value else 0} Wei")

        # Run multiple times
        for run in range(num_runs):
            print(f"\n--- Run {run + 1}/{num_runs} ---")

            result = benchmark.measure_debug_latency(
                contract_filename=contract_filename,
                contract_code=contract_code,
                function_name=function_name,
                inputs=inputs,
                state_slots=state_slots,
                state_arrays=state_arrays,
                deploy_value=deploy_value
            )

            # Add metadata
            result['contract_name'] = contract_name
            result['function_name'] = function_name
            result['annotation_targets'] = annotation_targets
            result['expected_state_slots'] = state_slots_count
            result['run_number'] = run + 1

            all_results.append(result)

            # Save result immediately
            save_result_to_file(result, csv_file, json_file)

            # Reset for next run
            if run < num_runs - 1:
                benchmark.reset()
                time.sleep(2)

    finally:
        # Close browser
        benchmark.close()

    # Create DataFrame
    results_df = pd.DataFrame(all_results)

    print(f"\n{'='*60}")
    print(f"[OK] Single contract benchmark completed")
    print(f"Results saved to:")
    print(f"  - {csv_file}")
    print(f"  - {json_file}")
    print(f"{'='*60}\n")

    return results_df


def run_benchmark_suite(num_runs=3, sample_size=None, start_from=None):
    """
    Run benchmark suite on dataset contracts

    Args:
        num_runs: Number of times to run each test (for averaging)
        sample_size: If specified, only test this many contracts (for quick testing)
        start_from: If specified, start from this contract file name (e.g., "AvatarArtMarketPlace_c.sol")
    """
    # Load dataset
    df = load_dataset()

    # If start_from is specified, skip contracts until we find the matching one
    if start_from:
        found_index = None
        for idx, row in df.iterrows():
            contract_filename = row['Sol_File_Name'].replace('.sol', '_c.sol')
            if contract_filename == start_from:
                found_index = idx
                break

        if found_index is not None:
            df = df.iloc[found_index:].reset_index(drop=True)
            print(f"\n[INFO] Starting from contract: {start_from} (skipped {found_index} contracts)")
        else:
            print(f"\n[WARNING] Contract {start_from} not found in dataset, starting from beginning")

    if sample_size:
        df = df.head(sample_size)

    print(f"\n{'='*60}")
    print(f"Remix Benchmark Suite")
    print(f"Total contracts: {len(df)}")
    print(f"Runs per contract: {num_runs}")
    if start_from:
        print(f"Starting from: {start_from}")
    print(f"{'='*60}\n")

    # Initialize benchmark
    benchmark = RemixBenchmark(headless=False)

    all_results = []

    # File paths
    csv_file = 'remix_benchmark_results.csv'
    json_file = 'remix_benchmark_results.json'

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

        # Load input file (state slots, arrays, inputs, deploy_value)
        state_slots, state_arrays, inputs, deploy_value = load_input_file(contract_filename)

        if state_slots is None and state_arrays is None and not inputs:
            print(f"[WARNING] No input data found, skipping contract: {contract_name}")
            continue

        print(f"Input data loaded:")
        print(f"  - State slots: {len(state_slots) if state_slots else 0}")
        print(f"  - State arrays: {len(state_arrays) if state_arrays else 0}")
        print(f"  - Function inputs: {len(inputs) if inputs else 0}")
        print(f"  - Deploy value: {deploy_value if deploy_value else 0} Wei")

        # Run multiple times
        for run in range(num_runs):
            print(f"\n--- Run {run + 1}/{num_runs} ---")

            result = benchmark.measure_debug_latency(
                contract_filename=contract_filename,
                contract_code=contract_code,
                function_name=function_name,
                inputs=inputs,
                state_slots=state_slots,
                state_arrays=state_arrays,
                deploy_value=deploy_value
            )

            # Add metadata
            result['contract_name'] = contract_name
            result['function_name'] = function_name
            result['annotation_targets'] = annotation_targets
            result['expected_state_slots'] = state_slots_count
            result['run_number'] = run + 1

            all_results.append(result)

            # IMPORTANT: Save result immediately to preserve it even if interrupted
            save_result_to_file(result, csv_file, json_file)

            # Reset for next run
            if run < num_runs - 1:
                benchmark.reset()
                time.sleep(2)

        # Reset for next contract
        benchmark.reset()
        time.sleep(2)

    # Close browser
    benchmark.close()

    # Clean up results file (remove duplicates and sort)
    import os

    if os.path.exists(csv_file):
        print(f"\n[INFO] Cleaning up results file...")
        results_df = pd.read_csv(csv_file)

        # Remove duplicates based on contract_name, function_name, and run_number
        # Keep the last occurrence (most recent run)
        results_df = results_df.drop_duplicates(
            subset=['contract_name', 'function_name', 'run_number'],
            keep='last'
        )

        # Sort by contract_name and run_number for better readability
        results_df = results_df.sort_values(
            by=['contract_name', 'run_number']
        ).reset_index(drop=True)

        # Save cleaned results
        results_df.to_csv(csv_file, index=False)
        results_df.to_json(json_file, orient='records', indent=2)

        print(f"[INFO] Final results: {len(results_df)} rows")
    else:
        results_df = pd.DataFrame(all_results)

    print(f"\n{'='*60}")
    print(f"[OK] Benchmark suite completed")
    print(f"Results saved to:")
    print(f"  - {csv_file}")
    print(f"  - {json_file}")
    print(f"  (Results are saved incrementally after each run)")
    print(f"{'='*60}\n")

    return results_df


if __name__ == "__main__":
    import sys

    # Check command line arguments
    start_from_file = None

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
        elif sys.argv[1] == '--start-from':
            # Start from a specific contract file
            if len(sys.argv) < 3:
                print("ERROR: --start-from requires a filename argument")
                print("Usage: python remix_benchmark.py --start-from AvatarArtMarketPlace_c.sol")
                sys.exit(1)
            start_from_file = sys.argv[2]
            print(f"\n>> Running benchmark starting from: {start_from_file}")
            print("Press Ctrl+C within 5 seconds to cancel...\n")
            time.sleep(5)
            results = run_benchmark_suite(num_runs=1, sample_size=None, start_from=start_from_file)
        elif sys.argv[1] == '--only':
            # Run only a specific contract
            if len(sys.argv) < 3:
                print("ERROR: --only requires a filename argument")
                print("Usage: python remix_benchmark.py --only BEP20_c.sol")
                sys.exit(1)
            contract_file = sys.argv[2]
            num_runs = int(sys.argv[3]) if len(sys.argv) > 3 else 1
            print(f"\n>> Running benchmark for single contract: {contract_file}")
            print(f"   Number of runs: {num_runs}")
            print("Press Ctrl+C within 5 seconds to cancel...\n")
            time.sleep(5)
            results = run_single_contract(contract_file, num_runs=num_runs)
        else:
            print("Usage: python remix_benchmark.py [OPTIONS]")
            print("\nOptions:")
            print("  --full                 Measure all 30 contracts (recommended for final results)")
            print("  --quick                Test with 3 contracts only (for testing)")
            print("  --start-from FILENAME  Start from a specific contract file")
            print("  --only FILENAME [RUNS] Run only a specific contract (default: 1 run)")
            print("\nExamples:")
            print("  python remix_benchmark.py --full")
            print("  python remix_benchmark.py --quick")
            print("  python remix_benchmark.py --start-from BEP20_c.sol")
            print("  python remix_benchmark.py --only BEP20_c.sol")
            print("  python remix_benchmark.py --only BEP20_c.sol 3")
            sys.exit(1)
    else:
        # Default: Full benchmark
        print("\n>> Running FULL benchmark (30 contracts x 1 run)")
        print("   Estimated time: ~30 minutes")
        print("   Tip: Use '--quick' for testing with 3 contracts only")
        print("   Tip: Use '--start-from FILENAME' to resume from a specific contract")
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

        # Filter successful results for metrics
        successful = results[results['pure_debug_time_ms'].notna()]

        if len(successful) > 0:
            print(f"\nLatency Metrics:")
            print(f"  Average Pure Debug Time: {successful['pure_debug_time_ms'].mean():.2f}ms")
            print(f"  Median Pure Debug Time:  {successful['pure_debug_time_ms'].median():.2f}ms")
            print(f"  Min Pure Debug Time:     {successful['pure_debug_time_ms'].min():.2f}ms")
            print(f"  Max Pure Debug Time:     {successful['pure_debug_time_ms'].max():.2f}ms")
            print(f"\nByteOp Metrics:")
            print(f"  Average ByteOp Count: {successful['byteop_count'].mean():.0f}")
            print(f"  Median ByteOp Count:  {successful['byteop_count'].median():.0f}")
            print(f"  Min ByteOp Count:     {successful['byteop_count'].min():.0f}")
            print(f"  Max ByteOp Count:     {successful['byteop_count'].max():.0f}")

        print(f"\nSuccess Rate: {(len(successful)/len(results) * 100):.1f}% ({len(successful)}/{len(results)})")
        print("="*60)
