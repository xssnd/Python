from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging
import time
from tqdm import tqdm

# Menerima input URL dari pengguna
url = input("Masukkan URL halaman yang akan di-scrape: ")

# Menerima input nama file log dari pengguna
log_filename = input("Masukkan nama file log (contoh: scraping_log.txt): ")

# Inisialisasi WebDriver (misalnya, ChromeDriver) dalam mode "headless" (tanpa buka browser)
options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

# Pengaturan driver tanpa option headless (non aktifkan jija tidak dibuthkan)
# driver = webdriver.Chrome()

# Buka URL
driver.get(url)

# Memulai timer
start_time = time.time()

# Menghitung jumlah total iterasi untuk progress bar
total_iterations = 0

# Inisialisasi set dan progress bar
unique_urls = set()
pbar = tqdm(total=total_iterations)

# Konfigurasi logging
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(message)s')

while True:
    # Scroll ke bawah halaman
    scroll_script = "window.scrollTo(0, document.body.scrollHeight);"
    for i in range(99999000):
        try:
            driver.execute_script(scroll_script)
        except Exception as e:
            break
    
    # Tunggu beberapa detik agar konten tambahan dimuat
    time.sleep(3)

    # Dapatkan konten halaman saat ini
    page_source = driver.page_source

    # Parsing halaman dengan BeautifulSoup
    soup = BeautifulSoup(page_source, 'html.parser')

    # Ambil semua link pada halaman ini
    links = [a['href'] for a in soup.find_all('a', href=True)]
    total_links = len(links)

    if total_links == total_iterations:
        # Jika tidak ada penambahan link, proses dihentikan
        break
    else:
        total_iterations = total_links

    # Logging URL yang telah di-scan
    for link in links:
        if link not in unique_urls:
            unique_urls.add(link)
            logging.info(link)
            pbar.update(1)

# Menghentikan timer (Anda bisa menghentikan program secara manual)
end_time = time.time()

# Cetak waktu yang diperlukan untuk scraping
scraping_time = end_time - start_time
print(f"Waktu scraping: {scraping_time} detik")

# Simpan semua link yang telah diambil ke dalam file 'text.txt' (mode "append")
with open('text.txt', 'a') as file:
    for link in links:
        file.write(link + '\n')

# Tutup browser
driver.quit()
