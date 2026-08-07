# orderTypeId katalogi — Urganch Aqlli shahar

Ushbu hujjat `orderType.csv` faylining Knowledge Base uchun Markdown ko'rinishidagi kanonik nusxasidir. ID'lar ichki texnik qiymat bo'lib, fuqaroga ovoz chiqarib aytilmaydi.

## Tanlash qoidasi

- Agent muammo mazmunini tinglab, eng mos bitta yozuvni tanlaydi.
- Muammo ikki turga teng darajada mos kelsa, bitta aniqlashtiruvchi savol beradi.
- Katalogda aniq moslik bo'lmasa, `57683` — **Boshqa turdagi masalalar** faqat muammo haqiqatan ham boshqa toifaga kirishi aniq bo'lganda tanlanadi; noaniqlikni yashirish uchun ishlatilmaydi.
- Tanlangan ID faqat webhook payload'iga yuboriladi. Fuqaroga tashkilot nomi va keyingi qadam tushuntiriladi.

## Kanonik yozuvlar

### Issiqlik masalasi
- `orderTypeId`: `46415`
- Qidiruv iboralari: isitish ishlamayapti, issiqlik yo'q, radiator sovuq, issiq ta'minoti, isitish mavsumi.

### Boshqa turdagi masalalar
- `orderTypeId`: `57683`
- Qidiruv iboralari: ro'yxatdagi toifalarga kirmaydigan alohida xizmat masalasi.
- Eslatma: muammo turi noaniq bo'lsa, avval aniqlashtiruvchi savol beriladi.

### BSK masalasi
- `orderTypeId`: `31344`
- Qidiruv iboralari: BSK, boshqaruv servis kompaniyasi, uy-joy boshqaruvi, pod'ezd, tom, umumiy uy ta'miri.

### Toza hudud masalasi
- `orderTypeId`: `31363`
- Qidiruv iboralari: chiqindi olib ketilmayapti, axlat, konteyner, sanitariya tozaligi, toza hudud.

### Suv masalasi
- `orderTypeId`: `31274`
- Qidiruv iboralari: ichimlik suvi, sovuq suv, suv kelmayapti, suv bosimi, quvurdan suv sizishi.

### Bandlik masalasi
- `orderTypeId`: `31345`
- Qidiruv iboralari: ish topish, ishsizlik, bandlik, kasbga joylashish, bo'sh ish o'rni.

### Elektr masalasi
- `orderTypeId`: `31342`
- Qidiruv iboralari: elektr yo'q, svet o'chdi, tok, kuchlanish, elektr tarmog'i.

### MSP tozalanmagan
- `orderTypeId`: `31352`
- Qidiruv iboralari: MSP tozalanmagan.
- Eslatma: “MSP” manba tizimidagi toifa nomi. Fuqaro bu qisqartmani boshqa ma'noda ishlatsa, avval bir savol bilan aniqlashtiring.

### Nasos masalasi
- `orderTypeId`: `31346`
- Qidiruv iboralari: nasos ishlamayapti, suv nasosi, bosim nasosi, nasos buzilgan.

### Gaz masalasi
- `orderTypeId`: `31343`
- Qidiruv iboralari: gaz yo'q, tabiiy gaz, gaz bosimi, gaz quvuri, gaz sizishi haqida xavfsiz murojaat.
- Eslatma: favqulodda xavf bo'lsa, agent oddiy ariza oqimini cho'zmaydi va tegishli favqulodda xizmatga qo'ng'iroq qilishni tavsiya qiladi.

### Obodonlashtirish
- `orderTypeId`: `41818`
- Qidiruv iboralari: ko'cha obodonchiligi, daraxt, yo'l cheti, hududni tartibga keltirish, ko'kalamzorlashtirish.

### Avtobus masalasi
- `orderTypeId`: `64401`
- Qidiruv iboralari: avtobus kelmayapti, yo'nalish, bekat, jamoat transporti, avtobus jadvali.

## Texnik xavfsizlik

- ID raqamini taxmin qilmang va katalogda yo'q yangi ID yaratmang.
- Fuqaro ID raqamini aytishi shart emas.
- Server qabul qilganda ham ID va muammo toifasini qayta tekshirsin.
