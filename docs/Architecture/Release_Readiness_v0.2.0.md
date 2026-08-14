# Hypatia Release Readiness — v0.2.0 sonrası durum

Tarih: 15 Ağustos 2026
Kapsam: yerel çalışma ağacı ve `origin/main` ile aynı olan `HEAD` (`1d07abb`)

## Karar

**Yeni bir release, tag veya push için henüz onay yok.**

Kalite kontrolleri geçmektedir; ancak release kimliği ve commit kapsamı
belirsizdir. Bu belge, çalışır durumdaki geliştirmeyi yayınlanabilir bir sürüm
sanmamak için hazırlanmıştır.

## Kanıtlanan durum

| Kontrol | Sonuç |
| --- | --- |
| Runtime sürümü (`src/core/Version.py`) | `0.2.0` |
| Paket sürümü (`pyproject.toml`) | `0.2.0` |
| En son `v0.2.0` tag'i | `955bc2d8dc3f2b1be92d1cc3f05241102a869b98` |
| Güncel `HEAD` | `1d07abb` |
| `v0.2.0` sonrasındaki commit sayısı | 233 |
| Remote eşitliği | Yerel `HEAD`, `origin/main` ile aynı |

Bu nedenle `0.2.0` etiketi, güncel ana dalın içeriğini temsil etmez. Yeni
sürüm adı ve sürüm kapsamı belirlenmeden sürüm numarası değiştirilmemelidir.

## Yerel değişikliklerin kapsamı

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

## Son doğrulama

15 Ağustos 2026 tarihinde yerel sanal ortam ile aşağıdaki denetimler geçti:

```text
python -m unittest discover -s tests -t .  -> 802 test, OK
black --check src tests                    -> 208 dosya değişmeden kalır
ruff check src tests                       -> başarılı
mypy src tests                             -> 208 kaynak dosyada hata yok
git diff --check                           -> başarılı
```

Bu sonuçlar, yerel birleşik çalışma ağacının teknik kalite sinyalidir; tek
başına release sürümü veya commit kapsamı onayı değildir.

## Release öncesi gerekli kararlar

1. Hedef sürüm adını ve hangi sprintlerin o sürüme gireceğini tanımla.
2. Ranked-selector top-k çalışmasını semantik bellek çalışmasından ayrı bir
   commit sınırına ayır veya bilinçli olarak aynı sürüme dahil et.
3. Sürüm, changelog ve release notlarını seçilen kapsama göre güncelle.
4. Aynı kalite kapılarını temiz bir çalışma ağacında yeniden çalıştır.
5. Ancak bundan sonra commit, push ve tag işlemlerini planla.

## Bu denetimin dışında kalanlar

Bu belge GitHub'a hiçbir değişiklik göndermez, tag oluşturmaz ve sürüm numarası
değiştirmez.
