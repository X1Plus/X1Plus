import subprocess
from functools import lru_cache
import os


@lru_cache(None)
def is_emulating():
    return not os.path.exists("/etc/bblap")


@lru_cache(None)
def serial_number():
    """
    Used to get the Serial Number for the Printer
    """
    return subprocess.check_output(["bbl_3dpsn"], stderr=subprocess.DEVNULL).decode(
        "utf-8"
    )


def get_MAC() -> str:
    """Return the MAC address of the wireless interface."""
    if is_emulating():
        return "CC:BD:D3:00:3B:D5"
    with open(f"/sys/class/net/wlan0/address", "r") as file:
        mac_address = file.read().strip()
    return mac_address


def get_IP() -> str:
    """Return the IP address of the printer. This is currently on hold."""
    pass
    # if is_emulating():
    #     return "192.168.2.113"
    # hostname = subprocess.run(["hostname", "-I"], capture_output=True)
    # return hostname.stdout.decode().split(" ")[0]


def capture_frames(device_path="/dev/video20", output_dir="ipcam", num_frames=10, interval=2):
    """
    Capture num_frames single frame images from camera at interval of `interval`
    seconds and save to /sdcard/ipcam directory.

    To capture from nozzle cam, set `device_path` to /dev/video13.

    Note that many franes may be captured, that they will be overwritten on
    the next call to capture_frames, and that at no point are the captured
    frames deleted from the SD card, so use with caution.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        pixel_format = "--set-fmt-video=width=1280,height=720,pixelformat=MJPG"
        if device_path == "/dev/video13":
            # Note I defaulted to YUYV here. Could also be NV12.
            "--set-fmt-video=width=640,height=480,pixelformat=YUYV"

        cap_cmd = ["v4l2-ctl", "--device", device_path, "--all"]
        result = subprocess.run(cap_cmd, capture_output=True, text=True)
        logger.info(f"{result.stdout}")

        logger.debug("Setting video format.")
        fmt_cmd = [
            "v4l2-ctl",
            "--device",
            device_path,
            pixel_format,
        ]
        subprocess.run(fmt_cmd, check=True)

        for i in range(num_frames):
            output_file = os.path.join(output_dir, f"frame_{i}.jpg")
            capture_cmd = [
                "v4l2-ctl",
                "--device",
                device_path,
                "--stream-mmap=3",
                "--stream-count=1",
                "--stream-to",
                output_file,
            ]

            result = subprocess.run(capture_cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Saved frame_{i}.jpg")
            else:
                logger.error(f"Failed to capture frame {i}. Error: {result.stderr}")

            if i < num_frames - 1:
                time.sleep(interval)

    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred during capture: {str(e)}")
    except Exception as e:
        logger.error(f"unexpected error occurred: {str(e)}", exc_info=True)
