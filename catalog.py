"""
Справочник товаров Mini App.

Каталог в боте через инлайн-кнопки удалён — выбор и корзина в TMA,
а витрина загружает этот список через /api/catalog.
"""
MINI_APP_CATEGORIES = (
    {"id": "all", "title": "Все товары"},
    {"id": "ready_meals", "title": "Готовая еда"},
    {"id": "sausage", "title": "Колбасы"},
    {"id": "horsemeat", "title": "Конина"},
    {"id": "steak", "title": "Стейки"},
    {"id": "fat", "title": "Жир"},
)

MINI_APP_PRODUCT_CATALOG = (
    {
        "id": "buckwheat_chicken",
        "title": "Гречка с курицей",
        "categoryId": "ready_meals",
        "emoji": "🍲",
        "price": 350,
        "image": "images/products/buckwheat_chicken.jpg",
    },
    {
        "id": "rice_chicken",
        "title": "Рис с курицей",
        "categoryId": "ready_meals",
        "emoji": "🍛",
        "price": 350,
        "image": "images/products/rice_chicken.jpg",
    },
    {
        "id": "beef_buckwheat",
        "title": "Гречка с говядиной",
        "categoryId": "ready_meals",
        "emoji": "🥩",
        "price": 350,
        "image": "images/products/beef_buckwheat.jpg",
    },
    {
        "id": "chicken_soup",
        "title": "Куриный суп",
        "categoryId": "ready_meals",
        "emoji": "🥣",
        "price": 250,
        "image": "images/products/chicken_soup.jpg",
    },
    {
        "id": "beef_soup",
        "title": "Говяжий бульон",
        "categoryId": "ready_meals",
        "emoji": "🍲",
        "price": 280,
        "image": "images/products/beef_soup.jpg",
    },
    {
        "id": "sausage_domashnyaya",
        "title": "Колбаса Домашняя",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_domashnyaya.jpg",
    },
    {
        "id": "sausage_sibirskaya",
        "title": "Колбаса Сибирская",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_sibirskaya.jpg",
    },
    {
        "id": "sausage_kamskaya",
        "title": "Колбаса Камская",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_kamskaya.jpg",
    },
    {
        "id": "sausage_pikantnaya",
        "title": "Колбаса Пикантная",
        "categoryId": "sausage",
        "emoji": "🌶",
        "price": 2380,
        "image": "images/products/sausage_pikantnaya.jpg",
    },
    {
        "id": "sausage_venskaya",
        "title": "Колбаса Венская",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_venskaya.jpg",
    },
    {
        "id": "sausage_orekhovaya",
        "title": "Колбаса Ореховая",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_orekhovaya.jpg",
    },
    {
        "id": "sausage_originalnaya",
        "title": "Колбаса Оригинальная",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 3080,
        "image": "images/products/sausage_originalnaya.jpg",
    },
    {
        "id": "sausage_originalnaya_syrokopchenaya",
        "title": "Сырокопчёная Оригинальная",
        "categoryId": "sausage",
        "emoji": "🥓",
        "price": 5180,
        "image": "images/products/sausage_originalnaya_syrokopchenaya.jpg",
    },
    {
        "id": "horse_konina_rublenaya",
        "title": "Конина рубленая",
        "categoryId": "horsemeat",
        "emoji": "🥩",
        "price": 4520,
        "image": "images/products/horse_konina_rublenaya.jpg",
    },
    {
        "id": "horse_konina_pressovannaya",
        "title": "Конина прессованная",
        "categoryId": "horsemeat",
        "emoji": "🥩",
        "price": 5180,
        "image": "images/products/horse_konina_pressovannaya.jpg",
    },
    {
        "id": "horse_steak",
        "title": "Стейк из конины",
        "categoryId": "steak",
        "emoji": "🥩",
        "price": 8400,
        "image": "images/products/horse_steak.jpg",
    },
    {
        "id": "fat_solenyy_bryushnoy",
        "title": "Жир солёный брюшной",
        "categoryId": "fat",
        "emoji": "🧂",
        "price": 1225,
        "image": "images/products/fat_solenyy_bryushnoy.jpg",
    },
    {
        "id": "fat_kopchenyy_bryushnoy",
        "title": "Жир копчёный брюшной",
        "categoryId": "fat",
        "emoji": "🥓",
        "price": 2030,
        "image": "images/products/fat_kopchenyy_bryushnoy.jpg",
    },
)

MINI_APP_PRODUCTS = tuple(
    (item["id"], item["title"])
    for item in MINI_APP_PRODUCT_CATALOG
)
MINI_APP_PRODUCT_IDS = frozenset(product_id for product_id, _ in MINI_APP_PRODUCTS)
MINI_APP_PRODUCT_TITLES = {
    product_id: title for product_id, title in MINI_APP_PRODUCTS
}
MINI_APP_PRODUCT_BY_ID = {
    str(item["id"]): item
    for item in MINI_APP_PRODUCT_CATALOG
}
