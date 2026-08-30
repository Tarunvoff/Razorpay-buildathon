import time
import os
from playwright.sync_api import sync_playwright

def take_screenshots():
    out_dir = r"C:\Users\TARUN\.gemini\antigravity-ide\brain\849d26d8-5fb0-48af-a687-b2278807202d\scratch"
    os.makedirs(out_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:5173')
        time.sleep(3)
        
        # Initial ALLOW state is already present in the mock data
        page.screenshot(path=os.path.join(out_dir, "allow_state.png"), full_page=True)
        
        # Now click the "Walkthrough" tab or equivalent to run a flag scenario
        # Let's just click "Live Dashboard"
        try:
            page.get_by_text('Live Dashboard').click()
            time.sleep(1)
            # Find the "Simulate Behavior Flag" button
            page.get_by_text('Simulate Behavior Flag').click()
            time.sleep(3) # Wait for the scenario to run and SSE event to arrive
            page.screenshot(path=os.path.join(out_dir, "flag_state.png"), full_page=True)
        except Exception as e:
            print(f"Error simulating flag: {e}")
        
        browser.close()

if __name__ == "__main__":
    take_screenshots()
