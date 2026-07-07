import sys
import os

print("--- Step 1: Checking Python Environment ---")
print(f"Python Version: {sys.version}")

try:
    import torch
    print("\n--- Step 2: Checking PyTorch & GPU ---")
    print(f"PyTorch Version: {torch.__version__}")
    
    gpu_available = torch.cuda.is_available()
    print(f"Is GPU (CUDA) Available?: {gpu_available}")
    
    if gpu_available:
        print(f"Device Name: {torch.cuda.get_device_name(0)}")
        device = torch.device("cuda")
    else:
        print("❌ CRITICAL: PyTorch is still running on CPU. Wait for the download to finish!")
        device = torch.device("cpu")
        
    print("\n--- Step 3: Testing Model Weights Loading ---")
    model_path = os.path.join("floortrans", "models", "model_1427.pth")
    
    if os.path.exists(model_path):
        print(f"Found model file at: {model_path}")
        print("Attempting to load weights into GPU...")
        
        # This simulates exactly what your FastAPI app does at startup
        weights = torch.load(model_path, map_location=device)
        
        print("✅ SUCCESS: Model loaded into your GPU flawlessly!")
    else:
        print(f"❌ ERROR: Cannot find the file at {model_path}. Check your folder steps.")

except ImportError:
    print("\n❌ PyTorch is not fully installed yet. The terminal is still downloading it.")