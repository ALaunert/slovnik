# Письменный пилот: пакет для решения владельца

Статус включения: `approved`.

Это внутренняя модельная проверка по источникам, не независимая языковая экспертиза.
Пакет не загружается в приложение. Неперечисленный ответ: `unresolved`.

## a1-written-location-library · revision 1

A1.LOCATION_INFO · practice · `location-library-practice`

### Контекст и задание

Вымышленная учебная группа раньше встречалась в библиотеке. Сегодня место изменено: школа. Знакомый спрашивает: «Где је састанак?»

Ответьте коротким сообщением и назовите сегодняшнее место встречи. Укажите встречу, а не собственное местоположение.

### Текст / образец ответа

```text
Састанак је у школи.
```

Русский смысл: Встреча проходит в школе.

Допустимые ответы: ["Састанак је у школи."]

Политика ответа: {"equivalent_script_answers": ["Sastanak je u školi."], "id": "a1-written-location-library-answers", "normalization": ["NFC", "trim"], "revision": 1, "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Ясный референт встречи; je после подлежащего, место u školi сверено в двух описаниях.
- **target_alignment:** Сообщение об изменённом месте, а не изолированное «здесь» без референта.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Sastanak je u školi. — эквивалентное письмо. U školi. и иной порядок оставлены unresolved.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://www.studyserbian.com/proba/grammar/nouns_locative_case.asp (Table 1, u/na for location); https://leda.cz/download/LedaCz-Srbstina-nejen-pro-samouky-ukazka-7808.pdf#page=6 (u školi); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=3 (biti); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=177 (sastanak in lexical definition)
- **Разногласия/исключения:** []

Content hash: `a937c2926f60ddfb6209bbbdf526ee89ee0858346ff08da1db61229a77387e07`.

## a1-written-location-office · revision 1

A1.LOCATION_INFO · assessment · `location-office-holdout`

### Контекст и задание

Вымышленный офис прислал план: sastanak / hotel / 18:00; ručak / škola / 13:00. Коллега спрашивает: «Gde je sastanak?»

Напишите одно сообщение с местом встречи по плану. Не отвечайте, где обед, и не описывайте маршрут.

### Текст / образец ответа

```text
Sastanak je u hotelu.
```

Русский смысл: Встреча проходит в гостинице.

Допустимые ответы: ["Sastanak je u hotelu."]

Политика ответа: {"equivalent_script_answers": ["Састанак је у хотелу."], "id": "a1-written-location-office-answers", "normalization": ["NFC", "trim"], "revision": 1, "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Одна ограниченная формула состояния; hotelu следует проверенному регулярному образцу.
- **target_alignment:** Два события в плане, требуется выбрать место встречи; это не замена существительного в тренировочном промпте.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Састанак је у хотелу. — эквивалентное письмо. Сообщения со временем и свободные перефразирования unresolved.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://www.studyserbian.com/proba/grammar/nouns_locative_case.asp (Table 1, masculine locative -u; location with u); https://leda.cz/download/LedaCz-Srbstina-nejen-pro-samouky-ukazka-7808.pdf#page=6 (biti with u); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=9 (hotel); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=177 (sastanak in lexical definition)
- **Разногласия/исключения:** []

Content hash: `0945b8916eb6498a0556f454f733be15317c3682c2bc790ae5aaa37c9446b556`.

## a1-written-personal-profile · revision 1

A1.PERSONAL_DETAILS · practice · `personal-profile-practice`

### Контекст и задание

Вымышленная карточка участника: Nina Pavlović · Niš. Нужно оформить профиль клуба.
Поля профиля: Име / Презиме / Град.

Заполните три поля данными карточки; это не ваши личные данные. Можно последовательно использовать кириллицу или латиницу.

### Текст / образец ответа

```text
Име: Нина
Презиме: Павловић
Град: Ниш
```

Русский смысл: Имя: Нина; фамилия: Павлович; город: Ниш.

Допустимые ответы: ["Име: Нина\nПрезиме: Павловић\nГрад: Ниш"]

Политика ответа: {"absent_field": "missing", "fields": {"grad": ["Ниш", "Niš"], "ime": ["Нина", "Nina"], "prezime": ["Павловић", "Pavlović"]}, "id": "a1-written-personal-profile-answers", "normalization": ["NFC", "trim"], "revision": 1, "scoring": "per_field", "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Краткие подписи полей, не обрывок предложения; вымышленное имя не является данными реального человека.
- **target_alignment:** Три соответствия поле–значение; отдельная оценка поля, не генерация свободной автобиографии.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Нина/Nina, Павловић/Pavlović, Ниш/Niš сверены по алфавиту. Порядок полей не влияет на смысл.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=4 (alphabet); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=174 (grad); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=175 (ime); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=189 (prezime)
- **Разногласия/исключения:** []

Content hash: `425108ba8aff5c55e78d6f1b919c617afd9d343307a7a97734ec6345a25e0ed9`.

## a1-written-personal-registration · revision 1

A1.PERSONAL_DETAILS · assessment · `personal-registration-holdout`

### Контекст и задание

Вымышленное сообщение для регистрации: «Moje ime je Ognjen. Moje prezime je Ilić. Moj grad je Užice.»
Форма регистрации просит поля в порядке Grad / Prezime / Ime.

Заполните форму по сообщению. Не копируйте целые предложения; впишите значение каждого поля. Допустимы оба сербских письма.

### Текст / образец ответа

```text
Grad: Užice
Prezime: Ilić
Ime: Ognjen
```

Русский смысл: Город: Ужице; фамилия: Илич; имя: Огнен.

Допустимые ответы: ["Grad: Užice\nPrezime: Ilić\nIme: Ognjen"]

Политика ответа: {"absent_field": "missing", "fields": {"grad": ["Užice", "Ужице"], "ime": ["Ognjen", "Огњен"], "prezime": ["Ilić", "Илић"]}, "id": "a1-written-personal-registration-answers", "normalization": ["NFC", "trim"], "revision": 1, "scoring": "per_field", "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Короткое сообщение администратора ограничено тремя фактами; moje/moj соответствует роду поля.
- **target_alignment:** Извлечение из сообщения и изменение порядка полей, в отличие от карточки профиля.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Ognjen/Огњен, Ilić/Илић, Užice/Ужице. Русское Огнен — смысловой перевод имени, не допустимый сербский ключ.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=3 (biti); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=4 (alphabet); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-2-Moja-dobra-prijateljica-2.pdf#page=5 (possessives); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=175 (ime); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=189 (prezime); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=174 (grad)
- **Разногласия/исключения:** []

Content hash: `1be6d95811fd82e4393e2f3bd194c1680b87d41fefc46410d7b8f62ef0086bd8`.

## a1-written-price-service · revision 1

A1.PRICE_INFO · assessment · `price-service-holdout`

### Контекст и задание

Вымышленный ценник кафе, цена стоит в левой колонке:
Cena (RSD) | Piće
110 | Čaj
150 | Kafa

Найдите цену кофе (kafa) и запишите только цифры. Не считайте сумму заказа.

### Текст / образец ответа

```text
Cena (RSD) | Piće
110 | Čaj
150 | Kafa
```

Русский смысл: Цена в динарах / напиток: 110 — чай; 150 — кофе.

Допустимые ответы: ["150"]

Политика ответа: {"currency": "RSD", "expected_numeral": "150", "id": "a1-written-price-service-answers", "normalization": ["NFC", "trim"], "queried_item": "Kafa", "revision": 1, "scoring": "item_price_match", "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Короткая таблица кафе; суммы вымышленные, не информация о текущих ценах.
- **target_alignment:** Другая ориентация таблицы, набор товаров и семейство; кофе расположен во второй строке.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Только 150; 110 относится к другому товару. Валюта/словесные числа вне узкого ключа.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=48 (drinks); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=51 (price questions); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=128 (dinara)
- **Разногласия/исключения:** []

Content hash: `ffe787fc29de77af7f01fdac26e66ecbef3ca72db0d28af468a15afb8098de90`.

## a1-written-price-shop · revision 1

A1.PRICE_INFO · practice · `price-shop-practice`

### Контекст и задание

Вымышленная полочная табличка:
Хлеб — 95 дин.
Вода — 60 дин.

Сколько стоит вода? Запишите только цифры, без валюты.

### Текст / образец ответа

```text
Хлеб — 95 дин.
Вода — 60 дин.
```

Русский смысл: Хлеб — 95 динаров; вода — 60 динаров.

Допустимые ответы: ["60"]

Политика ответа: {"currency": "RSD", "expected_numeral": "60", "id": "a1-written-price-shop-answers", "normalization": ["NFC", "trim"], "queried_item": "Вода", "revision": 1, "scoring": "item_price_match", "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Два самостоятельных товарных ярлыка; рубрика требует чтения соответствия, не падежа числительного.
- **target_alignment:** Цена воды среди двух строк; неверный товар отличим от неверного числа.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Только 60 для этого формата. Запись словами или с валютой — unresolved, не автоматически ошибочная.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://bcs.lrc.columbia.edu/wp-content/uploads/2021/09/Lekcija-3-Sta-Sto-imamo-2.pdf#page=3 (voda); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=128 (prices in dinara)
- **Разногласия/исключения:** []

Content hash: `e5920085d95b91e7c980567387ce0d7bdd6d164f96c0e050ff0747e528a1c01c`.

## a1-written-request-counter · revision 1

A1.SIMPLE_REQUEST · practice · `request-counter-practice`

### Контекст и задание

Вымышленная стойка напитков: вода доступна, сок закончился. Вы хотите воду. Сотрудник принимает короткую письменную просьбу.

Напишите вежливую просьбу о воде. Не пишите, что вода уже у вас.

### Текст / образец ответа

```text
Молим воду.
```

Русский смысл: Воду, пожалуйста.

Допустимые ответы: ["Молим воду."]

Политика ответа: {"equivalent_script_answers": ["Molim vodu."], "id": "a1-written-request-counter-answers", "normalization": ["NFC", "trim"], "revision": 1, "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Нейтральная короткая просьба; воду — проверенная форма объекта.
- **target_alignment:** Нужны функция просьбы и выбранный напиток; письменная репетиция, не устный навык.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Латиница Molim vodu. — та же запись, не новая проверочная семья. Желаю/хочу и развёрнутые просьбы пока unresolved.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=51 (Molim + akuzativ); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/09/Lekcija-3-Sta-Sto-imamo-2.pdf#page=3 (voda/vodu); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=4 (alphabet)
- **Разногласия/исключения:** []

Content hash: `0cc80b8b2a549256f32d352ec2f73546835c4301d4936d18957166ad7f3af1d6`.

## a1-written-request-kiosk · revision 1

A1.SIMPLE_REQUEST · assessment · `request-kiosk-holdout`

### Контекст и задание

Вымышленный киоск принимает записки. Меню: A — kafa, B — čaj. Покупатель отметил B. Работнику нужна фраза с названием напитка, а не буква заказа.

Составьте вежливую записку заказа по отмеченной позиции B. Не добавляйте количество или состав напитка.

### Текст / образец ответа

```text
Molim čaj.
```

Русский смысл: Чай, пожалуйста.

Допустимые ответы: ["Molim čaj."]

Политика ответа: {"equivalent_script_answers": ["Молим чај."], "id": "a1-written-request-kiosk-answers", "normalization": ["NFC", "trim"], "revision": 1, "unlisted": "unresolved"}

### Внутренние решения

- **naturalness:** Узкая формула; čaj сохраняет форму в выбранной роли.
- **target_alignment:** Перевод позиции меню в записку; нет слова molim в исходном меню и нет образца ответа.
- **answerability:** Ключ конечный; контекст явно задаёт единственный референт. Неперечисленный ответ требует разбора.
- **variants:** Молим чај. — эквивалентное письмо. Обратный порядок Čaj, molim. правдоподобен, но не включён без отдельной проверки.
- **translation:** Русский смысл составлен отдельно: проверены значения, референт и все числа/имена. Не перевод чужого примера.
- **Источники:** https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=51 (Molim + akuzativ); https://serbiversum.com/wp-content/uploads/2023/09/Zbirka-tekstova-i-zadataka-za-nastavnike-i-ucenike-srednje-skole.pdf#page=53 (čaj); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/09/Lekcija-3-Sta-Sto-imamo-2.pdf#page=3 (masculine accusative); https://bcs.lrc.columbia.edu/wp-content/uploads/2021/08/Lekcija-1-Zdravo-1.pdf#page=4 (alphabet)
- **Разногласия/исключения:** []

Content hash: `4a6c2a8f015daee26b262b02ddae1ffe70429142112927aa037e5efa32ca3398`.
