#!/usr/bin/env python3
"""
Life System Builder - Full Stack Startup Script
Starts both the FastAPI backend and React + Vite frontend
"""

import subprocess
import time
import os
import sys
import signal

def print_header(message):
    """Print a formatted header message"""
    print(f"\n🚀 {message}\n")

def print_success(message):
    """Print a success message"""
    print(f"✓ {message}")

def print_warning(message):
    """Print a warning message"""
    print(f"⚠️  {message}")

def print_info(message):
    """Print an info message"""
    print(f"📍 {message}")

def main():
    print_header("Starting Life System Builder Full Stack")
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print_warning("OPENAI_API_KEY is not set")
        print("   Some AI features will not work without this API key.\n")
    
    # List to keep track of processes
    processes = []
    
    try:
        # Start backend
        print_info("Starting backend (FastAPI on port 8080)...")
        backend_process = subprocess.Popen(
            ["uv", "run", "main.py"],
            cwd="/vercel/share/v0-project",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        processes.append(("Backend", backend_process))
        print_success("Backend process started (PID: {})".format(backend_process.pid))
        
        # Wait for backend to start
        time.sleep(3)
        
        # Start frontend
        print_info("Starting frontend (React + Vite on port 5173)...")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="/vercel/share/v0-project/artifacts/life-system-builder",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        processes.append(("Frontend", frontend_process))
        print_success("Frontend process started (PID: {})".format(frontend_process.pid))
        
        # Print startup information
        print_header("✓ Both services started!")
        print("📱 Frontend: http://localhost:5173")
        print("🔌 Backend API: http://localhost:8080\n")
        print("Press Ctrl+C to stop all services\n")
        
        # Wait for processes to complete
        for name, process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        print("\n\nShutting down services...")
        for name, process in processes:
            try:
                process.terminate()
                print_info("Terminated {}".format(name))
            except:
                pass
        
        # Give processes time to terminate gracefully
        time.sleep(1)
        
        # Force kill if necessary
        for name, process in processes:
            if process.poll() is None:
                try:
                    process.kill()
                    print_info("Force killed {}".format(name))
                except:
                    pass
        
        print_success("All services stopped")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        # Clean up any started processes
        for name, process in processes:
            try:
                process.terminate()
            except:
                pass
        sys.exit(1)

if __name__ == "__main__":
    main()
