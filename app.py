import streamlit as st
import pandas as pd
import joblib
import time
import google.generativeai as genai
from pytrends.request import TrendReq
from supabase import create_client, Client
from apify_client import ApifyClient

# --- 1. KONFIGURASI API (MENGAMBIL DARI RAHASIA / SECRETS) ---
# Saat deploy, kita simpan kunci di "Brankas" Streamlit, bukan di kodingan.

try:
    # Cek apakah dijalankan di Streamlit Cloud (Online)
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    APIFY_TOKEN = st.secrets["APIFY_TOKEN"]
except:
    # Fallback kalau dijalankan di Laptop sendiri (Localhost)
    # Ganti string di bawah ini dengan kunci aslimu saat testing lokal
    GOOGLE_API_KEY = "AIzaSyCo6E7xRCqTxkHDDbW17KS4g8Dbx3tYBHs"
    SUPABASE_URL = "https://ezezvswkhsmntnljzheb.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV6ZXp2c3draHNtbnRubGp6aGViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzExMzg1NDQsImV4cCI6MjA4NjcxNDU0NH0.r5eEwu2zIEN1zFKaLaaozVaNEX-M1rUETD2RXzO3o-Y"
    APIFY_TOKEN = "apify_api_qaoOFp0yb3VycnwOWOiWVvZScVh98Z2Ux26p"

# Setup Koneksi
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    apify_client = ApifyClient(APIFY_TOKEN)
except Exception as e:
    st.error(f"Error Konfigurasi Awal: {e}")

# --- 2. FUNGSI LOGIKA INTELEJENSI ---

def load_brain():
    """Memuat Model ML & Insight Pasar dari file .pkl"""
    try:
        model = joblib.load('viral_model.pkl')
        insight = joblib.load('model_insight.pkl')
        return model, insight
    except FileNotFoundError:
        return None, None

def get_google_trends(keyword):
    """Mengambil Data Grafik Permintaan Pasar"""
    try:
        pytrends = TrendReq(hl='id-ID', tz=420)
        pytrends.build_payload([keyword], cat=0, timeframe='today 12-m')
        return pytrends.interest_over_time()
    except:
        return None

def scrape_and_store_realtime(hashtag, query):
    """
    Scrape Data Real-time -> Simpan Lengkap ke Supabase (Sesuai Update Trainer)
    """
    try:
        # 1. Konfigurasi Robot Scraping
        run_input = {
            "hashtags": [hashtag],
            "searchQueries": [query] if query else [],
            "resultsPerPage": 5, 
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False
        }
        
        # 2. Eksekusi Apify
        actor_call = apify_client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
        
        if not actor_call:
            return None, "Gagal memanggil Actor."
            
        dataset_items = apify_client.dataset(actor_call["defaultDatasetId"]).list_items().items
        
        if not dataset_items:
            return None, "Tidak ada data ditemukan. Coba keyword lain."

        # 3. Simpan ke Supabase (Struktur Data Lengkap)
        cleaned_data = []
        for item in dataset_items:
            # Ambil Timestamp (Waktu Upload)
            created_at = item.get('createTimeISO', None)
            
            row = {
                # Identitas
                "niche": hashtag,
                "hashtag": hashtag,
                "author_name": item.get('authorMeta', {}).get('name', 'Unknown'),
                "video_url": item.get('webVideoUrl', ''),
                "desc_text": item.get('text', '')[:500],
                
                # Metrik Engagement (Penting untuk Trainer masa depan)
                "play_count": item.get('playCount', 0),
                "digg_count": item.get('diggCount', 0),
                "share_count": item.get('shareCount', 0),   # Baru
                "comment_count": item.get('commentCount', 0), # Baru
                "collect_count": item.get('collectCount', 0), # Baru
                
                # Metadata Teknis (Fitur ML)
                "duration": item.get('videoMeta', {}).get('duration', 0),
                "music_name": item.get('musicMeta', {}).get('musicName', 'Original'),
                "created_time": created_at
            }
            
            # Fire & Forget Insert (Agar app tidak lemot nunggu database)
            try:
                supabase.table("tiktok_trends").insert(row).execute() 
            except:
                pass 
            
            # Siapkan data untuk ditampilkan di tabel app
            cleaned_data.append(row)
            
        return cleaned_data, "Sukses"
        
    except Exception as e:
        return None, str(e)

def generate_creative_content(data):
    """AI Generative Modul A"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Bertindaklah sebagai Senior Content Strategist. Buatkan konten plan TikTok.
        
        DATA:
        - Topik: {data['topik']} | Platform: {data['platform']} | Audiens: {data['audiens']}
        - Tujuan: {data['objective']} | Tone: {data['tone']} | Pain Point: {data['pain_point']}
        - Format: {data['format']} | Hook: {data['hook']} | CTA: {data['cta']}
        
        OUTPUT:
        Buatkan Script Lengkap (Scene by Scene) dan Caption.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error AI: {str(e)}"

# --- 3. FRONTEND UI ---
st.set_page_config(page_title="Command Center Pro", layout="wide")

# Load Otak ML
ml_model, ml_insight = load_brain()
# Tambahkan ini di app.py bagian sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055666.png", width=50) # Ikon Roket
    st.title("🚀 Viral Engine")
    
    # --- VISUAL SAAS (GIMMICK) ---
    st.markdown("---")
    st.caption("👤 **User Status:**")
    st.info("💎 Plan: **SILVER TIER**")
    
    # Progress Bar Kuota (Biar kelihatan kayak SaaS beneran)
    st.progress(45, text="⚡ Kuota API: 45/200")
    
    if st.button("Upgrade Plan 👑"):
        st.toast("Fitur pembayaran belum tersedia di mode demo!", icon="💳")
    
    st.markdown("---")
    
    mode = st.radio("Pilih Modul:", ["🅰️ Model A: AI Creator", "🅱️ Model B: Real-Time Intelligence"])
    
    st.markdown("---")
    if ml_model:
        st.success("✅ ML Brain: Online")
    else:
        st.error("❌ ML Brain: Offline")
        st.caption("Jalankan 'trainer.py' dulu!")

# ==========================================
# MODUL A: CREATIVE STUDIO (AI)
# ==========================================
if mode == "🅰️ Model A: AI Creator":
    st.header("🅰️ AI Content Strategist")
    st.caption("Generate ide konten berkualitas berdasarkan parameter psikologis.")
    
    with st.form("form_a"):
        col1, col2 = st.columns(2)
        with col1:
            topik = st.text_input("Topik Utama", placeholder="Contoh: Review Laptop Gaming")
            audiens = st.text_input("Target Audiens", placeholder="Mahasiswa Teknik, Gamers")
            platform = st.selectbox("Platform", ["TikTok", "Instagram Reels", "YouTube Shorts"])
        with col2:
            objective = st.selectbox("Tujuan", ["Viral/Awareness", "Edukasi/Trust", "Sales/Konversi"])
            tone = st.selectbox("Tone", ["Santai/Bestie", "Profesional", "Lucu/Sarkas"])
            pain_point = st.text_input("Masalah Audiens", placeholder="Laptop lemot, budget tipis")
            
        col3, col4, col5 = st.columns(3)
        with col3: format_konten = st.selectbox("Format", ["Video Pendek", "Carousel", "Storytelling"])
        with col4: hook_style = st.selectbox("Hook", ["Pertanyaan", "Fakta Mengejutkan", "Rahasia"])
        with col5: cta = st.text_input("CTA(Untuk penonton melakukan aksi)", "Cek Keranjang Kuning!")
        
        submit_a = st.form_submit_button("✨ Generate Script")
        
    if submit_a:
        input_data = {
            "topik": topik, "audiens": audiens, "platform": platform, 
            "objective": objective, "tone": tone, "pain_point": pain_point,
            "format": format_konten, "hook": hook_style, "cta": cta
        }
        with st.status("🤖 AI sedang menulis naskah...", expanded=True):
            res = generate_creative_content(input_data)
            st.write("Selesai!")
        st.markdown(res)

# ==========================================
# MODUL B: REAL-TIME INTELLIGENCE (ML + SCRAPING)
# ==========================================
elif mode == "🅱️ Model B: Real-Time Intelligence":
    st.header("🅱️ Hybrid Intelligence System")
    st.caption("Gabungan Data Scraping Real-time + Prediksi Machine Learning.")

    # 1. FORM DATA GATHERING
    with st.form("scraping_form"):
        st.subheader("1. Data Gathering (User Scraping)")
        c1, c2 = st.columns(2)
        with c1:
            hashtag_target = st.text_input("Target Hashtag (gausah pakai #)", "bisnis")
        with c2:
            query_target = st.text_input("Kalimat yang ingin anda cari di pencarian", "Tips bisnis 2026")
            
        st.caption("Bot akan mengambil 15 video teratas (24 jam terakhir) untuk analisis cepat.")
        tombol_scrape = st.form_submit_button("🚀 Jalankan Misi (Scrape & Save)")

    # CONTAINER UNTUK MENYIMPAN HASIL SCRAPE SEMENTARA
    if "scraped_data" not in st.session_state:
        st.session_state.scraped_data = None

    if tombol_scrape:
        if "MASUKKAN" in APIFY_TOKEN:
            st.error("API Token User belum diisi!")
        else:
            with st.status("Menjalankan Misi...", expanded=True) as status:
                st.write("📡 Menghubungi TikTok...")
                data_baru, msg = scrape_and_store_realtime(hashtag_target, query_target)
                
                if data_baru:
                    st.write("💾 Menyimpan data ke Supabase...")
                    st.session_state.scraped_data = data_baru
                    status.update(label="Sukses!", state="complete", expanded=False)
                else:
                    status.update(label="Gagal!", state="error")
                    st.error(msg)

    # 2. DASHBOARD ANALISIS
    if st.session_state.scraped_data:
        st.divider()
        st.subheader("2. Market Insight (Detik Ini)")
        
        df_new = pd.DataFrame(st.session_state.scraped_data)
        
        # Hitung statistik sederhana dari data baru
        avg_likes_now = df_new['digg_count'].mean()
        avg_dur_now = df_new['duration'].mean()
        top_music = df_new['music_name'].mode()[0] if not df_new['music_name'].empty else "-"
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        col_stat1.metric("Avg Likes (24h)", f"{int(avg_likes_now):,}")
        col_stat2.metric("Tren Durasi", f"{int(avg_dur_now)} Detik")
        col_stat3.metric("Musik Top", f"{top_music}")

        st.markdown("---")

        # 3. ML PREDICTOR SIMULATOR
        st.subheader("3. Content Simulator (ML Powered)")
        st.info("Prediksi skor viralitas videomu menggunakan 'Otak' ML + Tren Data Baru.")

        c_sim1, c_sim2 = st.columns([1, 1])
        
        with c_sim1:
            # Grafik Google Trends
            trends = get_google_trends(query_target if query_target else hashtag_target)
            if trends is not None:
                st.line_chart(trends)
                st.caption("Grafik Permintaan Pasar (Google Trends)")
            else:
                st.warning("Data Trends tidak tersedia.")

        with c_sim2:
            st.write("#### 🎚️ Parameter Videomu")
            my_dur = st.slider("Rencana Durasi", 5, 180, 15)
            my_cap = st.slider("Panjang Caption", 10, 500, 100)
            my_hash = st.slider("Jumlah Hashtag", 1, 30, 5)
            
            if st.button("🔮 Hitung Hybrid Score"):
                if ml_model:
                    # A. PREDIKSI BASE (Dari Otak ML Historis)
                    input_ml = pd.DataFrame({
                        'duration': [my_dur],
                        'caption_len': [my_cap],
                        'hashtag_count': [my_hash]
                    })
                    raw_score = ml_model.predict(input_ml)[0]
                    
                    # B. PREDIKSI KONTEKS (Dari Data Scraping Baru)
                    # Jika durasi user mirip dengan tren durasi hari ini -> Bonus Score
                    dur_diff = abs(my_dur - avg_dur_now)
                    bonus = 0
                    if dur_diff <= 5: bonus = 15 # Bonus besar kalau durasi pas
                    elif dur_diff <= 10: bonus = 5
                    
                    # C. FINAL SCORING
                    # Bandingkan raw_score dengan Benchmark Pasar (dari model_insight.pkl)
                    benchmark = ml_insight.get('avg_engagement', 100)
                    
                    # Normalisasi: Jika prediksi == benchmark, nilai 60 (Standard)
                    # Jika prediksi 2x benchmark, nilai 90-100 (Viral)
                    normalized_score = min(int((raw_score / benchmark) * 60), 85)
                    
                    final_score = min(normalized_score + bonus, 100)
                    
                    # OUTPUT
                    st.metric("Hybrid Viral Score", f"{final_score}/100")
                    st.progress(final_score)
                    
                    # SCRIPT SARAN DINAMIS
                    best_dur_hist = int(ml_insight.get('best_duration', 15))
                    
                    if final_score > 75:
                        st.success("🔥 **POTENSI VIRAL TINGGI!** Settinganmu pas dengan pola historis & tren hari ini.")
                    else:
                        st.warning("⚠️ **PERLU OPTIMASI.**")
                        st.write(f"- Data historis menyarankan durasi: **{best_dur_hist} detik**.")
                        st.write(f"- Tren hari ini rata-rata durasi: **{int(avg_dur_now)} detik**.")
                        st.write("- Coba sesuaikan durasimu mendekati angka tersebut.")
                        
                else:
                    st.error("Model Error.")
        
        # Tabel Data Mentah
        with st.expander("Lihat Data Mentah (Real-time Scraped)"):
            st.dataframe(df_new[['author_name', 'digg_count', 'share_count', 'music_name', 'desc_text']])