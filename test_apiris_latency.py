import time
import os
from apiris.client import ApirisClient

def test_apiris_latency_reporting():
    # Provide a dummy string for config path
    client = ApirisClient("dummy.yaml")
    
    # Save the original get
    original_get = client.session.get
    
    class MockResponse:
        def __init__(self, text, status_code):
            self.text = text
            self.status_code = status_code
            self.headers = {}
    
    def mock_get(url, *args, **kwargs):
        # simulate realistic latency
        time.sleep(0.05) # 50ms
        return MockResponse('{"mock": "data"}', 200)
        
    client.session.get = mock_get
    
    try:
        decision = client.get("https://api.openai.com/v1/models")
        # timing_ms should be >= 50ms
        availability = decision.scoring_factors.get("availability_factors", [])
        latency_str = next((f["value"] for f in availability if f["name"] == "Response Latency"), "0ms")
        timing_ms = int(latency_str.replace("ms", ""))
        assert timing_ms >= 50, f"Expected timing_ms >= 50, but got {timing_ms}"
        print(f"PASS: Reported timing_ms {timing_ms}ms accurately reflects the 50ms network delay.")
    finally:
        client.session.get = original_get

if __name__ == "__main__":
    test_apiris_latency_reporting()
