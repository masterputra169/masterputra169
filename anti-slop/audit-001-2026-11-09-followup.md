# Laporan lanjutan audit 001 (2026-11-09)

Disetujui: semua nomor (1 sampai 18). Commit: `8f8b9c3`, branch `claude/compassionate-bell-fq6pio`.
File yang diubah: `scripts/build.py`, `README.md`, `.github/workflows/build.yml` (warna snake), file baru `DESIGN.md`.

**Belum live.** Workflow build hanya berjalan di `main`, jadi SVG baru baru dibuat setelah branch ini di-merge. Sebelum merge, lihat bagian "Yang harus dicek setelah merge".

## Status per temuan

| # | Status | Yang dikerjakan |
|---|---|---|
| 1 | Selesai | Setiap gambar punya 2 layout: `WIDE` 960 dan `NARROW` 480. README memilih lewat `<source media="(max-width: 1011px)">`. Teks terkecil di layar sekarang 11.5 sampai 19 px (sebelumnya 2.9 px). |
| 2 | Selesai | Kartu proyek full width, satu per baris, dan masing-masing tetap jadi link sendiri. |
| 3 | Selesai | `muted` gelap #8b98ad (≥6.4:1), `muted` terang #5b6b82 (≥5.0:1), cyan terang #0e7490 (≥4.95:1). Mint dan rose untuk teks punya token sendiri. `dim` tidak lagi dipakai untuk teks. |
| 4 | Selesai | 0 em dash di README dan di semua 44 SVG. Nilai kosong sekarang "n/a" atau "none yet". |
| 5 | Selesai (lebih jauh dari rencana) | Semua loop dihapus. Animasi masuk satu kali juga dihapus, karena terbukti Chromium tidak meneruskan `prefers-reduced-motion` ke SVG di dalam `<img>` (lihat catatan). Dial MOTION 1. |
| 6 | Selesai | Chip `0x7a…` diganti sumbu waktu asli: jam buka 4 candle dalam WIB. |
| 7 | Selesai | Tombol Connect jadi SVG setinggi 48 px dengan jarak ±9 px. Badge Followers/Stars tidak lagi berupa link, dan badge X di atas dihapus karena sudah ada di Connect. |
| 8 | Sebagian (batas platform) | Ada 5 gambar lebih sedikit (judul section). Tinggi gambar 100% tetap tidak bisa dipesan di GitHub. Dicatat di DESIGN.md. |
| 9 | Selesai, perlu konfirmasi | `DESIGN.md` berisi Design Read dan dial ENERGY 2 / RHYTHM 2 / MOTION 1, ditulis dari desain yang sudah ada. **Silakan dibaca dan diubah kalau tidak sesuai.** |
| 10 | Selesai | Gradien cyan→violet hanya di nama. Orb radial dihapus semua. Judul, footer, dan bar memakai warna solid. |
| 11 | Selesai | Pola titik dihapus dari semua SVG. |
| 12 | Selesai | Strip warna di kiri kartu dihapus. |
| 13 | Selesai | Label pakai Inter dengan huruf biasa (sentence case). Mono hanya untuk data. Baris `$ whoami` dan kursor berkedip dihapus. |
| 14 | Selesai | Badge jadi "Live", titik statis, radius 7, tanpa kapital. |
| 15 | Selesai | Alasan panah tertulis di DESIGN.md. Badge DollarKilat tidak lagi menulis domain yang bukan tujuan link-nya. |
| 16 | Selesai | Warna teks per tema tinggal 6: cyan, mint, rose, dan 3 netral. Violet hanya ada di gradien nama dan bar bahasa. Blue dan indigo dihapus. |
| 17 | Selesai | Chip, tag, dan badge radius 7. Tidak ada lagi bentuk pil penuh. |
| 18 | Selesai | Judul section jadi heading Markdown (`## About` dan seterusnya). |

Tambahan (ditemukan saat memperbaiki):
- **Fallback `mock_stats()` sebelumnya tampil seolah data asli** kalau API dan cache sama-sama gagal. Sekarang header dan stats menulis "Demo data" (R-17, R-38). Sudah dites dengan `--mock`.
- **Temuan baru #19 (belum disentuh, butuh persetujuan):** snake kontribusi dari Platane/snk beranimasi tanpa henti (R-19). Snake ini tidak ada di daftar audit, jadi saya biarkan. Kalau ingin MOTION 1 sepenuhnya, hapus blok snake dari README.

## Bukti verifikasi

- **Build:** `python scripts/build.py --out dist` menghasilkan 44 SVG. Font Google ter-embed, data BTC dan stats dari cache branch `output` (API langsung diblokir di sandbox). Build `--mock` juga berhasil.
- **Sweep lebar layar** (README di-render lokal, lebar konten meniru GitHub), di tema gelap dan terang:

| Viewport | Lebar README | Layout | Teks terkecil | Overflow |
|---|---|---|---|---|
| 360 | 304 | narrow | 12.0 px | 0 |
| 390 | 334 | narrow | 13.2 px | 0 |
| 600 | 544 | narrow | ≥19 px | 0 |
| 740 | 684 | narrow | ≥19 px | 0 |
| 768 | 392 | narrow | 15.5 px | 0 |
| 900 | 524 | narrow | ≥19 px | 0 |
| 1011 | 635 | narrow | ≥19 px | 0 |
| 1012 | 580 | wide | 11.5 px | 0 |
| 1280 | 848 | wide | 16.8 px | 0 |

- **Kontras:** setiap `fill` teks di 44 SVG dicek terhadap panel, chip, bg2, dan latar halaman GitHub. Hasilnya 0 pelanggaran (≥4.5:1, atau ≥3:1 untuk teks ≥24).
- **Pola terlarang:** 0 kemunculan `animation`, `<animate`, `animateMotion`, `repeatCount`, `infinite`, `pattern`, `radialGradient`, dan `—` di semua SVG.
- **Tap target:** keempat tombol Connect terukur tinggi 48 px di semua lebar.
- **Link (dicek dari kode, tidak diklik):** semua `href` sama dengan README lama (profil, 5 repo, X, LinkedIn, dollarkilat.xyz), dan tidak ada link baru. Saya tidak bisa membukanya dari sandbox karena github.com mengembalikan 504.
- **Reduced motion:** SVG yang dibuka langsung mematuhi `prefers-reduced-motion`, tapi di dalam `<img>` tidak. Karena itu semua animasi dihapus.

## Yang harus dicek setelah merge

1. **Dukungan `media="(max-width: 1011px)"` di GitHub.** Saya tidak bisa merender README di github.com dari sandbox. Buka profil di HP dan di desktop. Kalau HP tetap menampilkan layout lebar (teks kecil), berarti GitHub membuang atribut itu. Kalau gambar hilang atau tema tertukar, kabari saya untuk rollback.
2. Tunggu workflow pertama setelah merge (±2 menit) sampai SVG `-narrow` dan `connect-*` muncul di branch `output`.
3. Baca `DESIGN.md` dan ubah kalau ada yang tidak sesuai selera Anda.

## Delivery Gate

**Block 1, Hard Gate**
- R-02 PASS: 0 em dash di README dan semua SVG (grep).
- R-03 PASS: tidak ada overflow di 9 lebar layar, teks ≥11.5 px, tombol 48 px. Belum diverifikasi di github.com (lihat cek #1).
- R-17, R-18, R-36, R-38 PASS: tidak ada angka, testimoni, atau klaim karangan. Chip hash dihapus, data demo diberi label.
- R-23 PASS: tidak ada aset baru selain tombol teks.
- R-24, R-26 PASS (inspeksi kode): setiap link punya tujuan yang sama dengan sebelumnya.
- R-25 PASS: 0 pelanggaran kontras di kedua tema.
- R-27 PASS: header dan stats punya state demo/error yang jujur, dan streak kosong menampilkan "none yet".
- R-28 N/A: tidak ada FAQ.
- R-32, R-39 PASS dengan batas: link adalah `<a>` asli dan semua gambar punya alt. Hover dan focus mengikuti GitHub (batas platform).
- R-33 PASS: semua perubahan ditulis di source `build.py`, bukan di-patch lewat script.
- R-34 PASS: kedua tema di-render dan dicek.
- R-35 **sebagian**: build dijalankan dan semua gambar di-render di 9 lebar layar. Link hanya dicek dari kode, dan render asli di github.com belum dites.
- R-37 PASS dengan catatan: DESIGN.md ada, tapi isinya draf dari saya dan perlu konfirmasi Anda.
- R-40 **batas platform**: tinggi gambar tidak bisa dipesan di GitHub, dan sudah dicatat.

**Block 2, Purpose-Gate:** PASS. Gradien hanya di nama, panah, dan badge, dan alasannya tertulis di DESIGN.md. Tidak ada glow, orb, pola, maupun animasi.

**Block 3, Liveliness:** PASS. Dial dideklarasikan. Focal point: nama + chart. Motif: data pasar yang jujur. Aksen: satu gradien di nama.

**Block 4, Quality Locks:** PASS. Palet 2 warna inti, radius bervariasi, tidak ada buzzword atau CTA generik.

Kesimpulan: siap di-merge **setelah** Anda membaca DESIGN.md. Setelah merge, lakukan cek #1 di HP.
