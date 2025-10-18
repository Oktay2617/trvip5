import re
import sys
import time
from urllib.parse import urlparse, parse_qs, urljoin
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# Justin TV ana domain'i
JUSTINTV_DOMAIN = "https://tvjustin.com/"

# Kullanılacak User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# --- Varsayılan Kanal Bilgisini Alma Fonksiyonu ---
def scrape_default_channel_info(page):
    """
    Justin TV ana sayfasını ziyaret eder ve varsayılan iframe'den
    event URL'sini ve stream ID'sini alır.
    """
    print(f"\n📡 Varsayılan kanal bilgisi {JUSTINTV_DOMAIN} adresinden alınıyor...")
    try:
        # Ana sayfaya ilk gidiş. DOM'un yüklenmesini bekle.
        page.goto(JUSTINTV_DOMAIN, timeout=25000, wait_until='domcontentloaded') # cite: tvjustin.py

        iframe_selector = "iframe#customIframe" # cite: tvjustin.py
        print(f"-> Varsayılan iframe ('{iframe_selector}') aranıyor...")
        page.wait_for_selector(iframe_selector, timeout=15000) # cite: tvjustin.py
        iframe_element = page.query_selector(iframe_selector) # cite: tvjustin.py

        if not iframe_element:
            print("❌ Ana sayfada 'iframe#customIframe' bulunamadı.")
            return None, None

        iframe_src = iframe_element.get_attribute('src') # cite: tvjustin.py
        if not iframe_src:
            print("❌ Iframe 'src' özniteliği boş.")
            return None, None

        # event3.html veya event.html URL'sini oluştur
        event_url = urljoin(JUSTINTV_DOMAIN, iframe_src) # cite: tvjustin.py
        parsed_event_url = urlparse(event_url) # cite: tvjustin.py
        query_params = parse_qs(parsed_event_url.query) # cite: tvjustin.py
        stream_id = query_params.get('id', [None])[0] # cite: tvjustin.py

        if not stream_id:
            print(f"❌ Event URL'sinde ({event_url}) 'id' parametresi bulunamadı.")
            return None, None

        print(f"✅ Varsayılan kanal bilgisi alındı: ID='{stream_id}', EventURL='{event_url}'")
        return event_url, stream_id

    except Exception as e:
        print(f"❌ Ana sayfaya ulaşılamadı veya iframe bilgisi alınamadı: {e.__class__.__name__} - {e}")
        return None, None

# --- M3U8 Base URL Çıkarma Fonksiyonu ---
def extract_base_m3u8_url(page, event_url):
    """
    Verilen event URL'sine gider ve JavaScript içeriğinden base URL'i çıkarır.
    """
    try:
        print(f"\n-> M3U8 Base URL'i almak için Event sayfasına gidiliyor: {event_url}")
        page.goto(event_url, timeout=20000, wait_until="domcontentloaded") # cite: tvjustin.py
        content = page.content() # cite: tvjustin.py
        # Regex ile '/checklist/' ile biten URL'yi ara
        base_url_match = re.search(r"['\"](https?://[^'\"]+/checklist/)['\"]", content) # cite: tvjustin.py
        if not base_url_match:
             base_url_match = re.search(r"streamUrl\s*=\s*['\"](https?://[^'\"]+/checklist/)['\"]", content) # cite: tvjustin.py
        if not base_url_match:
            print(" -> ❌ Event sayfası kaynağında '/checklist/' ile biten base URL bulunamadı.")
            return None
        base_url = base_url_match.group(1) # cite: tvjustin.py
        print(f"-> ✅ M3U8 Base URL bulundu: {base_url}")
        return base_url
    except Exception as e:
        print(f"-> ❌ Event sayfası işlenirken hata oluştu: {e}")
        return None

# --- Tüm Kanal Listesini Kazıma Fonksiyonu (FİLTRESİZ) ---
def scrape_all_channels(page):
    """
    Justin TV ana sayfasında (zaten açık olduğu varsayılarak) JS'in
    listeyi doldurmasını bekler ve TÜM kanalların isimlerini ve ID'lerini
    (yinelenenler dahil) kazır.
    """
    print(f"\n📡 Tüm kanallar {JUSTINTV_DOMAIN} adresinden çekiliyor...")
    channels = [] # Sonuç listesi
    try:
        # GOTO YOK - Sayfa zaten açık varsayılıyor
        print("-> DOM güncellemeleri için 5 saniye bekleniyor...")
        page.wait_for_timeout(5000) # cite: tvjustin.py

        mac_item_selector = ".mac[data-url]" # cite: tvjustin.py
        print(f"-> Sayfa içinde '{mac_item_selector}' elementleri var mı kontrol ediliyor...")

        # JS ile elementlerin varlığını kontrol et
        elements_exist = page.evaluate(f'''() => {{ # cite: tvjustin.py
            const container = document.querySelector('.macListe#hepsi');
            if (!container) return false;
            return container.querySelector('{mac_item_selector}') !== null;
        }}''')

        if not elements_exist:
            print(f"❌ Sayfa içinde '{mac_item_selector}' elemanları bulunamadı (JS değerlendirmesi başarısız).")
            return []

        print("-> ✅ Kanallar sayfada mevcut. Bilgiler çıkarılıyor...")
        channel_elements = page.query_selector_all(".macListe#hepsi .mac[data-url]") # cite: tvjustin.py
        print(f"-> {len(channel_elements)} adet potansiyel kanal elemanı bulundu.")

        for element in channel_elements:
            name_element = element.query_selector(".takimlar") # cite: tvjustin.py
            channel_name = name_element.inner_text().strip() if name_element else "İsimsiz Kanal" # cite: tvjustin.py
            channel_name_clean = channel_name.replace('CANLI', '').strip() # cite: tvjustin.py

            data_url = element.get_attribute('data-url') # cite: tvjustin.py
            stream_id = None
            if data_url:
                try:
                    parsed_data_url = urlparse(data_url) # cite: tvjustin.py
                    query_params = parse_qs(parsed_data_url.query) # cite: tvjustin.py
                    stream_id = query_params.get('id', [None])[0] # cite: tvjustin.py
                except Exception:
                    pass

            if stream_id: # Sadece ID varsa ekle
                time_element = element.query_selector(".saat") # cite: tvjustin.py
                time_str = time_element.inner_text().strip() if time_element else None # cite: tvjustin.py
                if time_str and time_str != "CANLI": # cite: tvjustin.py
                     final_channel_name = f"{channel_name_clean} ({time_str})" # cite: tvjustin.py
                else:
                     final_channel_name = channel_name_clean # cite: tvjustin.py

                # Direkt listeye ekle, filtreleme yok
                channels.append({ # cite: tvjustin.py
                    'name': final_channel_name,
                    'id': stream_id
                })

        print(f"✅ {len(channels)} adet ham kanal bilgisi başarıyla çıkarıldı.")
        return channels

    except Exception as e:
        print(f"❌ Kanal listesi işlenirken hata oluştu: {e}")
        return []

# --- Gruplama Fonksiyonu ---
def get_channel_group(channel_name):
    channel_name_lower = channel_name.lower() # cite: tvjustin.py
    group_mappings = { # cite: tvjustin.py
        'BeinSports': ['bein sports', 'beın sports', ' bs', ' bein '],
        'S Sports': ['s sport'],
        'Tivibu': ['tivibu spor', 'tivibu'],
        'Exxen': ['exxen'],
        'Ulusal Kanallar': ['a spor', 'trt spor', 'trt 1', 'tv8', 'atv', 'kanal d', 'show tv', 'star tv', 'trt yıldız', 'a2'],
        'Spor': ['smart spor', 'nba tv', 'eurosport', 'sport tv', 'premier sports', 'ht spor', 'sports tv', 'd smart', 'd-smart'],
        'Yarış': ['tjk tv'],
        'Belgesel': ['national geographic', 'nat geo', 'discovery', 'dmax', 'bbc earth', 'history'],
        'Film & Dizi': ['bein series', 'bein movies', 'movie smart', 'filmbox', 'sinema tv'],
        'Haber': ['haber', 'cnn', 'ntv'],
        'Diğer': ['gs tv', 'fb tv', 'cbc sport']
    }
    for group, keywords in group_mappings.items(): # cite: tvjustin.py
        for keyword in keywords:
            if keyword in channel_name_lower:
                return group
    # Maçları ayırmak için kontrol
    if re.search(r'\(\d{2}:\d{2}\)', channel_name): return "Maç Yayınları" # cite: tvjustin.py (Saat formatı eklendi)
    if ' - ' in channel_name: return "Maç Yayınları" # cite: tvjustin.py
    return "Diğer Kanallar" # cite: tvjustin.py

# --- Ana Fonksiyon (İSME GÖRE FİLTRELEME İLE) ---
def main():
    with sync_playwright() as p:
        print("🚀 Playwright ile Justin TV M3U8 Kanal İndirici Başlatılıyor (Tüm Liste)...")

        browser = p.chromium.launch(headless=True) # cite: tvjustin.py
        context = browser.new_context(user_agent=USER_AGENT) # cite: tvjustin.py
        page = context.new_page() # cite: tvjustin.py

        # 1. Adım: Varsayılan kanaldan event URL'sini al (Base URL için)
        default_event_url, default_stream_id = scrape_default_channel_info(page) # cite: tvjustin.py
        if not default_event_url:
            print("❌ UYARI: Varsayılan kanal bilgisi alınamadı, M3U8 Base URL bulunamıyor. İşlem sonlandırılıyor.")
            browser.close()
            sys.exit(1)

        # 2. Adım: event URL'den M3U8 Base URL'ini çıkar
        base_m3u8_url = extract_base_m3u8_url(page, default_event_url) # cite: tvjustin.py
        if not base_m3u8_url:
            print("❌ UYARI: M3U8 Base URL alınamadı. İşlem sonlandırılıyor.")
            browser.close()
            sys.exit(1)

        # 3. Adım: Ana sayfadaki TÜM kanalları kazı (yinelenenler dahil)
        scraped_channels = scrape_all_channels(page) # Ham liste # cite: tvjustin.py
        if not scraped_channels:
            print("❌ UYARI: Hiçbir kanal bulunamadı, işlem sonlandırılıyor.")
            browser.close()
            sys.exit(1)

        # --- YENİ ADIM: KAZIMA SONRASI İSME GÖRE FİLTRELEME (İLK BULUNAN KALIR) ---
        print(f"\n-> {len(scraped_channels)} adet ham kanal bulundu. İsimlere göre tekilleştiriliyor (ilk bulunan kalacak)...")
        filtered_channels = [] # Sonuçların tutulacağı liste # cite: tvjustin.py
        seen_names = set()     # Hangi isimleri gördüğümüzü takip etmek için set # cite: tvjustin.py
        for channel_info in scraped_channels: # cite: tvjustin.py
            channel_name = channel_info['name'] # cite: tvjustin.py
            # Eğer bu isim DAHA ÖNCE eklenmediyse listeye ekle
            if channel_name not in seen_names: # cite: tvjustin.py
                filtered_channels.append(channel_info) # cite: tvjustin.py
                seen_names.add(channel_name) # cite: tvjustin.py
        print(f"-> Tekilleştirme sonrası {len(filtered_channels)} adet kanal kaldı.")
        # --- FİLTRELEME BİTTİ ---

        m3u_content = []
        output_filename = "justintv_kanallar.m3u8" # cite: tvjustin.py
        print(f"\n📺 {len(filtered_channels)} kanal için M3U8 linkleri oluşturuluyor...")
        created = 0

        player_origin_host = JUSTINTV_DOMAIN.rstrip('/') # cite: tvjustin.py
        player_referer = JUSTINTV_DOMAIN # cite: tvjustin.py

        m3u_header_lines = [ # cite: tvjustin.py
            "#EXTM3U",
            f"#EXT-X-USER-AGENT:{USER_AGENT}",
            f"#EXT-X-REFERER:{player_referer}",
            f"#EXT-X-ORIGIN:{player_origin_host}"
        ]

        # Filtrelenmiş liste üzerinde döngü kur
        for i, channel_info in enumerate(filtered_channels, 1): # cite: tvjustin.py
            channel_name = channel_info['name'] # cite: tvjustin.py
            stream_id = channel_info['id'] # cite: tvjustin.py
            group_name = get_channel_group(channel_name) # cite: tvjustin.py

            m3u8_link = f"{base_m3u8_url}{stream_id}.m3u8" # cite: tvjustin.py

            m3u_content.append(f'#EXTINF:-1 tvg-name="{channel_name}" group-title="{group_name}",{channel_name}') # cite: tvjustin.py
            m3u_content.append(m3u8_link) # cite: tvjustin.py
            created += 1

        browser.close() # cite: tvjustin.py

        if created > 0:
            with open(output_filename, "w", encoding="utf-8") as f: # cite: tvjustin.py
                f.write("\n".join(m3u_header_lines)) # cite: tvjustin.py
                f.write("\n")
                f.write("\n".join(m3u_content)) # cite: tvjustin.py
            print(f"\n\n📂 {created} kanal başarıyla '{output_filename}' dosyasına kaydedildi.")
        else:
            print("\n\nℹ️  Geçerli hiçbir M3U8 linki oluşturulamadığı için dosya oluşturulmadı.")

        print("\n🎉 İşlem tamamlandı!")

if __name__ == "__main__":
    main() # cite: tvjustin.py
