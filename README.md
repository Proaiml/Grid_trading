# Grid Trading Bot for Binance

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Binance API](https://img.shields.io/badge/Binance-API-F0B90B.svg)](https://binance-docs.github.io/apidocs/spot/en/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**Grid Trading Bot**, kripto para piyasalarında belirlenen fiyat aralıklarında otomatik olarak parçalı alım-satım yaparak piyasa dalgalanmalarından (volatilite) kâr sağlayan algoritmik bir ticaret botudur.

---

## 📊 Grid Trading Stratejisi Nedir?

Grid Trading, varlığın fiyatının belirli bir bant aralığında dalgalandığı (ranging/sideways) piyasa koşullarında en yüksek performansı veren kantitatif bir stratejidir:

- **Fiyat Düştükçe:** Önceden hesaplanan her grid basamağında otomatik **ALIM (BUY)** yapar.
- **Fiyat Yükseldikçe:** Bir alt basamaktan alınan varlığı kâr marjıyla otomatik **SATAR (SELL)**.
- **Duygulardan Bağımsız:** FOMO (kaçırma korkusu) veya panik satışı gibi insani zaafları ortadan kaldırarak 7/24 mekanik ve disiplinli çalışır.

---

## 🏗️ Matematiksel Model ve Sektör Mimarisi

Bot, sermayenizi ve fiyat aralığınızı matematiksel olarak eşit parçalara bölerek sektörlere ayırır:

```
higher_zone ──── [Price_High, ∞] ─────────────────> Tavan bölgesi (Tüm varlıklar satılır)
sector 5    ──── [Price_High - 1x, Price_High] ───> SELL / BUY Koridoru
sector 4    ──── [Price_Low + 3x, Price_Low + 4x]─> SELL / BUY Koridoru
sector 3    ──── [Price_Low + 2x, Price_Low + 3x]─> SELL / BUY Koridoru
sector 2    ──── [Price_Low + 1x, Price_Low + 2x]─> SELL / BUY Koridoru
sector 1    ──── [Price_Low, Price_Low + 1x] ─────> En alt alım koridoru
dead_zone   ──── [0, Price_Low] ──────────────────> Taban bölgesi (Bekleme)
```

### Hesaplama Formülleri:
1. **Toplam Sektör Sayısı:**
   $$\text{Grid\_Area} = \text{Grid\_Number} + 1$$
2. **Sektör Başına Düşen Bakiye:**
   $$\text{Sector\_Balance} = \frac{\text{Balance}}{\text{Grid\_Area}}$$
3. **Grid Fiyat Genişliği (Basamak Boyutu):**
   $$\text{Grid\_balance} = \frac{\text{Price\_High} - \text{Price\_Low}}{\text{Grid\_Area}}$$

### Sektör Durum Makinesi (State Machine):
Her sektör 2 farklı durumdan birinde bulunur:
- **`"$"` (Nakit Durumu):** Sektör nakittedir. Fiyat bir üst sektörden bu sektöre düştüğünde anında `Sector_Balance` tutarında **ALIM** yapar ve durumunu `"A"`ya çevirir.
- **`"A"` (Varlık Durumu):** Sektörde kripto varlık tutulmaktadır. Fiyat bu sektörden bir üst sektöre yükseldiğinde pozisyon kârla **SATILIR** ve durum tekrar `"$"**a döner.

---

## 📁 Proje Dosya Yapısı

```
Grid_trading/
│
├── main.py                 # Canlı Binance botu (İlhan Koçaslan'ın orijinal çekirdek kodu)
├── simulation.py           # Risksiz, görsel grafikli strateji simülatörü
├── run_simulation.bat      # Simülatörü tek tıkla çalıştıran Windows başlatıcısı
├── run_bot.bat             # Canlı botu tek tıkla çalıştıran Windows başlatıcısı
├── balance.json            # Bakiye ve sektör takip yapılandırması
├── loggrid.json            # Gerçekleşen işlemlerin kâr logları
├── requirements.txt        # Python bağımlılıkları (python-binance, matplotlib)
├── .env.example            # Binance API anahtarları için örnek yapılandırma
└── README.md               # Detaylı kullanım ve strateji kılavuzu
```

---

## 🚀 Hızlı Başlangıç (Quickstart)

### 1. Bağımlılıkların Kurulması
Komut satırından gerekli kütüphaneleri yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Risksiz Simülatörü Çalıştırma (Tavsiye Edilen)
Herhangi bir API anahtarına veya gerçek paraya ihtiyaç duymadan stratejinin nasıl çalıştığını, alım-satım noktalarını ve kâr eğrisini görmek için:

```bash
python simulation.py
```
*(Windows kullanıcıları doğrudan **`run_simulation.bat`** dosyasına çift tıklayabilir).*

Simülasyon tamamlandığında alım (yeşil üçgenler) ve satım (kırmızı üçgenler) noktalarını gösteren detaylı bir analiz grafiği açılacaktır.

### 3. Canlı Botu Çalıştırma (Binance)
Canlı işlem yapmadan önce:
1. `main.py` içerisindeki `privatekey` ve `secretkey` değişkenlerine Binance API anahtarlarınızı girin.
2. İşlem parametrelerini (`Asset`, `Price_Low`, `Price_High`, `Grid_Number`, `Balance`) kendi risk toleransınıza göre ayarlayın.
3. Botu başlatın:
```bash
python main.py
```
*(veya **`run_bot.bat`** dosyasına çift tıklayın).*

---

## ⚙️ Parametreler Kılavuzu (`main.py`)

| Parametre | Varsayılan | Açıklama |
| :--- | :---: | :--- |
| `Asset` | `"MATICUSDT"` | İşlem yapılacak Binance Spot işlem çifti |
| `Price_Low` | `1.42` | Grid sisteminin alt fiyat sınırı |
| `Price_High` | `1.70` | Grid sisteminin üst fiyat sınırı |
| `Grid_Number` | `4` | Alt ve üst sınır arasındaki grid sayısı |
| `Balance` | `60` | Stratejiye ayrılan toplam USDT sermayesi |
| `Total_Profit` | `0` | Biriken toplam kâr sayacı |
| `Total_trade` | `0` | Başarılı tamamlanan al-sat döngüsü sayısı |

---

## 🔒 Güvenlik & Risk Bildirimi

- **API İzinleri:** Binance üzerinde API anahtarı oluştururken **"Enable Spot & Margin Trading"** seçeneğini açın; ancak **"Enable Withdrawals" (Para Çekme) iznini KESİNLİKLE KAPALI** tutun.
- **Risk Uyarısı:** Kripto para ticareti yüksek risk içerir. Grid Trading stratejisi yatay piyasalarda yüksek verim sağlarken, sert tek yönlü düşüş trendlerinde varlığın değer kaybetme riski bulunmaktadır. Canlıya almadan önce mutlaka küçük tutarlarla veya simülatör üzerinde test ediniz.

---

## 👨‍💻 Yazar

- **İlhan Koçaslan** — [GitHub: @Proaiml](https://github.com/Proaiml)
- **BNB Cüzdan:** `0x13d598485848388110ec4ec3055e7c9731f5efba`
