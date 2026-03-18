import subprocess
import sys
import time


def main():
    print("Starting tracker in background...")
    tracker = subprocess.Popen([sys.executable, "tracker.py"])

    # give it a moment to initialise and write the PID file
    time.sleep(2)

    print("Doing work...")
    time.sleep(5)  # replace this with your actual work

    print("Stopping tracker and printing report...")
    subprocess.run([sys.executable, "report.py"])

    tracker.wait()


if __name__ == "__main__":
    main()

