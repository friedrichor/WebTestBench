# https://github.com/microsoft/playwright-mcp

PlaywrightTools = [
    ## Browser navigation & window control
    "mcp__playwright__browser_navigate",          # Navigate to a URL
    "mcp__playwright__browser_navigate_back",     # Go back to the previous page in the history
    "mcp__playwright__browser_navigate_forward",  # Go forward in browser history
    "mcp__playwright__browser_close",             # Close the page
    "mcp__playwright__browser_resize",            # Resize the browser window

    ## Page interaction
    "mcp__playwright__browser_click",          # Perform click on a web page
    "mcp__playwright__browser_type",           # Type text into editable element
    "mcp__playwright__browser_press_key",      # Press a key on the keyboard
    "mcp__playwright__browser_hover",          # Hover over element on page
    "mcp__playwright__browser_drag",           # Perform drag and drop between two elements
    "mcp__playwright__browser_select_option",  # Select an option in a dropdown
    "mcp__playwright__browser_fill_form",      # Fill multiple form fields

    ## Page inspection
    "mcp__playwright__browser_snapshot",  # Capture accessibility snapshot of the current page, this is better than screenshot
    # "mcp__playwright__browser_take_screenshot",  # Take a screenshot of the current page. You can't perform actions based on the screenshot, use browser_snapshot for actions.
    "mcp__playwright__browser_console_messages",  # Returns all console messages
    "mcp__playwright__browser_network_requests",  # Returns all network requests since loading the page
    
    ## Mouse actions
    "mcp__playwright__browser_mouse_click_xy",  # Click mouse button at a given position
    "mcp__playwright__browser_mouse_drag_xy",   # Drag left mouse button to a given position
    "mcp__playwright__browser_mouse_move_xy",   # Move mouse to a given position

    ## Browser setup & diagnostics
    "mcp__playwright__browser_install",  # Install Playwright browser drivers

    ## Advanced actions
    "mcp__playwright__browser_run_code",       # Run Playwright code snippet
    "mcp__playwright__browser_evaluate",       # Evaluate JavaScript expression on page or element
    "mcp__playwright__browser_wait_for",       # Wait for text to appear or disappear or a specified time to pass
    "mcp__playwright__browser_handle_dialog",  # Handle a dialog
    "mcp__playwright__browser_file_upload",    # Upload one or multiple files

    ## Tab management
    "mcp__playwright__browser_tabs",        # List, create, close, or select a browser tab.
    "mcp__playwright__browser_tab_list",    # List all open tabs
    "mcp__playwright__browser_tab_new",     # Open a new tab
    "mcp__playwright__browser_tab_select",  # Switch to a specific tab
    "mcp__playwright__browser_tab_close",   # Close a specific tab

    ## Assertions
    "mcp__playwright__browser_generate_locator",        # Generate locator for the given element to use in tests
    "mcp__playwright__browser_verify_element_visible",  # Verify element is visible on the page
    "mcp__playwright__browser_verify_list_visible",     # Verify list is visible on the page
    "mcp__playwright__browser_verify_text_visible",     # Verify text is visible on the page. Prefer browser_verify_element_visible if possible.
    "mcp__playwright__browser_verify_value",            # Verify element value
]
