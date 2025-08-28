# aiohttp variant
import aiohttp
from aiohttp import web
import asyncio
import subprocess
import json
import threading
import aiohttp_jinja2
import jinja2
import os

# Print the current working directory for debugging
print("Current working directory:", os.getcwd())

# Global variable to hold the current job name
current_job_name = "None"
# Global variable to hold the latest message
latest_message = ""

async def update_current_job():
    global current_job_name
    while True:
        try:
            with open('/userdata/print_ctx.json', 'r') as file:
                data = json.load(file)
                subtask_name = data['subtask_name']
                current_job_name = subtask_name
        except Exception as e:
            print(f"Error reading or parsing JSON file: {e}")
        await asyncio.sleep(10)

@aiohttp_jinja2.template('index.html')
async def printer_hmi(request):
    printer_details = {
        'status': 'Printing',
        'current_job': current_job_name,
        'progress': 75,
        'temperature': {
            'nozzle': 215,
            'bed': 60
        },
        'latest_message': latest_message,
    }
    return {'details': printer_details}

async def home_xyz_func(request):
    global latest_message
    subprocess.run(["/usr/bin/home_xyz.sh"], shell=False)
    latest_message = 'Home XYZ'
    raise web.HTTPFound('/')

async def preheat_100c(request):
    global latest_message
    subprocess.run(["/usr/bin/heatbed_set.sh", "-s", "100"], shell=False)
    latest_message = 'Preheat Activated - 100c'
    raise web.HTTPFound('/')

async def preheat_0c(request):
    global latest_message
    subprocess.run(["/usr/bin/heatbed_set.sh", "-s", "0"], shell=False)
    latest_message = 'Preheat Deactivated'
    raise web.HTTPFound('/')

async def start_bbl_screen_vnc(request):
    global latest_message
    try:
        latest_message = 'VNC Started'
        subprocess.run(["/usr/bin/start_bbl_screen_vnc.sh"], shell=True, timeout=3)
    except subprocess.TimeoutExpired:
        latest_message = 'VNC Started'
    raise web.HTTPFound('/')

async def current_image(request):
    image_path = '/userdata/log/cam/capture/calib_14.jpg'
    return web.FileResponse(image_path)

async def current_model_image(request):
    image_path = '/userdata/log/cam/flc/report/ref_model.png'
    return web.FileResponse(image_path)

async def current_depthmap_image(request):
    image_path = '/userdata/log/cam/flc/report/depth_map.png'
    return web.FileResponse(image_path)

async def current_errmapdepth_image(request):
    image_path = '/userdata/log/cam/flc/report/errmap_depth.png'
    return web.FileResponse(image_path)

app = web.Application()
# Use an absolute path to the templates directory
template_path = os.path.join(os.path.dirname(__file__), 'templates')
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_path))

# Add static file route
static_path = os.path.join(os.path.dirname(__file__), 'static')
app.router.add_static('/static/', static_path)

app.router.add_get('/', printer_hmi)
app.router.add_post('/home_xyz_func', home_xyz_func)
app.router.add_post('/preheat_100c', preheat_100c)
app.router.add_post('/preheat_0c', preheat_0c)
app.router.add_post('/start_bbl_screen_vnc', start_bbl_screen_vnc)
app.router.add_get('/current_image', current_image)
app.router.add_get('/current_model_image', current_model_image)
app.router.add_get('/current_depthmap_image', current_depthmap_image)
app.router.add_get('/current_errmapdepth_image', current_errmapdepth_image)

# Start the background thread for updating the current job
threading.Thread(target=lambda: asyncio.run(update_current_job()), daemon=True).start()

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=5001)