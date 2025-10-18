import re
import os

# --- Ayarlar ---
INPUT_FILENAME = "justintv_kanallar_raw.m3u8" # Kazıyıcının oluşturduğu dosya
OUTPUT_FILENAME = "justintv_kanallar.m3u8"  # Temizlenmiş nihai dosya
# ---------------

def extract_channel_name(extinf_line):
    """#EXTINF satırından kanal adını çıkarır."""
    # tvg-name="..." kısmını veya sondaki virgül sonrasını kullanabiliriz.
    # Sondaki virgül sonrası daha güvenilir olabilir.
    match = re.search(r",(.+)$", extinf_line)
    if match:
        return match.group(1).strip()
    else:
        # Alternatif: tvg-name'i dene
        match_tvg = re.search(r'tvg-name="([^"]+)"', extinf_line)
        if match_tvg:
            return match_tvg.group(1).strip()
    return None # İsim bulunamazsa

def clean_m3u8(input_file, output_file):
    """
    Girdi M3U8 dosyasını okur, aynı isimli kanalları tekilleştirir
    ve temizlenmiş dosyayı oluşturur.
    """
    if not os.path.exists(input_file):
        print(f"❌ Hata: Girdi dosyası '{input_file}' bulunamadı.")
        return

    print(f"🧹 '{input_file}' dosyası okunuyor ve temizleniyor...")
    
    seen_names = set()
    header_lines = []
    output_lines = []
    
    current_extinf = None

    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            for line in infile:
                line = line.strip()
                if not line: # Boş satırları atla
                    continue

                if line.startswith('#EXTM3U') or line.startswith('#EXT-X-'):
                    # Başlık satırlarını doğrudan kopyala
                    header_lines.append(line)
                    continue

                if line.startswith('#EXTINF'):
                    current_extinf = line # Bir sonraki URL için #EXTINF satırını sakla
                    continue

                if current_extinf and (line.startswith('http://') or line.startswith('https://')):
                    # URL satırına ulaştık, şimdi ismi kontrol et
                    channel_name = extract_channel_name(current_extinf)
                    
                    if channel_name:
                        # Eğer bu isim daha önce görülmediyse, ekle
                        if channel_name not in seen_names:
                            output_lines.append(current_extinf) # #EXTINF satırını ekle
                            output_lines.append(line)          # URL satırını ekle
                            seen_names.add(channel_name)       # İsmi görüldü olarak işaretle
                        # else: # Yinelenenleri atla
                        #     print(f"-> Atlandı (yinelenen isim): {channel_name}")
                    else:
                        print(f"⚠️ Uyarı: İsim çıkarılamadı: {current_extinf}")
                    
                    current_extinf = None # #EXTINF satırını sıfırla
                # Diğer satır türlerini (varsa) şimdilik göz ardı ediyoruz
                
    except Exception as e:
        print(f"❌ Dosya okunurken/işlenirken hata oluştu: {e}")
        return

    if not output_lines:
        print("ℹ️ Temizlenecek geçerli kanal bulunamadı.")
        return

    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            if header_lines:
                outfile.write("\n".join(header_lines))
                outfile.write("\n")
            outfile.write("\n".join(output_lines))
        print(f"✅ {len(output_lines) // 2} adet benzersiz isimli kanal '{output_file}' dosyasına yazıldı.") # Her kanal 2 satır
    except Exception as e:
        print(f"❌ Çıktı dosyası yazılırken hata oluştu: {e}")

if __name__ == "__main__":
    clean_m3u8(INPUT_FILENAME, OUTPUT_FILENAME)
    print("\n🎉 Temizleme işlemi tamamlandı!")
