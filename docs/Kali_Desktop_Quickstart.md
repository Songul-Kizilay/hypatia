# Kali panelini kullanma

Hypatia v0.3.319, kayıtlı program kapsamları bulunan masaüstü kurulumlarında
**Kali** sekmesini gösterir. İki işlem vardır: `dig` ile DNS kaydı sorgulama ve
`curl` ile HTTPS yanıt başlıklarını okuma.

1. **Kapsamları yenile** düğmesine bas. Etkin, kayıtlı program kapsamını seç.
   Liste boşsa Research (Advanced) içindeki Target program formundan kapsam
   kaydet. Programın işlem politikası seçtiğin kontrole izin vermelidir;
   HTTPS başlıkları için HTTPS kontrolü ve 443 portu gerekir.
2. Kapsam içindeki alan adını yaz ve işlem türünü seç. DNS için A, AAAA veya
   CNAME seçebilirsin; HTTPS işleminde bu alan devre dışıdır.
3. **Önizle** düğmesi çalıştırılacak işlemi ve sınırlarını gösterir.
4. **Onayla** düğmesi ayrı bir onay sorar ve tam önizlemeye bağlı izin kaydeder.
5. **Çalıştır** düğmesi ağ isteği başlamadan önce ayrıca onay sorar.
   Çalışma arka plandaki masaüstü işçisiyle yürür; sonuç aynı panelde görünür.

Hedefi, kapsamı veya işlem türünü değiştirirsen yeniden önizleme ve onay gerekir.
İzin tek kullanım içindir. Sonuç, incelemen için gösterilir ve kendiliğinden
kanıt, bulgu veya hafıza kaydına dönüşmez.

Gerçek çalıştırma için Windows üzerinde `kali-linux` adlı WSL dağıtımı ve seçilen
aracın (`/usr/bin/dig` veya `/usr/bin/curl`) kurulu olması gerekir. Hypatia
başlatılırken mevcut `HYPATIA_KALI_OPERATION_EXECUTION_ENABLED=true` ayarı da
etkin olmalıdır. Panelin görünmesi tek başına çalıştırma özelliğinin etkin
olduğunu göstermez; runtime koşulları sağlanmazsa uygulama gerekçeyi gösterir.

Bu sürümün doğrulaması sahte işlem adaptörleriyle yapılmıştır; bir bug bounty
hedefine canlı istek gönderilmemiştir.
