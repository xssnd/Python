# Disk Space Monitor

Mini software Python untuk memantau kapasitas **setiap partisi/filesystem yang ter-mount** dan memberi peringatan ketika ruang kosong tersisa **10% atau kurang**.

## Fitur

- Deteksi partisi lintas platform menggunakan `psutil` (Linux, Windows, macOS).
- Status `OK`, `WARNING` (default free space <= 10%), dan `CRITICAL` (default <= 5%).
- Menampilkan mount point, device, filesystem, total, terpakai, dan ruang kosong.
- Mode sekali jalan (`--once`) atau pemantauan berkala.
- Notifikasi opsional ke Telegram, Discord Webhook, dan SMTP Email.
- Cooldown per mount point untuk menghindari spam; notifikasi recovery saat kondisi pulih.
- Konfigurasi JSON dan environment variables untuk kredensial.
- Abaikan mount point tertentu, opsi untuk melewati removable drive, output JSON.
- Logging ke console/file, graceful shutdown (Ctrl+C/SIGTERM), dan unit tests.
- Filesystem yang tidak dapat dibaca dilewati tanpa menghentikan pemantauan.

## Persyaratan

- Python 3.10+
- Dependensi: `psutil`

## Instalasi

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json`. Setidaknya satu kanal notifikasi dapat diisi; tanpa konfigurasi notifikasi, hasil tetap tampil di terminal.

## Menjalankan

```bash
# Satu kali scan
python monitor.py --once

# Scan berulang sesuai interval config
python monitor.py

# Output JSON untuk integrasi/automation
python monitor.py --once --json

# Lokasi konfigurasi khusus
python monitor.py --config /path/to/config.json
```

Default interval adalah 5 menit. Interval minimum 5 detik.

## Konfigurasi

| Kunci | Default | Keterangan |
|---|---:|---|
| `warning_percent` | 10 | Peringatan jika free space <= nilai ini |
| `critical_percent` | 5 | Status kritis jika free space <= nilai ini |
| `interval_seconds` | 300 | Jeda antar scan |
| `cooldown_seconds` | 3600 | Jeda notifikasi berulang per mount |
| `recovery_alerts` | true | Kirim pesan ketika partisi kembali sehat |
| `include_removable` | true | Sertakan removable drive |
| `ignored_mounts` | [] | Daftar mount point yang diabaikan |
| `log_file` | null | Path file log opsional |

### Environment variables untuk kredensial

| Kanal | Environment variables |
|---|---|
| Telegram | `DSM_TELEGRAM_BOT_TOKEN`, `DSM_TELEGRAM_CHAT_ID` |
| Discord | `DSM_DISCORD_WEBHOOK_URL` |
| Email | `DSM_SMTP_HOST`, `DSM_SMTP_PORT`, `DSM_SMTP_USERNAME`, `DSM_SMTP_PASSWORD`, `DSM_EMAIL_FROM`, `DSM_EMAIL_TO` |

Kredensial dari environment akan menimpa nilai pada JSON. Jangan commit `config.json` atau token/webhook ke Git.

## Unit tests

```bash
python -m unittest discover -s tests -v
```

Tes mencakup batas threshold, klasifikasi status, filesystem tidak terbaca, mount duplikat, cooldown, dan recovery.

## Struktur

```text
disk_space_monitor/
├── monitor.py
├── notifiers.py
├── config.example.json
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
```

## Catatan operasional

- Jalankan dengan akun yang memiliki izin membaca informasi filesystem.
- Gunakan SMTP TLS/STARTTLS sesuai kebijakan mail server.
- Pengiriman notifikasi memerlukan koneksi internet; kegagalan kanal dicatat dan tidak menghentikan scan.
- Persentase dihitung dari byte free dibagi total kapasitas filesystem.
