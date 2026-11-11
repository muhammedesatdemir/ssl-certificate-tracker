# SSL Sertifika Takibi

Müşterilerin SSL sertifikalarının bitiş tarihlerini takip eden basit bir Django uygulaması.

- Sertifikalar (alan adı, müşteri adı, bitiş tarihi) Django admin panelinden eklenir ve düzenlenir.
- Ana sayfa tüm sertifikaları bitiş tarihine göre sıralı listeler; her satırda **kalan gün** ve **durum** görünür.

## Durum kuralları

| Durum | Koşul |
|---|---|
| Süresi Dolmuş | kalan gün < 0 |
| Yakında Dolacak | 0 ≤ kalan gün ≤ 30 |
| Geçerli | kalan gün > 30 |

- Kalan gün = `bitiş tarihi - bugün`. Bitiş günü, gün sonuna kadar geçerli sayılır; bugün biten sertifikanın kalan günü **0** ve durumu "Yakında Dolacak"tır.
- "Bugün", `Europe/Istanbul` takvim günüdür (`TIME_ZONE`, `USE_TZ=True`).
- Eşik (30 gün) tek bir sabittir: `EXPIRY_WARNING_DAYS` ([certificates/models.py](certificates/models.py)).
- Aynı alan adı farklı bitiş tarihleriyle tekrar girilebilir (yenilemeler için); aynı alan adı + aynı tarih çifti girilemez. Alan adı kaydedilirken `strip().lower()` ile normalize edilir.

## Kurulum

Gereksinim: Python 3.11 veya üzeri.

```powershell
# Windows (PowerShell)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

> Windows'ta `python` komutu eski bir sürüme gidiyorsa venv'i yukarıdaki gibi `py -3.13` ile oluşturun ve her zaman venv'i aktifleştirin.

## Çalıştırma

```powershell
python manage.py runserver
```

- Liste sayfası: http://127.0.0.1:8000/
- Admin paneli: http://127.0.0.1:8000/admin/

### Örnek veri (isteğe bağlı)

```powershell
python manage.py seed_certificates
```

Bugüne göre 5 örnek sertifika ekler (−10, 0, +15, +30, +60 gün); böylece her durum tabloda görünür. Yalnızca `*.example.com` örnek alan adlarına dokunur, tekrar çalıştırılabilir (kopya oluşturmaz, tarihleri bugüne göre yeniler).

## Testler

```powershell
python manage.py test
```

Testler tarihi `today=` parametresiyle dışarıdan verir; gerçek saate bağlı değildir. Kapsam: durum sınırları (−1, 0, +29, +30, +31 gün, çok uzak gelecek/geçmiş), alan adı normalizasyonu, benzersizlik, sıralama, liste sayfası, admin ve seed komutu.

## Ortam değişkenleri

| Değişken | Varsayılan (yalnızca geliştirme) |
|---|---|
| `DJANGO_SECRET_KEY` | geliştirme anahtarı |
| `DJANGO_DEBUG` | `True` |
| `DJANGO_ALLOWED_HOSTS` | boş (virgülle ayrılmış liste) |

Canlı ortamda ilk ikisini mutlaka değiştirin.

## Bilinçli tercihler

- **Liste sayfası herkese açıktır.** Ödev kapsamında kullanıcı girişi beklenmediği için kimlik doğrulama eklenmedi. Sayfa müşteri adlarını gösterdiğinden gerçek veriyle kullanılmadan önce erişim kısıtlaması eklenmelidir.
- Kapsam dışı bırakılanlar: canlı TLS taraması, e-posta/bildirim, Celery, REST API, joker (`*.`) alan adı doğrulaması.


## AI ile çalışma notu

### 1. İşe nasıl başladın, AI'a ilk ne verdin?
İşe doğrudan kod yazdırarak başlamadım. İlk adımda repo köküne projenin kural ve kısıtlarını belirten taslak bir `CLAUDE.md` dosyası ekledim. Yapay zekaya ilk prompt'umda bu kuralları SSL/güvenlik domaini ve Django mimarisi açısından incelemesini, potansiyel saat dilimi (timezone) ve sınır durumu (boundary) risklerini raporlamasını istedim. Gelen teknik önerilerden iş kuralı ve domain doğruluğu için kritik olanları (Europe/Istanbul timezone, DateField + `localdate()` kullanımı, tek eşik sabiti) kabul ettim; ödev kapsamını gereksiz şişirecek olanları (kullanıcı girişi, Celery, TLS tarayıcı vb.) ise bilinçli olarak eledim. Kurallar kesinleştikten sonra adım adım bir geliştirme planı çıkarttırarak kodlamaya geçtik.

### 2. AI'ın yazdığı kodun doğru çalıştığını nasıl kontrol ettin?
Yapay zekanın ürettiği çıktılara doğrudan güvenmek yerine çok katmanlı bir doğrulama uyguladım:
- **Statik Kod İncelemesi:** Zaman farkı hesaplamalarında naive datetime yerine `django.utils.timezone.localdate()` kullanıldığını, veritabanı indeksini ve admin form kontrollerini bizzat inceledim.
- **Birim Testleri (25 Test):** Model seviyesindeki sınır günleri (−1, 0, +29, +30, +31 gün), alan adı normalizasyonu, admin filtre tutarlılığı ve liste görünümü için toplam 25 birim test koştum. Testlerde zamana bağımlılığı kırmak için model metotlarına `today=` parametresi dışarıdan enjekte edildi.
- **Görsel ve Uçtan Uca Doğrulama:** Geliştirdiğimiz `seed_certificates` komutu ile tüm sınır durumlarını içeren örnek verileri yerel veritabanına basarak hem ana tabloyu hem de admin panelindeki arama ve filtreleri tarayıcı üzerinden elle test ettim.

### 3. Testlerin hangi durumları kapsaması gerektiğine nasıl karar verdin?
Sertifika geçerlilik takiplerinde hatalar genellikle sınır günlerde (edge cases) ortaya çıkar. Bu yüzden rastgele tarihler yerine **Sınır Değer Analizi (Boundary Value Analysis)** metodolojisini uyguladım:
- **Süresi Dolmuş Eşiği:** Geçmiş tarihler (örn. −10 gün ve hemen dün: −1 gün). Negatif günlerin ve kırmızı rozetin doğrulanması.
- **Sıfırıncı Gün (Bugün):** Bitiş tarihi tam bugün olan kayıt (0 gün kaldı). Gün sonuna kadar geçerli sayıldığı için "Yakında Dolacak" durumunda ve turuncu rozetle listelenmesi.
- **Uyarı Penceresi Sınırları:** Eşik değeri olan 30 günün hemen öncesi (+29 gün), tam eşik günü (+30 gün) ve hemen bir gün sonrası (+31 gün - geçerli durumu).
- **Domain Bütünlüğü:** Admin formundan büyük harfle veya boşlukla girilen alan adlarının normalizasyonu ve `(domain_name, expiration_date)` benzersizliğinin veritabanı seviyesinde korunması.

### 4. AI'ın yanlış yaptığı ya da yönlendirmen gereken bir an oldu mu, ne yaptın?
Süreç boyunca yapay zekayı iki ana başlıkta yönlendirmem gerekti:

1. **Kapsam Yönetimi ve Aşırı Mühendislik (Over-engineering) Engeli:**
   AI ilk analizde kullanıcı kimlik doğrulaması (login), Celery ile arka plan görevleri, canlı TLS taraması ve karmaşık regex validatörleri gibi kapsamı aşan öneriler getirdi. Ödevin *"basit ve çalışır olması yeterli, kullanıcı girişi beklenmiyor"* kısıtını hatırlatarak bu bileşenleri eledim ve projenin gereksiz karmaşıklaşmasını engelledim.

2. **İş Mantığı ve Karar Noktalarının Netleştirilmesi:**
   AI mimariyi kurarken bazı domain kararlarını bana bıraktı. Bu noktalarda süreci şu kararlarla yönlendirdim:
   - Alan adının tek başına benzersiz (unique) yapılmasının gelecekteki sertifika yenilemelerini engelleyeceğini belirterek `(domain_name, expiration_date)` çiftine benzersizlik verilmesini sağladım.
   - Sınır günü mantığını netleştirerek, bitiş tarihi tam bugün olan (kalan gün: 0) sertifikaların gün sonuna kadar geçerli sayılarak "Yakında Dolacak" kategorisine girmesini kurala bağladım.
   - Testlerde zaman mock'lamanın yaratabileceği kırılganlığı önlemek adına, model metoduna dışarıdan tarih alabilen (`today=None`) sade bir parametrik yapı kurdurdum.