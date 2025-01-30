import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import streamlit as st
import plotly.express as px
import altair as alt
from numerize import numerize
from datetime import datetime 
from auth import login

# Page configuration
st.set_page_config(
    page_title="Data Call Center",
    page_icon="💖",
    layout="centered",
    initial_sidebar_state="expanded")

def connect_db():
    conn = psycopg2.connect(
        dbname='callcenter', 
        user='postgres', 
        password='123456',
        host='localhost',
        port='5432'
    )
    return conn

# Fungsi untuk mengambil data dari database berdasarkan query
def fetch_data_from_db(query):
    # Koneksi ke database
    conn = connect_db()
    
    # Menggunakan pandas untuk membaca hasil query dan mengubahnya menjadi DataFrame
    df = pd.read_sql(query, conn)
    
    # Menutup koneksi
    conn.close()

    return df

# Fungsi untuk memotong string jika melebihi batas panjang
def truncate_string(value, max_length=200):
    if isinstance(value, str) and len(value) > max_length:
        return value[:max_length]  # Potong string jika panjangnya lebih dari max_length
    return value

def insert_csv_to_db(df, table_name):
    # Ubah nama kolom menjadi huruf kecil dan ganti spasi dengan underscore
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    # Mengisi nilai kosong dengan '-'
    df.fillna('-', inplace=True)

    # Cek apakah kolom 'waktu_lapor' ada
    if 'waktu_lapor' in df.columns:
        df['waktu_lapor'] = pd.to_datetime(df['waktu_lapor'], errors='coerce')
        df['waktu_lapor'] = df['waktu_lapor'].where(df['waktu_lapor'].notna(), None)

    # Cek apakah kolom 'waktu_selesai' ada
    if 'waktu_selesai' in df.columns:
        df['waktu_selesai'] = pd.to_datetime(df['waktu_selesai'], errors='coerce')
        df['waktu_selesai'] = df['waktu_selesai'].where(df['waktu_selesai'].notna(), None)

    # Cek panjang string dan potong jika lebih dari 200 karakter
    for col in df.columns:
        df[col] = df[col].apply(truncate_string)

    # Koneksi ke database
    conn = connect_db()
    cur = conn.cursor()

    # Menyusun query untuk menetapkan format date style pada PostgreSQL
    cur.execute("SET datestyle TO 'ISO, DMY'")  # Atur format tanggal ke 'DD/MM/YYYY'

    if table_name == 'laporan':
        # Query untuk tabel laporan
        insert_query = """
        INSERT INTO laporan (
            no, uid, no_laporan, tipe_saluran, waktu_lapor, 
            agent_l1, tipe_laporan, pelapor, no_telp, kategori, 
            sub_kategori_1, sub_kategori_2, deskripsi, lokasi_kejadian, 
            kecamatan, kelurahan, catatan_lokasi, latitude, longitude, 
            waktu_selesai, ditutup_oleh, status, dinas_terkait, durasi_pengerjaan
        ) 
        VALUES %s
        """
        data = [tuple(x if pd.notna(x) else None for x in row) 
        for row in df[['no', 'uid', 'no_laporan', 'tipe_saluran', 'waktu_lapor', 
                                            'agent_l1', 'tipe_laporan', 'pelapor', 'no_telp', 'kategori', 
                                            'sub_kategori_1', 'sub_kategori_2', 'deskripsi', 'lokasi_kejadian', 
                                            'kecamatan', 'kelurahan', 'catatan_lokasi', 'latitude', 'longitude', 
                                            'waktu_selesai', 'ditutup_oleh', 'status', 'dinas_terkait', 'durasi_pengerjaan']].values]
    elif table_name == 'tiket_dinas':
        # Query untuk tabel tiket dinas
        insert_query = """
        INSERT INTO tiket_dinas (
            no_laporan, uid_dinas, no_tiket_dinas, dinas, l2_notes, 
            status, tiket_dibuat, tiket_selesai, durasi_penanganan
        ) 
        VALUES %s
        """
        data = [tuple(x) for x in df[['no.laporan', 'uid_dinas', 'no.tiket_dinas', 'dinas', 'l2_notes', 
                                      'status', 'tiket_dibuat', 'tiket_selesai', 'durasi_penanganan']].values]
    elif table_name == 'log_dinas':
        # Query untuk tabel log dinas
        insert_query = """
        INSERT INTO log_dinas (
            no_laporan, no_tiket_dinas, dinas, agent_l2, status, 
            waktu_proses, durasi_penanganan, catatan, foto_1, foto_2, foto_3, foto_4
        ) 
        VALUES %s
        """
        check_query = """
        SELECT COUNT(*) FROM log_dinas
        WHERE no_tiket_dinas = %s AND status = %s AND catatan = %s
        """
        data = [tuple(x) for x in df[['no.laporan', 'no.tiket_dinas', 'dinas', 'agent_l2', 'status', 
                                      'waktu_proses', 'durasi_penanganan', 'catatan', 'foto_1', 
                                      'foto_2', 'foto_3', 'foto_4']].values]
    valid_data = []
    duplicate_count = 0  # Hitung data duplikat
    inserted_count = 0  # Hitung data yang berhasil dimasukkan

    for row in data:
        # Periksa hanya jika check_query ada (untuk log_dinas)
        if table_name == 'log_dinas':
            cur.execute(check_query, (row[1], row[4], row[7]))  # no_tiket_dinas, status, catatan
            if cur.fetchone()[0] == 0:
                valid_data.append(row)
            else:
                duplicate_count += 1  # Tambahkan ke hitungan duplikat
        else:
            valid_data.append(row)  # Untuk tabel selain log_dinas, anggap data valid

    try:
        if valid_data:
            execute_values(cur, insert_query, valid_data)
            inserted_count = len(valid_data)  # Hitung data yang berhasil dimasukkan

        conn.commit()
        if inserted_count > 0:
            st.success(f"Data berhasil dimasukkan ke dalam database!")
        if duplicate_count > 0:
            st.warning(f"Data sudah ada di database dan tidak dimasukkan.")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.error("Terjadi kesalahan: duplikasi data ditemukan.")
    except Exception as e:
        conn.rollback()
        st.error(f"Terjadi kesalahan: {e}")
    finally:
        cur.close()
        conn.close()

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Fungsi untuk menampilkan statistik
def generate_statistics(df, table_name):
    st.subheader("📊 Statistik")
    total = len(df)

    if table_name == 'laporan' and 'status' in df.columns:
        # Normalisasi nilai kolom status
        df['status'] = df['status'].str.strip().str.lower()

        # Hitung jumlah setiap status
        selesai = df[df['status'] == 'selesai'].shape[0]
        proses = df[df['status'].str.contains('proses', case=False)].shape[0]
        baru = df[df['status'].str.contains('baru', case=False)].shape[0]

        # Tampilkan statistik di UI
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Data", total)
        col2.metric("Selesai", selesai)
        col3.metric("Proses", proses)
        col4.metric("Baru", baru)

    elif table_name in ['tiket_dinas', 'log_dinas'] and 'status' in df.columns:
        # Statistik untuk tiket_dinas dan log_dinas
        df['status'] = df['status'].str.strip().str.lower()
        total2 = len(df)
        aktif = df[df['status'] == 'aktif'].shape[0]
        dikerjakan = df[df['status'].str.contains('dikerjakan', case=False)].shape[0]
        selesai = df[df['status'] == 'selesai'].shape[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Data",total2)
        col2.metric("Aktif", aktif)
        col3.metric("Dikerjakan", dikerjakan)
        col4.metric("Selesai", selesai)

# Fungsi untuk visualisasi data
def generate_visualizations(df, table_name):
    if table_name == 'laporan':

        # Visualisasi distribusi status laporan
        if 'status' in df.columns:
            fig_pie = px.pie(df, names='status', title='Distribusi Status Laporan')
            st.plotly_chart(fig_pie)

        # Visualisasi tipe laporan
        if 'tipe_laporan' in df.columns:
            tipe_laporan_count = df['tipe_laporan'].value_counts().reset_index()
            tipe_laporan_count.columns = ['tipe_laporan', 'jumlah']
            fig_tipe = px.bar(
                tipe_laporan_count, 
                x='tipe_laporan', 
                y='jumlah', 
                labels={'tipe_laporan': 'Tipe Laporan', 'jumlah': 'Jumlah'}, 
                title="Distribusi Tipe Laporan"
            )
            st.plotly_chart(fig_tipe)

    elif table_name == 'tiket_dinas':

        # Visualisasi distribusi status tiket_dinas
        if 'status' in df.columns:
            fig_pie = px.pie(df, names='status', title='Distribusi Status Tiket Dinas')
            st.plotly_chart(fig_pie)

    elif table_name == 'log_dinas':

        # Visualisasi distribusi status log_dinas
        if 'status' in df.columns:
            fig_pie = px.pie(df, names='status', title='Distribusi Status Log Dinas')
            st.plotly_chart(fig_pie)

# Streamlit interface
st.sidebar.title("Menu")
options = st.sidebar.selectbox("Pilih Menu", ["HomePage", "Unggah Data", "Statistik", "Pencarian Data"])

# Opsi untuk halaman yang dipilih
if options == "HomePage":
    # Buat kolom dengan proporsi yang sesuai
    col1, col2 = st.columns([1, 6])

    with col1:
        st.image("image/gambar2.png", width=80)  # Pastikan path benar

    with col2:
        st.markdown(
            "<h3 style='display: flex; align-items: center; margin: 0;'>"
            "Selamat Datang di Aplikasi Manajemen Data Call Center Kabupaten Sidoarjo</h3>",
            unsafe_allow_html=True
        )

    # Deskripsi aplikasi
    st.markdown(
        """
        **Aplikasi Manajemen Data Call Center Kabupaten Sidoarjo**  

        Aplikasi ini dirancang untuk membantu pengelolaan data call center di Kabupaten Sidoarjo dengan lebih efisien dan terorganisir. Dengan fitur unggah, filter, dan pencarian data, aplikasi ini mempermudah pelacakan dan analisis informasi secara real-time, memastikan respons yang lebih cepat dan akurat terhadap setiap laporan atau permintaan yang masuk.  
        """
    )

    st.markdown(
        """
        ---
        🚀 **Mulai jelajahi aplikasi ini sekarang! Pilih halaman dari menu navigasi di sebelah kiri.**
        """
    )


    st.markdown(
        """
        ---
    """)

    # Menampilkan jumlah total data
    with st.container():
        query_total = """
        SELECT COUNT(*) AS total_data
        FROM (
            SELECT no_laporan FROM laporan
            UNION ALL
            SELECT no_laporan FROM tiket_dinas
            UNION ALL
            SELECT no_laporan FROM log_dinas
        ) AS all_data;
    """

        query_status = """
        SELECT status, COUNT(*) AS jumlah FROM (
            SELECT status FROM laporan
            UNION ALL
            SELECT status FROM tiket_dinas
            UNION ALL
            SELECT status FROM log_dinas
        ) AS all_status
        GROUP BY status;
    """

        df_total = fetch_data_from_db(query_total)
        df_status = fetch_data_from_db(query_status)

        # Membuat layout menggunakan Streamlit
    if not df_total.empty and not df_status.empty:
        total_data = df_total['total_data'].iloc[0]
        selesai = df_status[df_status['status'] == 'Selesai']['jumlah'].sum() if 'Selesai' in df_status['status'].values else 0
    
    # Container untuk Total Data & Selesai
    st.markdown('<div class="container">', unsafe_allow_html=True)
    col0, col00 = st.columns(2)
    with col0:
        st.metric(label="Total Data", value=total_data)
    with col00:
        st.metric(label="Selesai", value=selesai)
    st.markdown('</div>', unsafe_allow_html=True)

    # Menambahkan visualisasi total laporan, tiket dinas, dan log dinas
    with st.container():
        query_total_laporan = "SELECT COUNT(*) AS total_laporan FROM laporan"
        query_total_tiket = "SELECT COUNT(*) AS total_tiket FROM tiket_dinas"
        query_total_log = "SELECT COUNT(*) AS total_log FROM log_dinas"

        df_total_laporan = fetch_data_from_db(query_total_laporan)
        df_total_tiket = fetch_data_from_db(query_total_tiket)
        df_total_log = fetch_data_from_db(query_total_log)

        if not df_total_laporan.empty and not df_total_tiket.empty and not df_total_log.empty:
            total_laporan = df_total_laporan['total_laporan'].iloc[0]
            total_tiket = df_total_tiket['total_tiket'].iloc[0]
            total_log = df_total_log['total_log'].iloc[0]

            # Container untuk Total Laporan, Tiket, dan Log Dinas
            st.markdown('<div class="container">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Laporan", value=total_laporan)
            with col2:
                st.metric(label="Total Tiket Dinas", value=total_tiket)
            with col3:
                st.metric(label="Total Log Dinas", value=total_log)
            st.markdown('</div>', unsafe_allow_html=True)

            # Membuat dua kolom untuk visualisasi pertama
            col1, col2 = st.columns(2)

            with col1:
                query_laporan = "SELECT status FROM laporan"
                df_laporan = fetch_data_from_db(query_laporan)
                if not df_laporan.empty:
                    fig_pie_laporan = px.pie(df_laporan, names='status', title='Distribusi Status Laporan')
                    st.plotly_chart(fig_pie_laporan)

            with col2:
                query_tiket_dinas = "SELECT status FROM tiket_dinas"
                df_tiket_dinas = fetch_data_from_db(query_tiket_dinas)
                if not df_tiket_dinas.empty:
                    fig_pie_tiket = px.pie(df_tiket_dinas, names='status', title='Distribusi Status Tiket Dinas')
                    st.plotly_chart(fig_pie_tiket)

            # Membuat dua kolom untuk visualisasi kedua
            col3, col4 = st.columns(2)

            with col3:
                query_log_dinas = "SELECT status FROM log_dinas"
                df_log_dinas = fetch_data_from_db(query_log_dinas)
                if not df_log_dinas.empty:
                    fig_pie_log = px.pie(df_log_dinas, names='status', title='Distribusi Status Log Dinas')
                    st.plotly_chart(fig_pie_log)

            with st.container():
                query_bulanan = """
                    SELECT 
                        TO_CHAR(DATE_TRUNC('month', waktu_lapor::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah
                    FROM laporan
                    GROUP BY DATE_TRUNC('month', waktu_lapor::TIMESTAMP)
                    UNION ALL
                    SELECT 
                        TO_CHAR(DATE_TRUNC('month', tiket_dibuat::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah
                    FROM tiket_dinas
                    GROUP BY DATE_TRUNC('month', tiket_dibuat::TIMESTAMP)
                    UNION ALL
                    SELECT 
                        TO_CHAR(DATE_TRUNC('month', waktu_proses::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah
                    FROM log_dinas
                    GROUP BY DATE_TRUNC('month', waktu_proses::TIMESTAMP);
                """
                df_bulanan = fetch_data_from_db(query_bulanan)
                if not df_bulanan.empty:
                    df_bulanan['bulan'] = pd.to_datetime(df_bulanan['bulan'], format='%Y-%m')
                    df_bulanan = df_bulanan.sort_values(by='bulan')

                    fig_bulanan = px.bar(df_bulanan, x='bulan', y='jumlah', 
                                         title='Jumlah Data Masuk Tiap Bulan',
                                         labels={'bulan': 'Bulan', 'jumlah': 'Jumlah Data'})
                    st.plotly_chart(fig_bulanan)

            # Visualisasi distribusi status laporan, tiket dinas, dan log dinas dalam satu grafik
            with st.container():
                query_combined_status = """
                SELECT 'Laporan' AS jenis, status, COUNT(*) AS jumlah FROM laporan GROUP BY status
                UNION ALL
                SELECT 'Tiket Dinas', status, COUNT(*) AS jumlah FROM tiket_dinas GROUP BY status
                UNION ALL
                SELECT 'Log Dinas', status, COUNT(*) AS jumlah FROM log_dinas GROUP BY status;
                """
                df_combined_status = fetch_data_from_db(query_combined_status)
                if not df_combined_status.empty:
                    fig_combined_pie = px.pie(df_combined_status, names='status', values='jumlah', color='jenis', 
                                              title='Distribusi Status Laporan, Tiket Dinas, dan Log Dinas')
                    st.plotly_chart(fig_combined_pie)

            # Grafik tren perkembangan data laporan, tiket dinas, dan log dinas per bulan
            with st.container():
                query_trend = """
                SELECT TO_CHAR(DATE_TRUNC('month', waktu_lapor::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah 
                FROM laporan GROUP BY DATE_TRUNC('month', waktu_lapor::TIMESTAMP)
                UNION ALL
                SELECT TO_CHAR(DATE_TRUNC('month', tiket_dibuat::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah 
                FROM tiket_dinas GROUP BY DATE_TRUNC('month', tiket_dibuat::TIMESTAMP)
                UNION ALL
                SELECT TO_CHAR(DATE_TRUNC('month', waktu_proses::TIMESTAMP), 'YYYY-MM') AS bulan, COUNT(*) AS jumlah 
                FROM log_dinas GROUP BY DATE_TRUNC('month', waktu_proses::TIMESTAMP)
                """
                df_trend = fetch_data_from_db(query_trend)
                if not df_trend.empty:
                    df_trend['bulan'] = pd.to_datetime(df_trend['bulan'], format='%Y-%m')
                    df_trend = df_trend.sort_values(by='bulan')

                    fig_trend = px.line(df_trend, x='bulan', y='jumlah', color='bulan', 
                                        title='Tren Jumlah Data Laporan, Tiket Dinas, dan Log Dinas per Bulan',
                                        labels={'bulan': 'Bulan', 'jumlah': 'Jumlah Data'})
                    st.plotly_chart(fig_trend)

            # Filter rentang waktu untuk kategori dan tipe laporan
            st.subheader("Pilih Rentang Waktu")
            waktu_option = st.radio("Pilih rentang waktu:", ["Tahun", "Rentang Waktu"])

            if waktu_option == "Tahun":
                tahun = st.selectbox("Pilih Tahun", pd.date_range("2022-11-01", "2025-01-31", freq='Y').strftime('%Y').tolist())
                query_kategori = f"""
                    SELECT kategori, COUNT(*) AS jumlah 
                    FROM laporan
                    WHERE TO_CHAR(waktu_lapor::DATE, 'YYYY') = '{tahun}'
                    AND kategori != '-'
                    GROUP BY kategori
                    ORDER BY jumlah DESC
                    LIMIT 10;
                """
                query_tipe_laporan = f"""
                    SELECT tipe_laporan, COUNT(*) AS jumlah 
                    FROM laporan
                    WHERE TO_CHAR(waktu_lapor::DATE, 'YYYY') = '{tahun}'
                    AND tipe_laporan != '-'
                    GROUP BY tipe_laporan
                    ORDER BY jumlah DESC
                    LIMIT 10;
                """
            else:
                start_date = st.date_input("Pilih Rentang Tanggal Mulai", value=pd.to_datetime("2022-11-01"))
                end_date = st.date_input("Pilih Rentang Tanggal Akhir", value=pd.to_datetime("2023-12-31"))
                query_kategori = f"""
                    SELECT kategori, COUNT(*) AS jumlah 
                    FROM laporan
                    WHERE waktu_lapor BETWEEN '{start_date}' AND '{end_date}'
                    AND kategori != '-'
                    GROUP BY kategori
                    ORDER BY jumlah DESC
                    LIMIT 10;
                """
                query_tipe_laporan = f"""
                    SELECT tipe_laporan, COUNT(*) AS jumlah 
                    FROM laporan
                    WHERE waktu_lapor BETWEEN '{start_date}' AND '{end_date}'
                    AND tipe_laporan != '-'
                    GROUP BY tipe_laporan
                    ORDER BY jumlah DESC
                    LIMIT 10;
                """

            # Mengambil data dan menampilkan grafik kategori
            df_kategori = fetch_data_from_db(query_kategori)
            if not df_kategori.empty:
                fig_kategori = px.pie(df_kategori, names='kategori', values='jumlah', title='Top 10 Kategori Kejadian')
                st.plotly_chart(fig_kategori)

            # Mengambil data dan menampilkan grafik tipe laporan
            df_tipe_laporan = fetch_data_from_db(query_tipe_laporan)
            if not df_tipe_laporan.empty:
                fig_tipe_laporan = px.pie(df_tipe_laporan, names='tipe_laporan', values='jumlah', title='Top 10 Tipe Laporan')
                st.plotly_chart(fig_tipe_laporan)

        else:
            st.warning("Tidak ada data yang tersedia.")


elif options == "Unggah Data":
    st.title("📁 Unggah dan Simpan Data")
    table_choice = st.selectbox("Pilih tabel untuk mengimpor data:", ['laporan', 'tiket_dinas', 'log_dinas'])
    uploaded_file = st.file_uploader("Pilih file CSV", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write("Data yang diunggah:")
        st.dataframe(df.head())

        if st.button("Masukkan ke Database"):
            insert_csv_to_db(df, table_choice)

elif options == "Statistik":
    st.title("📑 Statistik Data")
    statistik_table = st.selectbox("Pilih tabel untuk dianalisis:", ['laporan', 'tiket_dinas', 'log_dinas'])
    
    if statistik_table == 'laporan':
        query = "SELECT * FROM laporan"
        status_options = ['baru', 'proses', 'selesai']
        time_column = 'waktu_lapor'
    elif statistik_table == 'tiket_dinas':
        query = "SELECT * FROM tiket_dinas"
        status_options = ['aktif', 'dikerjakan', 'selesai']
        time_column = 'tiket_dibuat'
    elif statistik_table == 'log_dinas':
        query = "SELECT * FROM log_dinas"
        status_options = ['aktif', 'dikerjakan', 'verivikasi l2', 'selesai', 'selesai tanpa eskalasi', 
                          'perbaharuan laporan', 'transfer tiket']
        time_column = 'waktu_proses'
 
    # Ambil data dari database
    df_statistik = fetch_data_from_db(query)
    if not df_statistik.empty:
        df_statistik['status'] = df_statistik['status'].str.strip().str.lower()

        # Filter berdasarkan status
        selected_status = st.multiselect("Pilih Status:", status_options)
        if selected_status:
            df_statistik = df_statistik[df_statistik['status'].isin(selected_status)]

        # Filter berdasarkan rentang waktu
        date_range = st.date_input(
            "Pilih Rentang Waktu:", 
            value=(pd.to_datetime("2022-11-01"), pd.to_datetime("2023-01-31"))
        )

        # Validasi apakah pengguna memilih rentang waktu
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = None, None

        if start_date and end_date:
            # Pastikan start_date dan end_date adalah objek datetime
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)

            # Opsi: Menghapus komponen waktu dari kolom datetime jika hanya membandingkan tanggal
            df_statistik[time_column] = pd.to_datetime(df_statistik[time_column]).dt.normalize()  # Hapus komponen waktu

            # Filter berdasarkan rentang waktu
            df_statistik = df_statistik[(df_statistik[time_column] >= start_date) & (df_statistik[time_column] <= end_date)]
        
        # Tampilkan data
        st.write("Data Terkini:")
        st.dataframe(df_statistik)

        # Statistik dan visualisasi
        generate_statistics(df_statistik, statistik_table)
        generate_visualizations(df_statistik, statistik_table)

        # Analisis Tren Waktu
        if time_column in df_statistik.columns:
            trend_data = df_statistik.copy()
            trend_data[time_column] = pd.to_datetime(trend_data[time_column]).dt.date
            trend_group = trend_data.groupby(time_column).size().reset_index(name='jumlah')

            # Line chart dengan Plotly
            fig_trend = px.line(trend_group, x=time_column, y='jumlah', title='Tren Jumlah Data dari Waktu ke Waktu')
            st.plotly_chart(fig_trend)

        # Ekspor data
        if st.button("Ekspor Data ke CSV"):
            csv = df_statistik.to_csv(index=False).encode('utf-8')
            st.download_button("Unduh CSV", data=csv, file_name=f"{statistik_table}_data.csv", mime="text/csv")
    else:
        st.warning("Tidak ada data yang tersedia untuk tabel ini.")

# Fitur Pencarian Data
elif options == "Pencarian Data":
    st.title("🔍 Pencarian Data")

    # Input rentang waktu dan kata kunci
    start_date = st.date_input("Pilih Tanggal Mulai", value=datetime(2022, 12, 1))
    end_date = st.date_input("Pilih Tanggal Akhir", value=datetime(2023, 12, 31))
    search_input = st.text_input("Masukkan kata kunci pencarian (No Laporan, No Telp, Kecamatan, Kelurahan, Dinas, dll):")

    if st.button("Cari"):
        # Query SQL untuk pencarian data
        query = f"""
        SELECT DISTINCT
            l.no_laporan, l.no_telp, l.uid, l.tipe_laporan, l.kecamatan, l.kelurahan, l.status AS status_laporan,
            l.waktu_lapor, l.pelapor, l.kategori, l.sub_kategori_1, l.sub_kategori_2, l.lokasi_kejadian,
            t.no_tiket_dinas, t.dinas, t.status AS status_tiket, t.tiket_dibuat, t.tiket_selesai, 
            g.no_tiket_dinas AS log_no_tiket, g.dinas AS log_dinas, g.status AS status_log, g.waktu_proses, g.catatan
        FROM 
            laporan l
        LEFT JOIN 
            tiket_dinas t ON l.no_laporan = t.no_laporan
        LEFT JOIN 
            log_dinas g ON l.no_laporan = g.no_laporan
        WHERE 
            (l.no_laporan ILIKE '%{search_input}%' OR
            l.no_telp ILIKE '%{search_input}%' OR
            l.kecamatan ILIKE '%{search_input}%' OR
            l.kelurahan ILIKE '%{search_input}%' OR
            l.pelapor ILIKE '%{search_input}%' OR
            l.kategori ILIKE '%{search_input}%' OR
            l.sub_kategori_1 ILIKE '%{search_input}%' OR
            l.sub_kategori_2 ILIKE '%{search_input}%' OR
            l.lokasi_kejadian ILIKE '%{search_input}%' OR
            t.no_tiket_dinas ILIKE '%{search_input}%' OR
            t.dinas ILIKE '%{search_input}%' OR
            g.dinas ILIKE '%{search_input}%' OR
            g.catatan ILIKE '%{search_input}%') AND
            ((l.waktu_lapor BETWEEN '{start_date}' AND '{end_date}') OR
            (t.tiket_dibuat BETWEEN '{start_date}' AND '{end_date}') OR
            (t.tiket_selesai BETWEEN '{start_date}' AND '{end_date}') OR
            (g.waktu_proses BETWEEN '{start_date}' AND '{end_date}'))
        ORDER BY 
            l.waktu_lapor DESC, g.waktu_proses DESC, t.tiket_selesai DESC
        """

        # Ambil data dari database
        df_result = fetch_data_from_db(query)

        if not df_result.empty:
            # Gantikan nilai None dengan tanda "-"
            df_result = df_result.fillna('-')

            def get_latest_status(row):
                # Ambil tanggal terbaru dari waktu_lapor, tiket_selesai, dan waktu_proses
                dates = [
                    row['waktu_lapor'], 
                    row['waktu_proses'], 
                    row['tiket_selesai']
                ]
                
                # Tentukan tanggal terbaru yang valid
                valid_dates = [d for d in dates if isinstance(d, datetime)]  # Pastikan tanggal valid
                latest_date = max(valid_dates) if valid_dates else None

                # Tentukan status berdasarkan tanggal terbaru
                if latest_date:
                    # Jika tanggal lebih besar dari 31 Desember 2023, statusnya "Selesai"
                    if latest_date > datetime(2023, 12, 31):
                        return 'Selesai'
                    # Jika lebih besar dari 1 Januari 2023, statusnya "Proses"
                    elif latest_date >= datetime(2023, 1, 1):
                        return 'Proses'
                return row['status_laporan']  # Jika tidak ada perubahan, tetap status lama

            # Terapkan logika status pada DataFrame
            df_result['status_laporan'] = df_result.apply(get_latest_status, axis=1)

            def convert_to_datetime(value):
                """Mengonversi nilai menjadi datetime jika belum dalam format datetime."""
                if isinstance(value, str):
                    try:
                        # Coba konversi string ke datetime dengan format yang umum
                        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        return None
                elif isinstance(value, pd.Timestamp):
                    return value.to_pydatetime()
                return value

            def calculate_duration(row):
                """Menghitung durasi antara waktu_lapor dan tiket_selesai."""
                # Konversi ke datetime terlebih dahulu
                waktu_lapor = convert_to_datetime(row['waktu_lapor'])
                tiket_selesai = convert_to_datetime(row['tiket_selesai'])
                
                # Jika kedua waktu ada, hitung durasinya
                if waktu_lapor and tiket_selesai:
                    duration = tiket_selesai - waktu_lapor
                    return duration
                return None  # Jika salah satu kosong, kembalikan None

            # Terapkan fungsi untuk menghitung durasi pada DataFrame
            df_result['durasi'] = df_result.apply(calculate_duration, axis=1)

            # Menambahkan format untuk durasi (jika durasi ada)
            df_result['durasi'] = df_result['durasi'].apply(lambda x: str(x) if x is not None else '-')

            # Hapus duplikat berdasarkan kolom-kolom penting (misal: no_laporan atau no_tiket_dinas)
            df_result = df_result.drop_duplicates(subset=["no_laporan", "no_tiket_dinas"])

            # Tampilkan hasil
            st.write("Hasil Pencarian:")
            st.dataframe(df_result)
        else:
            st.warning(f"Tidak ditemukan data untuk kata kunci: {search_input} dengan rentang waktu {start_date} hingga {end_date}")


