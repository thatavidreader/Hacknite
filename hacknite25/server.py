#import
import os
import requests
import numpy as np
import folium
from flask import Flask, render_template, send_file
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, bbox_to_dimensions, BBox

#flask app
app = Flask(__name__)

#sentinel satellite api
config = SHConfig()
config.sh_client_id = "cbdf46c0-c676-4218-9f2e-fb4efc3109da"
config.sh_client_secret = "FEDSA1s13BjmlhgAkcgpuedLkwAlUZI9"

#farm location coords
center_lon, center_lat = 79.655, 10.777  # Change to your farm location
bbox_size = 0.005  # Adjust area size
BBOX_COORDS = [
    center_lon - bbox_size / 2, center_lat - bbox_size / 2,
    center_lon + bbox_size / 2, center_lat + bbox_size / 2
]
bbox = BBox(BBOX_COORDS, crs=3857)  # Use EPSG:3857 (Web Mercator)
resolution = 10  # 10m per pixel
size = bbox_to_dimensions(bbox, resolution=resolution)

#crop water needs
crop_water_needs = {"wheat": 0.2, "corn": 0.3, "rice": 0.4}
crop_type = "rice"  # Change as per your crop
required_ndmi = crop_water_needs[crop_type]

#soil moisture ndmi-
evalscript_ndmi = """
function setup() {
    return {
        input: ["B08", "B11"],
        output: { bands: 1, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [(sample.B08 - sample.B11) / (sample.B08 + sample.B11)];
}
"""

# flaskroute
@app.route("/")
def index():
    return render_template("index.html")

#irrigation simulation
@app.route("/run_simulation")
def run_simulation():
    # Fetch Weather Data 
    api_key = "fbba9e57ccf14604a33180804252903"  # Replace with your API Key
    lat, lon = center_lat, center_lon
    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={lat},{lon}"

    response = requests.get(url)
    weather_data = response.json()

    if "current" in weather_data:
        temperature = weather_data["current"]["temp_c"]
        rainfall = weather_data["current"]["precip_mm"]
    else:
        temperature = np.random.uniform(20, 40)  # Simulated temperature
        rainfall = np.random.choice([0, np.random.uniform(10, 30)])  # Simulated rainfall

    # Sentinel NDMI Data Request
    ndmi_request = SentinelHubRequest(
        evalscript=evalscript_ndmi,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=("2025-02-15", "2025-03-15"),
            maxcc=0.2  # Max cloud coverage 20%
        )],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config
    )

    ndmi_image = ndmi_request.get_data()[0].astype(np.float32)

    # NDMI Thresholding
    ndmi_threshold = 0.125  # Dry areas
    medium_threshold = 0.15  # Medium areas

    dry_pixels = np.where(ndmi_image < ndmi_threshold)
    med_pixels = np.where((ndmi_image >= ndmi_threshold) & (ndmi_image < medium_threshold))

    # Function to convert pixel coordinates to lat/lon
def pixel_to_geo(pixel_x, pixel_y, bbox, img_size):
    lon_min, lat_min, lon_max, lat_max = bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y  # ✅ Correct
    img_width, img_height = img_size  # Image dimensions

    lon = lon_min + (pixel_x / img_width) * (lon_max - lon_min)
    lat = lat_max - (pixel_y / img_height) * (lat_max - lat_min)
    
    return [lat, lon]

    # Convert pixel locations to lat/lon
    dry_locations = [pixel_to_geo(x, y, bbox, size) for x, y in zip(dry_pixels[1], dry_pixels[0])]
    med_locations = [pixel_to_geo(x, y, bbox, size) for x, y in zip(med_pixels[1], med_pixels[0])]

    # Generate Map with Dry & Medium Zones
    farm_map = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles="Esri.WorldImagery")

    for lat, lon in dry_locations:
        folium.CircleMarker(location=[lat, lon], radius=1.5, color='red', fill=False).add_to(farm_map)

    for lat, lon in med_locations:
        folium.CircleMarker(location=[lat, lon], radius=1.5, color='yellow', fill=False).add_to(farm_map)

    # **Save the Map in Templates Directory**
    map_path = "templates/dry_areas_map.html"
    farm_map.save(map_path)

    # **Render the Map in Flask**
    return render_template("dry_areas_map.html")


#run flasl
if __name__ == "__main__":
    app.run(debug=True)
