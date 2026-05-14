import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from shapely.ops import voronoi_diagram
import fiona
import simplekml
import zipfile
import os
import tempfile

# Mengaktifkan dukungan KML
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

def generate_thiessen(uploaded_file, stations_data):
    # Menggunakan folder sementara (temp) agar aman di server
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, uploaded_file.name)
        
        # Simpan file yang diunggah pengguna ke server
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # Ekstrak jika KMZ, langsung baca jika KML
        if input_path.lower().endswith('.kmz'):
            with zipfile.ZipFile(input_path, 'r') as kmz:
                kml_filename = [name for name in kmz.namelist() if name.endswith('.kml')][0]
                kml_path = kmz.extract(kml_filename, tmpdir)
        else:
            kml_path = input_path
            
        # Baca batas DAS
        das_gdf = gpd.read_file(kml_path, driver='KML')
        das_boundary = das_gdf.geometry.unary_union
        
        # Proses titik stasiun
        points = [Point(lon, lat) for name, lat, lon in stations_data]
        multipoint = MultiPoint(points)
        voronoi_polygons = voronoi_diagram(multipoint, envelope=das_boundary.buffer(0.5))
        
        kml = simplekml.Kml()
        
        # Potong dan masukkan ke KML
        for poly in voronoi_polygons.geoms:
            clipped_poly = poly.intersection(das_boundary)
            if clipped_poly.is_empty:
                continue
                
            station_name = "Tidak Diketahui"
            for name, lat, lon in stations_data:
                if poly.contains(Point(lon, lat)):
                    station_name = name
                    break
                    
            geometries = [clipped_poly] if clipped_poly.geom_type == 'Polygon' else clipped_poly.geoms
            
            for geom in geometries:
                coords = list(geom.exterior.coords)
                pol = kml.newpolygon(name=f"Area {station_name}", outerboundaryis=coords)
                pol.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.aqua)
                pol.style.linestyle.color = simplekml.Color.blue
                pol.style.linestyle.width = 2
                
        # Simpan hasil akhir
        output_kmz_path = os.path.join(tmpdir, "thiessen_result.kmz")
        kml.savekmz(output_kmz_path)
        
        # Baca hasilnya untuk tombol download
        with open(output_kmz_path, "rb") as f:
            kmz_bytes = f.read()
            
        return kmz_bytes

# ==========================================
# ANTARMUKA WEB (STREAMLIT UI)
# ==========================================
st.set_page_config(page_title="Generator Thiessen KMZ", page_icon="🌧️")

st.title("🌧️ Generator Poligon Thiessen DAS")
st.write("Aplikasi web untuk membuat area pengaruh stasiun hujan (Poligon Thiessen) berformat KMZ secara otomatis.")

st.header("1. Upload Batas DAS")
uploaded_file = st.file_uploader("Pilih file batas DAS (Format .kml atau .kmz)", type=['kml', 'kmz'])

st.header("2. Input Koordinat Stasiun")
st.write("Masukkan koordinat stasiun hujan dalam format Decimal Degrees.")

# Buat layout kolom untuk input
stations_data = []
for i in range(5):
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input(f"Nama Stasiun {i+1}", key=f"name_{i}")
    with col2:
        lat = st.text_input(f"Latitude {i+1}", key=f"lat_{i}")
    with col3:
        lon = st.text_input(f"Longitude {i+1}", key=f"lon_{i}")
        
    if name and lat and lon:
        try:
            stations_data.append((name, float(lat), float(lon)))
        except ValueError:
            st.error(f"Format angka pada baris {i+1} salah! Gunakan titik (.), bukan koma.")

# Tombol Eksekusi
st.header("3. Proses dan Download")
if st.button("Mulai Pembuatan Poligon", type="primary"):
    if not uploaded_file:
        st.warning("Harap upload file DAS terlebih dahulu!")
    elif len(stations_data) < 2:
        st.warning("Minimal harus ada 2 stasiun hujan yang valid!")
    else:
        with st.spinner("Sedang memproses peta spasial..."):
            try:
                # Panggil fungsi proses
                result_bytes = generate_thiessen(uploaded_file, stations_data)
                st.success("Poligon berhasil dibuat!")
                
                # Tampilkan tombol download
                st.download_button(
                    label="⬇️ Download Hasil (KMZ)",
                    data=result_bytes,
                    file_name="poligon_thiessen_hasil.kmz",
                    mime="application/vnd.google-earth.kmz"
                )
            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses: {e}")