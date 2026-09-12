# kaan-trade — Kripto Analiz Paneli ve Sanal Bot

## Paneli başlatmak

Masaüstündeki **"kaan-trade Paneli"** kısayoluna çift tıklayın. Uygulama
kendi penceresinde açılır — tarayıcı değil, adres çubuğu yok, siyah komut
penceresi yok. Kapatmak için pencereyi kapatın; arka plandaki sunucu da
otomatik kapanır.

Kısayol kaybolursa klasördeki **`KaanTrade.vbs`** dosyası aynı işi yapar.

### Nasıl çalışıyor?

Uygulama iki parçadan oluşuyor:

1. **Streamlit sunucusu** — arka planda, görünmez şekilde çalışır ve
   sayfayı üretir.
2. **`masaustu.py`** — `pywebview` ile bir Windows penceresi açar ve
   sayfayı içine yükler.

Yani bir web sayfası, masaüstü uygulaması kılığında. Bunu seçtim çünkü
Python'la gerçek bir arayüz yazmanın en kısa yolu bu ve grafik konusunda
çok güçlü.

### Tarayıcıda açmak isterseniz

Hata ayıklamak için tarayıcı sürümü daha kullanışlı olabilir
(`uygulamayi_baslat.bat` ya da):

```bash
.\.venv\Scripts\streamlit.exe run uygulama.py
```

### Panel ne gösteriyor?

Panelin beş sayfası var, üstteki sekmelerden geçiş yapılıyor:

**Piyasa** — Binance'teki bütün USDT çiftleri (~650 coin) tek tabloda.
Üstte piyasa geneli (toplam hacim, yükselen/düşen sayısı, BTC hakimiyeti,
Korku & Açgözlülük), ortada en çok yükselen/düşen/hacimli coinlerin çubuk
grafikleri, altta **arama kutulu, sıralanabilir tam tablo**. Bir satıra
tıklayıp "analiz sayfasında aç" dediğinizde o coin ikinci sayfaya açılır.

**Coin analizi** — Kenar çubuğundaki arama kutusundan herhangi bir coini
yazıp seçin. Anlık fiyat, CoinGecko piyasa bilgileri, teknik durum (RSI,
hareketli ortalamalar), vadeli piyasa verisi (fonlama oranı, açık
pozisyon) ve TradingView tarzı mum grafiği.

**Analiz Botu** — Seçili coin için, piyasada yaygın izlenen teknik
durumları tek tek listeler (trend, RSI/hacim uyumsuzluğu, MACD,
Bollinger sıkışması, destek/direnç, para akışı, fonlama oranı, emir
defteri, BTC'ye göre göreli güç). Ayrıntısı aşağıda, "Analiz Botu"
bölümünde.

**Karşılaştırma** — En fazla 8 coin seçip aynı grafikte kıyaslayın
(hepsi başlangıçta 100 kabul edilir), dönem getirisi / oynaklık / en
büyük düşüş tablosu, ve bir **korelasyon haritası**: coinler birlikte mi
hareket ediyor, yoksa birbirinden bağımsız mı?

**Haberler** — 9 global kaynaktan (7 kripto-odaklı + 2 genel piyasa)
toplanan haber akışı. Türe ve kaynağa göre süzülebilir, başlık/özette
arama yapılabilir, her haberin hangi coin(ler)den bahsettiği otomatik
etiketlenir. Başlığa tıklayınca haber kaynağında açılır.

### Mum grafiği ve göstergeler

Coin analizi sayfasındaki mum grafiği TradingView tarzı. Gösterge
seçimi de TradingView'daki "gösterge ekle" listesine benzer: istediğiniz
kadar ekleyip çıkarabilirsiniz.

- **Zaman dilimi**: 1 dakika ile 1 hafta arası
- **Mum sayısı**: 100 ile 1000 arası
- **Ortalama tipi**: SMA (basit) ya da EMA (üstel, fiyata daha hızlı tepki verir)
- **Ortalama periyotları**: 9 / 20 / 50 / 100 / 200

**Göstergeler** (çoklu seçim, istediğiniz kadar açık kalabilir):

| Gösterge | Nerede çizilir | Ne gösterir |
|---|---|---|
| Hacim | Alt panel | İşlem hacmi çubukları |
| RSI | Alt panel | 0-100 arası, 70 üstü aşırı alım / 30 altı aşırı satım |
| MACD | Alt panel | İki ortalamanın farkı ve momentum histogramı |
| Stokastik | Alt panel | Fiyatın son dönemin aralığına göre konumu (0-100) |
| Bollinger Bantları | Fiyatın üzerine | 20 dönemlik oynaklık bantları |
| VWAP | Fiyatın üzerine | Ekrandaki mumlar boyunca hacim ağırlıklı ortalama fiyat |
| Parabolic SAR | Fiyatın üzerine | Trend yönünü gösteren noktalar |
| Fibonacci | Fiyatın üzerine | Ekrandaki en yüksek/düşük arasında standart geri çekilme seviyeleri |

Her göstergenin ne çizdiği, açtığınızda grafiğin altındaki
"Seçili N gösterge ne çiziyor?" bölümünde de yazıyor.

Ayrıca:
- Altta **hacim çubukları**, mumla aynı renkte
- Fareyle **sürükleyerek kaydırın**, **tekerlekle yakınlaştırın**
- Bir mumun üzerine gelin: açılış, en yüksek, en düşük, kapanış görünür

**Mum grafiği nasıl okunur?**

Her mum bir zaman dilimini anlatır. Kalın gövdenin alt ve üst kenarları
açılış ve kapanış fiyatlarıdır. İnce fitiller o dönemde görülen en yüksek
ve en düşük fiyatı gösterir.

- **Yeşil mum**: kapanış açılıştan yüksek, o dönem yükseldi
- **Kırmızı mum**: kapanış açılıştan düşük, o dönem düştü
- **Uzun fitil**: fiyat oraya gitti ama tutunamadı
- **Büyük gövde**: o dönemki hareket güçlüydü

Grafik, tablo ve korelasyon haritası gibi ağır kısımlar **kendiliğinden
yenilenmez** — yakınlaştırmanız bozulmasın diye. Siz bir şey
değiştirdiğinizde (coin, zaman dilimi, ayar) yenilenirler.

Her kutunun yanındaki **`?` işaretine tıklayın** — o sayının ne anlama
geldiğini ve hangi kaynaktan geldiğini yazdım.

### Anlık veri nasıl çalışıyor?

Panel Binance'e **WebSocket** ile bağlanıyor — borsaya "fiyat kaç?" diye
sormak yerine, borsa her değişimi kendisi anında gönderiyor. Gecikme
genelde 1 saniyenin altında.

Bu bağlantı arka planda ayrı bir iş parçacığında (thread) sürekli açık
duruyor ([canli_veri.py](canli_veri.py)) ve bütün coinlerin son fiyatını
hafızada tutuyor. Ekran bu hafızadan okuyor, yani "anlık güncelleme"
açıkken internete tekrar gitmiyor — sadece hafızadaki en güncel sayıyı
gösteriyor.

Kenar çubuğundan **yenileme aralığını** (1-5 saniye) ve **en az 24 saatlik
hacim süzgecini** ayarlayabilirsiniz. Hacim süzgeci önemli: çok düşük
hacimli coinlerde fiyat güvenilmez olur, tek bir küçük emir fiyatı
%50 oynatabilir.

**Neden sadece "fiyat/özet" kısmı saniyede bir yenileniyor da grafik
yenilenmiyor?** Günlük mumdan hesaplanan RSI saniyede değişmez; onu her
saniye yeniden çizmek hem gereksiz hem de yakınlaştırmanızı bozar. Anlık
olması gereken tek şey fiyatın kendisi, panel de öyle tasarlandı.

**Peki "En çok yükselenler" gibi sıralamalı çubuk grafikler neden bazen
1-2 saniye geriden geliyor?** Bilerek öyle: sıralamaya dayalı bir grafik
saniyede bir yeniden çizilirse, ufak fiyat oynamalarında bile çubuklar
yer değiştirir ve göze "titriyor" gibi görünür. Bu yüzden bu grafikler
5 saniyede bir tazelenir — hem yeterince güncel kalır hem de akıcı
durur. Fiyat/yüzde kutuları bundan etkilenmez, onlar hep her saniye taze.

### Veri kaynakları

| Kaynak | Ne verir | Hız |
|---|---|---|
| Binance WebSocket | Anlık fiyat, 24s değişim, hacim (~650 coin) | ~1 saniye |
| Binance REST (ccxt) | Mum verisi, emir defteri | istek anında |
| Binance vadeli | Fonlama oranı, açık pozisyon | 60 saniye önbellek |
| CoinGecko | Piyasa değeri, sıralama, zirve | 2-5 dakika önbellek |
| CoinGecko /global | Toplam piyasa değeri, BTC/ETH hakimiyeti | 2 dakika önbellek |
| alternative.me | Korku & Açgözlülük endeksi | günlük |
| 9 haber kaynağı (RSS) | Başlık, özet, kaynak, coin etiketi | 5 dakika önbellek |

Hepsi ücretsiz, hiçbiri API anahtarı istemiyor. Yavaş değişen veriler
önbelleğe alınıyor, böylece kaynakların ücretsiz kullanım sınırlarının
çok altında kalıyoruz.

### Haber kaynakları

| Kaynak | Tür |
|---|---|
| CoinDesk, CoinTelegraph, Decrypt, CryptoSlate, Bitcoin.com, The Block, Investing.com | Kripto |
| MarketWatch, CNBC Markets | Genel piyasa (Fed kararı, enflasyon gibi kripto fiyatlarını da etkileyen makro haberler) |

Kaan-trade bu haberleri yazmaz, seçmez ya da yorumlamaz — RSS ile
kaynağında ne yayınlanmışsa onu, olduğu gibi gösterir. Bir kaynağa o an
ulaşılamazsa (kısa süreli kesinti gibi) diğer kaynaklardan gelen
haberler gösterilmeye devam eder, panel çökmez.

### Panel ne yapmaz

Fiyatın nereye gideceğini söylemez ve al/sat tavsiyesi vermez. Strateji
taraması bölümünde göreceğiniz gibi, test ettiğimiz 16 standart
göstergenin hiçbiri geleceği bilmedi. Panel **şu anki durumu** ölçer.

### Analiz Botu

**Analiz Botu tavsiye vermez.** Al/sat önerisi, hedef fiyat ya da genel
bir "sinyal puanı" üretmez — bilerek. Bunun yerine, seçili coin için
piyasada yaygın olarak izlenen teknik durumları **tek tek, birbirinden
bağımsız gözlemler** halinde listeler; yorumu size bırakır.

Örnek: fiyat düşerken bile "hacimde para girişi işareti var" ya da
"RSI'da pozitif uyumsuzluk var" gibi, düz grafikte kolayca görülmeyen
gözlemler ayrı ayrı gösterilir. Bazı gözlemler aynı anda birbiriyle
çelişebilir (biri yukarı, biri aşağı yönlü okunabilir) — bu bir hata
değil, piyasanın kendi doğası.

Gözlem kategorileri:

| Kategori | Neye bakar |
|---|---|
| Trend | Fiyatın 50/100/200 günlük ortalamalara göre konumu, altın/ölüm kesişimi |
| Momentum | RSI seviyesi, RSI/fiyat uyumsuzluğu (diverjans) |
| MACD | Sinyal çizgisine göre konum, histogram büyüme/küçülme |
| Volatilite | Bollinger bant sıkışması/dokunuşu, ATR trendi |
| Destek/Direnç | Geçmiş swing tepe/dip seviyelerine yakınlık, yıllık zirve/dip |
| Hacim | Hacim patlaması, OBV trendi ve OBV/fiyat uyumsuzluğu, VWAP konumu |
| Vadeli Piyasa | Fonlama oranının olağan dışı yüksek/düşük olması |
| Emir Defteri | Anlık alış/satış baskısı dengesi |
| Göreli Güç | Coinin son dönemde BTC'ye göre daha güçlü mü zayıf mı gittiği |
| Likidite | Fiyatın bir destek/direnç seviyesini fitille kırıp kapanışta geri dönmesi (likidite avı / SFP) |

Gözlemler **günlük mumlardan** hesaplanır (Coin analizi sayfasındaki
"teknik durum" kutusuyla aynı kaynak), bu yüzden saniyede değil, coin
değiştirdiğinizde yenilenir. Mantık [analiz_botu.py](analiz_botu.py)
içinde, Streamlit'e hiç bağımlı olmayan saf fonksiyonlar halinde yazılı
— her biri tek başına test edilebilir.

**Bu gözlemlerin dayandığı göstergeler "işe yaradığı kanıtlanmış"
oldukları için değil, piyasa katılımcıları tarafından yaygın izlendiği
için burada.** Strateji taraması bölümünde gördüğümüz gibi, aynı
göstergelerin hiçbiri geleceği güvenilir şekilde tahmin edemedi.

#### Piyasa taraması: 3 faktör hizalanması

Analiz Botu sayfasının üstünde, **tek bir coin değil hacim süzgecini
geçen bütün coinleri** tarayan bir bölüm var. "Piyasayı tara"
düğmesine bastığınızda, her coin için üç bağımsız durumu ayrı ayrı
kontrol eder ve hangilerinin AYNI ANDA görüldüğüne göre üç katmanda
gruplar. Her katman içinde coinler **hacme (likiditeye) göre** sıralanır
— en çok işlem gören coin en üstte.

Tarama **arka planda** (ayrı bir iş parçacığında) çalışır: taranırken
fiyat şeridi, sayfa geçişleri ve coin seçimi donmaz, panelin geri
kalanını normal şekilde kullanabilirsiniz.

1. **Sıkışma** — volatilite daralması (aşağıda açıklanan TTM Squeeze
   yöntemi).
2. **Yukarı yönlü hacim** — hacim patlaması ya da "sessiz birikim"
   (fiyat durgunken hacim artışı) sinyali, ama sadece **yukarı** yönlü
   olanlar sayılır; kırmızı mumdaki patlama ya da "para çıkışı" bu
   bacağı doldurmaz.
3. **Vadeli piyasa teyidi** — fonlama oranı aşırı pozitif DEĞİL (yani
   long'lar zaten aşırı kalabalık değil) VE açık pozisyon son 5 günde
   en az %3 artmış (vadeli piyasaya taze para giriyor).

Üçü birden görülen coinler **"sıkışma + hacim + vadeli teyidi"**
(en üstte), ilk ikisi görülen **"sıkışma + yukarı hacim"**, sadece
sıkışma görülen **"sadece sıkışma"** diye ayrı listelenir.

**Bu bir formül olsa da bir garanti ya da tahmin değildir.** Üç
faktörün aynı anda görülmesi, piyasada yaygın izlenen üç durumun bir
arada olduğu anlamına gelir — coinin yükseleceğinin kanıtı değil.
Vadeli piyasası olmayan coinler (çoğu küçük altcoin, Binance'te sadece
spot işlem görür) 3. bacağı hiçbir zaman teyit edemez; bu onların
"kötü" olduğu anlamına gelmez, sadece o veri kaynağının mevcut
olmadığı anlamına gelir.

**Sıkışma nasıl tespit ediliyor?** Sadece Bollinger bant genişliğinin
kendi geçmişine göre dar olup olmadığına bakmak yerine, **TTM Squeeze**
yöntemi kullanılıyor: Bollinger bantları (standart sapma tabanlı) ile
Keltner kanalı (ATR tabanlı) karşılaştırılıyor; Bollinger bantları
Keltner kanalının **içine** girdiğinde sıkışma sayılıyor. İki farklı,
birbirinden bağımsız oynaklık ölçüsünün aynı anda "dar" demesi, tek bir
ölçüye bakmaktan daha güvenilir kabul edilir. Sıkışma biraz önce
sonlandıysa (birkaç mum önce açıktı, şimdi kapandı) bu da ayrıca
"Sıkışma az önce sona erdi" diye işaretlenir.

**Daha fazla (az bilinen) altcoin taramak isterseniz** kenar
çubuğundaki "En az 24s hacim" süzgecini "Süzgeç yok" yaparak taramayı
bütün ~650 coine genişletebilirsiniz. Bu, taramayı önemli ölçüde
yavaşlatır ve listeye düşük hacimli/güvenilmez fiyatlı coinler de
girer — panel bunu bir uyarı olarak gösterir.

Tarama isteğe bağlıdır (düğmeye basınca çalışır, sayfa her açıldığında
otomatik taramaz) çünkü her coin için borsadan veri çekmek gerekiyor —
170 coin'de ilk tarama 30-60 saniye sürebilir, "Süzgeç yok" ile daha
uzun sürer. Sonraki taramalar, veri onbellekte kaldığı sürece çok daha
hızlı gelir. Sonuçlardaki bir coini incelemek isterseniz kenar
çubuğundaki arama kutusundan seçebilirsiniz.

**Gözlemler artık sadece KAPANMIŞ mumlara bakıyor.** Daha önce, o günün/
saatin/dakikanın henüz bitmemiş (yani hâlâ oluşmakta olan) son mumu da
hesaba katılıyordu — bu, özellikle hacim karşılaştırmalarını yanıltıcı
yapıyordu (gün yeni başlamışken "hacim düşük" görünüp aslında sadece
gün bitmediği için düşük görünüyordu). Artık her zaman son *kapanmış*
mum kullanılıyor; canlı grafikteki "şu an oluşan mum" ise ayrı ve doğru
bir mekanizmayla (WebSocket'ten gelen anlık fiyatla) ekleniyor.

#### Likidite avı / sahte kırılım (Swing Failure Pattern)

Piyasa Taraması bölümünün altında ikinci, bağımsız bir tarama daha
var: **likidite avı** (bilinen adlarıyla "stop hunt", "liquidity
sweep", "Swing Failure Pattern / SFP"). Bu, fiyatın bir önceki
destek/direnç seviyesini **fitille kırıp KAPANIŞTA geri döndüğü**
durumları arar — o seviyede bekleyen stop-loss ve kırılım emirlerinin
"süpürüldüğü", ama hareketin devam gücü olmadığı için fiyatın geri
toparlandığı, yaygın izlenen bir örüntü. Aynı anda bir kırmızı mumla
"likiditeye doğru" giden ama aslında sahte olabilen düşüşler (ya da
yükselişler) tam olarak bu.

Nasıl çalışıyor:
1. Önceki bir swing dip/tepe seviyesi bulunur (son mum hariç).
2. Son (kapanmış) mumun fitili o seviyenin ötesine geçiyor mu?
3. Ama kapanış yine seviyenin doğru tarafında mı kalıyor?
4. Hacim, o mumda son 20 mumun ortalamasının belirgin üzerinde mi?
   Bu, kullanıcının istediği "para giriş/çıkışına bakarak" teyididir —
   süpürmenin gerçek bir emir akışıyla mı, yoksa sessiz bir
   dalgalanmayla mı olduğunu ayırt etmeye yardım eder. Hacim teyidi
   olanlar "(hacim teyitli)" diye ayrıca işaretlenir, olmayanlar da
   listeye girer ama "zayıf teyit" olarak anlatılır.

Ayrıca **aşırı büyük sarkmalar (%15 üzeri) elenir** — gerçek bir
likidite avı tanım gereği küçük, kısa süreli bir fitil sarkmasıdır;
yüzde onlarca/yüzlerce bir sarkma aynı formüle uysa bile artık farklı
bir olaydır (büyük bir pump/dump ya da eski/anlamsız bir referans
seviyesi), test sırasında böyle bir sahte-pozitif örnek yakalayıp bu
sınırı ekledik.

Bu tarama, zaten çekilen mum verisiyle çalıştığı için **ek borsa
isteği gerektirmez** — sıkışma taramasıyla aynı anda, aynı düğmeyle
çalışır. Sonuçlar "destek fitille kırıldı" (olası sahte düşüş) ve
"direnç fitille kırıldı" (olası sahte yükseliş) diye iki gruba
ayrılır. Seçili tek bir coin için de aynı gözlem "Likidite" kategorisi
altında Analiz Botu'nun gözlem listesinde görünür.

**Web araştırmasında bu deseni "%66-68 başarı oranı" ile anan
kaynaklar var — ama bu rakamı burada ileri sürmüyoruz.** Bu projede
defalarca kanıtladığımız gibi (`tarama.py`), kimsenin bağımsız,
kontrol gruplu şekilde test edip yayınlamadığı böyle rakamlara
güvenmiyoruz. Söylediğimiz tek şey: "bu, piyasada yaygın izlenen bir
desenle eşleşiyor" — "genelde döner" değil.

### Görünüm

Panel, TradingView ve benzeri işlem platformlarından esinlenilerek
tasarlandı:

- **Üst navigasyon çubuğu** — logo ve sayfa sekmeleri (Piyasa / Coin
  analizi / Analiz Botu / Karşılaştırma / Haberler), pill/segmented-control
  görünümünde. Kenar çubuğu artık sadece ayarlara ayrılmış durumda.
- **Kayan fiyat şeridi (ticker tape)** — her sayfanın üstünde, en çok
  işlem gören ~16 coinin fiyat ve değişimini gösteren yatay, elle
  kaydırılabilir bir şerit.
- **Koyu tema** — TradingView'in gerçek renk paletine yakın
  (`#131722` zemin, `#2962ff` mavi vurgu), Inter yazı tipi ve Tabler
  ikon seti.
- **Renkli tablo** — "Bütün coinler" tablosundaki 24 saatlik değişim
  sütunu yeşil/kırmızı renklendirilir (pandas Styler ile).
- **Mini sparkline** — Coin analizi sayfasındaki büyük fiyat
  göstergesinin yanında, son 4 günün hafif bir eğilim çizgisi.

Bu görsel öğelerin tümü **hafif** tutuldu: sparkline gerçek bir
Plotly grafiği değil, elle yazılmış düz SVG — çünkü saniyede bir
yeniden çizilen bir başlıkta ağır bir grafik kütüphanesi çalıştırmak
akıcılığı bozar (bkz. yukarıdaki "En hareketli coinler" bölümünde
anlatılan aynı ders).

### Mum grafiği artık canlı

Coin analizi sayfasındaki mum grafiği, Yenileme aralığı ayarına göre
(1-5 saniye) kendini yeniliyor — eskiden sadece siz bir şey
değiştirdiğinizde güncelleniyordu. İki değişiklik bunu sağlıyor:

- **Canlı mum**: gerçek geçmiş verisi hep aynı kalır (5 dakikada bir
  önbellekten yenilenir), ama grafiğin en sağına WebSocket'ten gelen
  anlık fiyatla oluşan tek bir "şu an" mumu eklenir. Böylece grafik
  bir önceki kapanmış mumda değil, gerçekten şu anda duruyor gibi
  görünür.
- **Canlı fiyat çizgisi**: fiyatın üzerine, o anki değeri gösteren
  kesikli bir çizgi ve etiket çizilir; önceki kapanışa göre
  yeşil/kırmızı renk alır.

Yakınlaştırmanız `uirevision` sayesinde korunuyor — grafik saniyede
bir yeniden gönderilse de siz nereye bakıyorsanız orada kalırsınız.
Zaman dilimi/gösterge gibi ayarları değiştirmek de otomatik
yenilemeyle çakışmaz; bu, sayfa gezinmesinde daha önce çözdüğümüz
"otomatik yenileme tıklamayı geri alıyor" sorununun bir daha
yaşanmaması için özellikle test edildi.

Fiyat gösterimi de artık **tam hassasiyette**: yüksek fiyatlı
coinlerde (BTC gibi) bile kuruş kısmı atılmıyor — `$63,822` değil
`$63,822.47` yazılır.

### Grafiğe çizim yapmak

Mum grafiğinin araç çubuğunda çizim araçları var: çizgi, serbest çizim,
dikdörtgen, daire ve silgi. İstediğiniz seviyeyi işaretleyip üzerine not
düşebilirsiniz — çizimler yalnızca tarayıcınızda tutulur, hiçbir yere
kaydedilmez.

Grafik saniyede bir kendini yenilediği için (fiyat hareket etsin diye),
çizim yaparken elinizin altında sabit durmasını isterseniz **"Grafiği
canlı tut"** anahtarını kapatın. Kapatınca grafik dondurulur, saniyelik
fiyat hareketi durur ama çizimleriniz silinmeden kalır. Coin ya da zaman
dilimi değiştirdiğinizde çizimler otomatik temizlenir.

Ayrıca mum gövdeleri daha kalın kenarlı çizilir, karışık dönemlerde
(çok sayıda küçük mum yan yana) hangi mumun nerede bittiğini ayırt etmek
kolaylaşsın diye.

---

## Sanal para ile kripto bot

Bu klasörde, **gerçek para kullanmayan** bir kripto alım-satım botu var.
Bot borsaya sadece "fiyat kaça?" diye sorar; alıp satma işlemleri
bilgisayarınızın içindeki hayali bir cüzdanda olur.

> Kod içinde hiçbir borsa şifresi / API anahtarı yok.
> Bu yüzden botun gerçek emir gönderme yetkisi **teknik olarak da yok**.

---

## Botu başlatmak

En kolay yol: **`calistir.bat`** dosyasına çift tıklayın.

Ya da terminalden:

```bash
.\.venv\Scripts\python.exe bot.py
```

Botu **durdurmak** için terminalde `Ctrl + C` tuşlarına basın.

---

## Klasörde ne var?

| Dosya | Ne işe yarar |
|---|---|
| `KaanTrade.vbs` | Uygulamayı pencere olarak başlatır (masaüstü kısayolu buna bağlı). |
| `masaustu.py` | Masaüstü penceresini açan kısım (pywebview). |
| `uygulama.py` | Panelin ekran kısmı (Streamlit) — 6 sayfa: Piyasa, Coin analizi, Analiz Botu, Sanal Trader, Karşılaştırma, Haberler. |
| `canli_veri.py` | WebSocket ile ~650 coinin anlık fiyatını hafızada tutan katman. |
| `grafikler.py` | Mum grafiği, korelasyon haritası, çubuk grafikler (plotly). |
| `gostergeler.py` | Gösterge matematiği: EMA, MACD, Stokastik, VWAP, Parabolic SAR, Fibonacci. |
| `analiz_botu.py` | Analiz Botu'nun gözlem fonksiyonları — tavsiye üretmeyen, ham gözlem döndüren saf Python. |
| `desenler.py` | Swing noktaları, Order Block, Fair Value Gap tespiti (saf geometri). |
| `strateji_desenleri.py` | SFP/OB/FVG/Destek-Direnç desenlerinin pozisyon-tabanlı strateji hali. |
| `sanal_trader.py` | Çoklu strateji, otomatik rotasyonlu sanal alım-satım motoru (bkz. "Sanal Trader" bölümü). |
| `tarama_desenler.py` | Yeni desen stratejilerini rastgele-kontrol-grubuyla doğrular. |
| `calistir_sanal_trader.bat` | Çift tıklayınca Sanal Trader'ı başlatan kısayol. |
| `.github/workflows/sanal_trader.yml` | GitHub Actions: bilgisayar kapalıyken saatte bir otomatik çalıştırır. |
| `requirements-sanal-trader.txt` | Sadece Sanal Trader'ın (GitHub Actions gibi başsız ortamlarda) ihtiyaç duyduğu dar kütüphane listesi. |
| `.gitignore` | Git'e hangi dosyaların gönderilmeyeceği (sanal ortam, indirilen veri vb.). |
| `haberler.py` | 9 kaynaktan RSS ile haber toplama, coin etiketleme. |
| `veri_kaynaklari.py` | Yavaş değişen veriler (CoinGecko, korku endeksi, fonlama). |
| `uygulamayi_baslat.bat` | Paneli tarayıcıda açar (hata ayıklamak için). |
| `.streamlit/config.toml` | Görünüm ayarları: koyu tema, port, menü. |
| `kaantrade.ico` | Uygulamanın ikonu. |
| `bot.py` | Canlı sanal bot. Ayarlar en üstte. |
| `geriye_donuk_test.py` | "Bu strateji son 2 yılda ne yapardı?" testi. |
| `dogrulama.py` | Çok coinli, eğitim/test bölmeli doğrulama. |
| `stratejiler.py` | 16 stratejinin kütüphanesi + rastgele kontrol grubu. |
| `tarama.py` | Bütün stratejileri bütün coinlerde tarar, şansla kıyaslar. |
| `veri_indir.py` | Borsadan uzun geçmiş veri indirip diske kaydeder. |
| `calistir.bat` | Çift tıklayınca botu başlatan kısayol. |
| `requirements.txt` | Projenin ihtiyaç duyduğu kütüphanelerin listesi. |
| `.venv/` | "Alet çantası" — kurduğumuz kütüphaneler burada durur. Dokunmanıza gerek yok. |
| `veri/` | İndirilen geçmiş fiyat verisi. Silinirse yeniden indirilir. |
| `cuzdan.json` | Bot çalışınca oluşur. Sanal paranızın son hali. |
| `islemler.csv` | Bot çalışınca oluşur. Canlı sanal işlemlerin listesi. |
| `cikti/test_islemleri.csv` | Test çalışınca oluşur. Geçmişte yapılan işlemler. |
| `cikti/test_grafik.png` | Test çalışınca oluşur. Fiyat ve portföy grafiği. |
| `cikti/sanal_trader/` | Sanal Trader çalışınca oluşur: cüzdan, işlem ve rotasyon geçmişi. |

---

## Ayarları değiştirmek

`bot.py` dosyasını açın, en üstteki `AYARLAR` bölümünü bulun:

```python
AYARLAR = {
    "borsa": "binance",
    "sembol": "BTC/USDT",
    "zaman_dilimi": "1h",
    ...
}
```

Sık değiştirilenler:

- **`sembol`** — İzlenecek coin. Örnek: `"ETH/USDT"`, `"SOL/USDT"`
- **`zaman_dilimi`** — Mum uzunluğu: `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"4h"`, `"1d"`
- **`baslangic_bakiye`** — Kaç sanal dolarla başlanacağı
- **`dongu_saniye`** — Bot kaç saniyede bir fiyata baksın

> **İpucu:** Botun çalıştığını hızlı görmek için `zaman_dilimi` değerini
> `"5m"`, `dongu_saniye` değerini `30` yapabilirsiniz. Daha sık sinyal üretir.

Ayarları değiştirdikten sonra botu durdurup yeniden başlatın.

---

## Bot ne yapıyor? (Strateji)

Kullandığımız yöntemin adı **hareketli ortalama kesişmesi**. Mantığı şu:

- **Hızlı ortalama** = son 10 mumun ortalama fiyatı → çabuk tepki verir
- **Yavaş ortalama** = son 30 mumun ortalama fiyatı → ağır hareket eder

Kural:

- Hızlı ortalama yavaşı **yukarı** keserse → yükseliş başlıyor olabilir → **AL**
- Hızlı ortalama yavaşı **aşağı** keserse → düşüş başlıyor olabilir → **SAT**
- Kesişme yoksa → **BEKLE**

Bot her turda ekrana şunu yazar: o anki fiyat, üretilen sinyal, sinyalin
sebebi, cüzdanın son hali ve baştan bu yana yüzde kaç kâr/zarar olduğu.

---

## Geriye dönük test (backtest)

Stratejiyi canlı beklemeden ölçmek için:

```bash
.\.venv\Scripts\python.exe geriye_donuk_test.py
```

Ne yapar: son 2 yılın saatlik verisinde stratejiyi baştan sona çalıştırır,
sonuçları ekrana yazar, işlemleri `cikti/test_islemleri.csv` dosyasına ve
grafiği `cikti/test_grafik.png` dosyasına kaydeder (klasör yoksa otomatik
oluşturulur). Ayrıca 33 farklı ortalama kombinasyonunu dener.

### 25 Temmuz 2026 tarihli ilk sonuç

| Ölçüt | Sonuç |
|---|---|
| Strateji getirisi (10/30) | **−48.77 %** |
| Hiç işlem yapmasaydınız | −0.99 % |
| Ödenen komisyon | 541 USDT (başlangıç 1000 USDT) |
| Kazanma oranı | 30.1 % (342 işlemin 103'ü kârlı) |
| En büyük düşüş | −60.83 % |

**Komisyon sıfır olsaydı sonuç −1.86 % olurdu.** Yani kaybın neredeyse
tamamı stratejinin kötü tahmin yapmasından değil, çok sık işlem yapıp
her seferinde komisyon ödemesinden geliyor.

Her turda ortalama −0.18 % kaybediliyor; bu küçük eksi 342 kez üst üste
çarpıldığında paranın yarısı gidiyor.

### Parametre taraması ne gösterdi?

Veri ikiye bölünüyor: ilk %70 "eğitim", son %30 "test". En iyi ayar
eğitimde aranıyor, sonra hiç bakılmamış test verisinde deneniyor.

| Ayar | Eğitim getirisi | Test getirisi |
|---|---|---|
| 20/100 | +24.44 % | −25.99 % |
| 15/100 | +16.18 % | −17.87 % |
| 30/100 | +11.06 % | −26.59 % |

Eğitimde en iyi görünen ayar test verisinde para kaybetti. Buna **aşırı
uydurma** deniyor: yeterince çok kombinasyon denerseniz geçmişte harika
görünen bir ayarı mutlaka bulursunuz, ama bu yetenek değil tesadüftür.

Bu yüzden bir stratejiye güvenmenin tek yolu, onu **hiç görmediği** veride
denemektir. Bu proje bunu otomatik yapıyor.

---

## Doğrulama aracı

```bash
.\.venv\Scripts\python.exe dogrulama.py
```

Aynı kuralı üç coinde (BTC, ETH, SOL) ve dört ayarda birden dener, her
birinde veriyi eğitim/test olarak ikiye böler. Amacı tek bir parlak sayıya
kanmayı önlemek.

### Ne bulduk?

Saatlik 10/30 kesişmesi para kaybediyor çünkü çok sık işlem yapıyor.
Çözüm yönü: **daha seyrek işlem**. Günlük mumlarda "fiyat hareketli
ortalamanın üzerindeyse pozisyonda kal" kuralı 342 yerine 23 işlem yapıyor.

Hiç bakılmamış test verisinde, 12 durumun **12'sinde**:

- en büyük düşüş azaldı (örnek: BTC −39.53 % → −14.01 %)
- getiri al-ve-tut'u geçti

### Ama bu kanıt değil

Test dönemi (2025-12 / 2026-07) üç coinde de **düşüşle** geçti. Düşen bir
piyasada "nakite kaç" diyen *her* kural iyi görünür. Yani gördüğümüz şey
öngörü yeteneği değil, sadece **daha az piyasada kalmak**.

Trend filtrelerinin bilinen zayıflığı yükselen piyasalarda ortaya çıkar:
fiyat ortalamanın etrafında gezinirken sizi sürekli girip çıkartır ve
komisyon yedirir. Elimizdeki 2 yıllık veride güçlü ve uzun bir yükseliş
dönemi olmadığı için **bu zayıflığı test edemiyoruz**. Bunun için daha
eski veri (örneğin 2020-2021) indirmek gerekir.

### Güvenilir olan tek bulgu

Getiri sayıları ayar değiştikçe çok oynuyor (ETH'de eğitimde +101 %, testte
−6 %). Oynayan sayılara güvenilmez. Ama **düşüş azalması** hem üç coinde
hem dört ayarda tutarlı çıktı. Tutarlılık, yüksek sayıdan daha değerlidir.

Yani bu kural bir kâr aracı değil, bir **risk azaltma** aracı olarak
anlamlı görünüyor.

---

## Strateji taraması

```bash
.\.venv\Scripts\python.exe tarama.py
```

16 stratejiyi 10 coinde, 6 yıllık günlük veride (2020-07 / 2026-07, yani
2021 yükselişi de dahil) test eder ve hepsini **rastgele karar veren bir
kontrol grubuyla** karşılaştırır.

### Kontrol grubu neden en önemli parça?

`stratejiler.py` içindeki `rastgele` fonksiyonu para atarak karar verir.
200 farklı denemeyle bir "şans dağılımı" çıkarıyoruz. Sonra her gerçek
stratejiye soruyoruz: bu dağılımın neresindesin?

İlaç denemelerindeki şeker hapı (placebo) ne işe yararsa bu da onu yapar.
Bir strateji rastgeleyi geçemiyorsa hiçbir şey bilmiyor demektir.

### 25 Temmuz 2026 sonucu

| Strateji | TEST getirisi | Rastgeleyi geçme | Piyasada |
|---|---|---|---|
| SMA trend 100 | +33.7 % | 83 % | 40 % |
| SMA trend 50 | +27.1 % | 78 % | 43 % |
| Donchian 55/20 | +17.8 % | 73 % | 29 % |
| Momentum 90 | +17.6 % | 73 % | 40 % |
| MA kesişme 20/100 | +16.8 % | 72 % | 42 % |
| **al ve tut** | −23.2 % | 40 % | 100 % |
| MACD | −35.8 % | 24 % | 52 % |
| **RASTGELE (kontrol)** | **−10.5 %** | — | ~50 % |

**Hiçbir strateji %95 eşiğini geçemedi.** En iyisi %83'te kaldı. Yani
16 stratejinin hiçbiri, getiri açısından para atmaktan ayırt edilemiyor.

### En çarpıcı bulgu

Rastgele kontrol grubu **−10.5 %** yaptı, al-ve-tut **−23.2 %**. Yani
para atarak karar vermek, Bitcoin'i elde tutmaktan daha iyi sonuç verdi.
Rastgele, coinlerin 7'sinde al-ve-tut'u geçti.

Sebep basit: rastgele strateji zamanın ancak yarısında piyasadaydı ve bu
dönem düşüşle geçti. **Düşen piyasada az piyasada kalmak, tek başına
yeterlidir.** Beceriye gerek yok.

Bu bulgu, bu README'nin bir üst bölümündeki "trend filtresi 12/12 durumda
al-ve-tut'u geçti" sonucunu geçersiz kılıyor. O sonuç gerçekti ama sebebi
stratejinin zekâsı değil, sadece daha az piyasada kalmasıydı. Kontrol
grubu olmadan bunu göremezdik. **Kontrol grubu kullanmamanın bedeli budur.**

### Aracın yakaladığı sahte kazanan

RSI 20/50 düşüş testini %100 ile geçmiş görünüyor (−11.0 %). Ama
"piyasada" sütunu **%7** diyor — medyan 2 işlem. Yani neredeyse hep
nakitte oturdu. Nakitte oturmanın düşüşü olmaz; bu bir yetenek değil,
ölçünün kandırılması. `tarama.py` bunu otomatik yakalayıp eliyor.

Bu yüzden tabloda **her zaman "piyasada" sütununa bakın.**

---

## Sanal Trader (çoklu pozisyon, otomatik rotasyon)

`sanal_trader.py`, TEK bir sanal PORTFÖYLE, geniş bir likit-coin evreninde
AYNI ANDA BİRDEN FAZLA pozisyon tutabilen bir motor. Bilgisayar açıkken
bağımsız bir arka plan süreci olarak 7/24 çalışır — `calistir_sanal_trader
.bat` ile başlatılır, kendi WebSocket bağlantısını kurar (panelden
bağımsız); panelin "Sanal Trader" sayfası onun yazdığı dosyaları okuyup
gösterir (sayfa/coin değiştirdiğinizde ya da "Yenile" düğmesiyle
tazelenir, fiyatlar ise panelin KENDİ canlı bağlantısından anlık gelir).

**Coin evreni** (varsayılan, `AYARLAR`'dan değiştirilebilir): canlı
piyasadaki TÜM USDT çiftlerinden, en az $5M 24 saatlik hacmi olan en
likit 40 coin — yani sadece BTC/ETH değil, **altcoinler de** dahil.
Stabilcoin çiftleri (USDC/USDT gibi, fiyatça neredeyse hiç oynamıyor)
bilerek dışarıda tutulur.

**Aynı anda en fazla 8 pozisyon.** Yeni bir pozisyon açılırken, o andaki
kullanılabilir nakit kalan boş pozisyon yeri sayısına eşit bölünür
(basit eşit-ağırlık). Var olan pozisyonlar bu yüzden sürekli yeniden
dengelenmez — sadece yeni girişlerde büyüklük belirlenir.

**Zaman dilimi:** SAATLİK mumlar (günlük değil) — sinyaller ve dolayısıyla
işlemler çok daha sık üretilsin diye. Bu "daha sık işlem = daha iyi"
anlamına gelmez; sadece "sürekli çalıştığını görebilme" isteğini
karşılamak için bilinçli bir tercih.

**Nasıl çalışır:**
1. HER döngüde (varsayılan saatte bir — yeni saatlik mumla aynı anda;
   daha sık olması ANLAMSIZ, çünkü veri de o hızda değişiyor, "sürekli/
   her an" isteğini verinin izin verdiği en anlamlı hızda karşılıyoruz)
   o anki likit evrendeki HER coin için, HANGİ stratejinin (16 klasik +
   SFP/Order Block/Fair Value Gap/Destek-Direnç kırılması) o coinde en
   iyi performans gösterdiğini son 30 günlük (saatlik) veriyle ölçer —
   16 stratejiyi test ettiğimiz AYNI motorla (`dogrulama.simule_et`).
   Her coin kendi "en iyi" stratejisine atanır; atamalar VE o coin için
   en iyi 5 aday `cikti/sanal_trader/rotasyon_gunlugu.csv`'ye yazılır —
   hangi kararın neden verildiği her zaman denetlenebilir.
2. Bu atama SADECE YENİ AÇILACAK pozisyonlar için geçerlidir — halihazırda
   AÇIK bir pozisyon, rotasyon başka bir strateji daha iyi çıkarsa bile
   kendi AÇILDIĞI stratejinin sinyaline göre yönetilmeye devam eder (saatte
   bir yeniden atama yapılırken açık bir pozisyonun ortasında strateji
   değiştirmek tutarsız olurdu). Atanmış ama henüz pozisyon AÇILMAMIŞ her
   coin için GÜNCEL (saatlik) sinyale bakılır: sinyal "içerde" ise ve boş
   pozisyon yeri varsa AL, sinyal "dışarda" ise ve o coin elimizdeyse
   SAT. Böylece birden fazla coin, birbirinden bağımsız olarak, AYNI
   ANDA pozisyonda olabilir.
3. Elde tutulan ama sonraki rotasyonda evrenden düşen bir coin (hacmi
   azaldıysa vb.) "yetim" kalmaz — eski stratejisiyle izlenmeye devam
   eder, sadece yeni giriş için aday olmaktan çıkar.

**Panelde canlı grafik ve pozisyon tablosu:** "Sanal Trader" sayfası, o
an açık HER pozisyonu (coin, strateji, giriş/güncel fiyat, kâr/zarar %)
canlı fiyatlarla bir tabloda gösterir. Cüzdan-değeri grafiği de sadece
işlem anlarını birleştiren seyrek bir çizgi DEĞİL — `islemler.csv`'yi
baştan sona "oynatıp" her andaki AÇIK POZİSYONLARIN TAMAMINI saatlik
kapanış fiyatlarıyla toplayan, gerçekten sürekli bir eğridir; üzerinde
AL/SAT anları üçgen işaretleyicilerle görünür. (Sayfayı saniyede bir
OTOMATİK yenilemeyi de denedik, ama bu — Streamlit'in fragment
mekanizmasıyla ilgili bir kısıtlama yüzünden — sayfa geçişlerini
kilitleme riski taşıdığı için "Yenile" düğmesine geri dönüldü; veri
kendisi zaten sürekli/saatlik çözünürlükte, sadece ekran kendiliğinden
saniyede bir tetiklenmiyor.)

### Yeni desenler: SFP, Order Block, Fair Value Gap, Destek/Direnç kırılması

16 klasik stratejinin yanına, `desenler.py` + `strateji_desenleri.py` ile
4 yeni "desen" tabanlı strateji eklendi:

- **SFP (likidite avı)**: fiyatın önceki bir destek/direnç seviyesini
  fitille kırıp kapanışta geri dönmesi ("Swing Failure Pattern" / stop
  hunt / likidite süpürmesi).
- **Order Block**: güçlü bir hareketten hemen önceki son ters yönlü
  mumun bıraktığı bölge — bazı analistler burayı büyük (kurumsal)
  emirlerin biriktiği yer sayar.
- **Fair Value Gap**: 3 mumluk fiyat dengesizliği — güçlü tek yönlü bir
  hareket sırasında kimsenin işlem yapmadığı bir aralık kalması.
- **Destek/Direnç kırılması**: mevcut Donchian stratejisinden farklı
  olarak, rolling max/min yerine swing (fraktal) noktalarıyla bulunan
  "anlamlı" seviyeleri kullanır.

**ÖNEMLİ — bunların TEK bir evrensel tanımı yok.** "Order Block" ve
"Fair Value Gap" özellikle Smart Money Concepts / ICT camiasından gelen,
kaynaktan kaynağa değişen terimlerdir. `desenler.py`'de kullanılan
tanımlar yaygın anlatılan, makul birer versiyondur — "işe yaradıklarının
kanıtı" değildir. Bu yüzden panelde ("Analiz Botu" sayfasında,
tek-coin gözlem kartlarında) görünseler bile "bu bir tahmin değildir"
notuyla sunulurlar; sohbette bir coin hakkında sorduğunuzda ben de aynı
kodu kullanıp yorumlayabilirim.

### Doğrulama sonucu: bu desenler de rastgeleyi geçemedi

Canlı motora eklemeden önce, `tarama_desenler.py` ile AYNI
rastgele-kontrol-grubu yöntemiyle (10 coin, ~6 yıllık **GÜNLÜK** veri, 200
rastgele deneme, eğitim/test ayrımı) test edildiler. Sonuç, orijinal 16
stratejiyle birebir aynı desende:

| Strateji | Test getirisi | Rastgeleyi geçti mi (%95 eşiği) |
|---|---|---|
| Order Block | −4.5 % | Hayır (%57) |
| Fair Value Gap | −5.6 % | Hayır (%56) |
| SFP (likidite avı) | −10.6 % | Hayır (%50) |
| Destek/Direnç kırılması | −23.0 % | Hayır (%40) |
| **Rastgele (kontrol)** | −10.5 % | — |

Hiçbiri istatistiksel olarak rastgeleyi geçmedi. (Order Block ve FVG'nin
"düşüşü azaltma" oranı yüksek görünse de bu bir aldatmaca: piyasada
sadece %2 ve %15 zaman geçiriyorlar — yukarıdaki "sahte kazanan" bölümünde
anlatılan durumun aynısı.)

**Bilinen sınırlama:** Sanal Trader şu an SAATLİK mumlarla çalışıyor,
ama bu doğrulama GÜNLÜK mumlarla yapıldı — saatlik zaman diliminde ayrıca
doğrulanmadı. Panel bunu "Sanal Trader" sayfasının en üstündeki uyarıda
da açıkça belirtir. Bu sonucu çalıştırmak isterseniz:

```bash
.\.venv\Scripts\python.exe tarama_desenler.py
```

### Bu yüzden: Sanal Trader bir KÂR ARACI değil, bir GÖZLEM aracıdır

Sanal Trader'ın "en iyi performans gösteren"i seçmesi, o stratejinin
**gelecekte de** iyi gideceğinin garantisi DEĞİLDİR — sadece GEÇMİŞTE en
iyi performansı gösterenin seçildiği anlamına gelir ("yakın geçmişi
kovalama" / regime-chasing riski). Panelin kendisi de bunu her zaman,
her sayfada söyler.

Amacımız kâr garantisi değil: hangi stratejinin ne zaman öne çıktığını,
gerçek piyasa verisiyle ama SANAL parayla, şeffaf bir şekilde kaydetmek —
tam olarak istediğiniz "bu gerçekten işe yarıyor mu, ne kadar işe
yarıyor, dürüstçe görebileyim" sorusuna cevap vermek için.

### Bilgisayarınız kapalıyken de 7/24 çalışsın (GitHub Actions)

`calistir_sanal_trader.bat`, bilgisayarınız AÇIKKEN çalışır. Kapatırsanız
durur. Bilgisayarınız kapalıyken de sürekli çalışmasını istiyorsanız,
kodun GitHub'ın kendi (ücretsiz) sunucularında saatte bir otomatik
çalışmasını sağlayabilirsiniz — `.github/workflows/sanal_trader.yml`
bunun için hazır.

**Nasıl çalışır:** GitHub, deponuzu saatte bir (her saat 5. dakikada)
geçici bir sunucuda açar, `python sanal_trader.py --once` ile TEK bir
kontrol turu çalıştırır (rotasyon zamanıysa rotasyon da dahil), sonra
`cikti/sanal_trader/` içindeki güncellenmiş dosyaları (portföy, açık
pozisyonlar, işlem/rotasyon geçmişi) depoya geri kaydeder ve sunucuyu
kapatır. Panel bu depodan senkronize edilen dosyaları okur.

**Kurulum adımları:**
1. [github.com](https://github.com) üzerinde ücretsiz bir hesabınız
   yoksa oluşturun.
2. Yeni, **herkese açık (public)** bir depo (repository) oluşturun
   (isim serbest, örn. `kaan-trade`). **Neden public:** GitHub Actions
   dakikaları public depolarda tamamen ücretsiz/sınırsızdır; private
   depolarda aylık 2.000 dakikayla sınırlıdır ve bu sistemin saatlik
   taraması (40 coin × 19 strateji) bu sınırı aşar. Depoda hiçbir API
   anahtarı, şifre ya da kişisel bilgi YOK — sadece kod ve sanal
   (gerçek olmayan) işlem sonuçları paylaşılır.
3. Depoyu oluşturduktan sonra GitHub'ın size gösterdiği adresi
   (`https://github.com/kullanici-adiniz/depo-adi.git`) bana verin,
   ben projeyi oraya göndereyim (push edeyim).
4. Depo ayarlarında (Settings → Actions → General → Workflow
   permissions) **"Read and write permissions"** seçeneğinin işaretli
   olduğundan emin olun — GitHub Actions'ın sonuçları depoya geri
   yazabilmesi için gerekli.
5. Bu kadar — Actions sekmesinden saatte bir otomatik çalıştığını
   görebilirsiniz, ya da "Run workflow" ile hemen elle tetikleyebilirsiniz.

**Sınırlama:** Panel (Streamlit uygulaması) hâlâ sizin bilgisayarınızda
çalışır — bu adım sadece `sanal_trader.py`'yi bilgisayarınızdan
bağımsızlaştırır. Paneli görmek istediğinizde bilgisayarınızı açıp
`git pull` ile en güncel sonuçları indirmeniz (ya da uygulamayı
açmanız) yeterli; panel kendisi 7/24 açık kalmaz, sadece veriler
GitHub'da birikir.

### Sanal Trader'ı sıfırlamak istersem?

Yerel `cikti/sanal_trader/` klasörünü silin. GitHub Actions
kullanıyorsanız, depodaki `cikti/sanal_trader/` klasörünü de silip
commit'leyin. Bir sonraki çalıştırmada `baslangic_bakiye` ile yeniden
başlar.

---

## Sıfırdan başlamak istersem?

`cuzdan.json` ve `islemler.csv` dosyalarını silin. Bot bir sonraki
açılışta yeniden `baslangic_bakiye` ile başlar.

---

## Önemli uyarı

Bu proje **öğrenme amaçlıdır, yatırım tavsiyesi değildir.**

Buradaki basit ortalama stratejisi yatay (kararsız) piyasalarda çok sık
hatalı sinyal üretir ve komisyonlar yüzünden para kaybettirebilir. Sanal
testte iyi görünen bir sonuç, gerçek piyasada aynı sonucu vereceğinin
garantisi **değildir** — gerçek işlemde slipaj, emir gecikmesi ve likidite
gibi burada hiç simüle edilmeyen etkenler devreye girer.

Gerçek para ile işlem yapmayı düşünüyorsanız, önce lisanslı bir finansal
danışmana başvurun.
