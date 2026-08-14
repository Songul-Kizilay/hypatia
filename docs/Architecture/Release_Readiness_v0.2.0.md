# Historical Release Readiness — v0.2.0 sonrası durum

Tarih: 15 Ağustos 2026
Bu belge 15 Ağustos 2026 tarihinde, PR #238 merge edilmeden önceki durumu
kaydeder. Tarihsel denetim kapsamındaki `HEAD`, `1d07abb` idi.

## Karar

**PR #238 daha sonra `main`e merge edildi; yeni bir release veya tag henüz
oluşturulmadı.**

Kalite kontrolleri geçmişti; ancak release kimliği ve commit kapsamı
belirsizdi. Bu belge, çalışır durumdaki geliştirmeyi yayınlanabilir bir sürüm
sanmamak için hazırlanmıştır. Runtime ve paket sürümü güncel `main` üzerinde
hâlâ `0.2.0` olduğundan, release kimliği borcu devam eder.

## Kanıtlanan durum

| Kontrol | Sonuç |
| --- | --- |
| Runtime sürümü (`src/core/Version.py`) | `0.2.0` |
| Paket sürümü (`pyproject.toml`) | `0.2.0` |
| En son `v0.2.0` tag'i | `955bc2d8dc3f2b1be92d1cc3f05241102a869b98` |
| Tarihsel denetim `HEAD` | `1d07abb` |
| Güncel `main` | `1dabe7884c8415c98ff3dda624a8524df216520d` (PR #238 merge) |
| Güncel `v0.2.0` sonrasındaki commit sayısı | 236 |
| Güncel remote eşitliği | Yerel `main`, `origin/main` ile aynı |

Bu nedenle `0.2.0` etiketi, güncel ana dalın içeriğini temsil etmez. Yeni
sürüm adı ve sürüm kapsamı belirlenmeden sürüm numarası veya tag
oluşturulmamalıdır.

## Tarihsel yerel değişiklik kapsamı

Çalışma ağacı tek bir değişiklikten oluşmamaktadır:

1. Semantik bellek temeli: embedding değer nesnesi, indeks, Ollama adaptörü,
   opt-in runtime ve `semantic recall <sorgu>` geri dönüş yolu.
2. Kalite altyapısı: tüm test alt dizinlerinin keşfedilmesi ve MyPy paket
   yapılandırması.
3. Dokümantasyon: Architecture Audit v0.1, kullanım kılavuzu, durum ve
   changelog güncellemeleri.
4. Önceden mevcut yerel çalışma: ranked learned-memory selector için top-k
   ortam değişkeni ve ilgili entegrasyon testleri.

Özellikle `src/core/Bootstrap.py` hem ranked-selector top-k kodunu hem de
semantik bellek bağlantısını içerir. Bu dosya parçalı olarak hazırlanmadıkça,
tek bir commit iki bağımsız sprinti karıştırır.

## Tarihsel doğrulama

15 Ağustos 2026 tarihinde yerel sanal ortam ile aşağıdaki denetimler geçti:

```text
python -m unittest discover -s tests -t .  -> 805 test, OK
black --check src tests                    -> 208 dosya değişmeden kalır
ruff check src tests                       -> başarılı
mypy src tests                             -> 208 kaynak dosyada hata yok
git diff --check                           -> başarılı
```

Bu sonuçlar, yerel birleşik çalışma ağacının teknik kalite sinyalidir; tek
başına release sürümü veya commit kapsamı onayı değildir.

## Release için hâlâ gerekli kararlar

1. Hedef sürüm adını ve hangi sprintlerin o sürüme gireceğini tanımla.
2. Ranked-selector top-k çalışmasını semantik bellek çalışmasından ayrı bir
   commit sınırına ayır veya bilinçli olarak aynı sürüme dahil et.
3. Sürüm, changelog ve release notlarını seçilen kapsama göre güncelle.
4. Aynı kalite kapılarını temiz bir çalışma ağacında yeniden çalıştır.
5. Ancak bundan sonra commit, push ve tag işlemlerini planla.

## Bu denetimin kapsamı dışında kalanlar

Bu belge GitHub'a hiçbir değişiklik göndermez, tag oluşturmaz ve sürüm numarası
değiştirmez. PR #238'ün merge edilmesi yalnızca doğrulanmış kodun `main`e
alındığını gösterir; bağımsız bir release kararı değildir.
