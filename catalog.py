"""
Справочник товаров Mini App: id должны совпадать с web/script.js.

Каталог в боте через инлайн-кнопки удалён — выбор и корзина в TMA.
"""

# Источник данных для будущего API каталога.
# web/script.js пока ещё хранит свой список товаров, на следующем этапе переведём его на API.
MINI_APP_CATEGORIES = (
    {"id": "all", "title": "Все товары"},
    {"id": "chicken", "title": "С курицей"},
    {"id": "beef", "title": "С говядиной"},
    {"id": "soup", "title": "Супы"},
)

MINI_APP_PRODUCT_CATALOG = (
    {
        "id": "buckwheat_chicken",
        "title": "Гречка с курицей",
        "categoryId": "chicken",
        "emoji": "🍲",
        "price": 350,
        "image": "images/products/buckwheat_chicken.jpg",
    },
    {
        "id": "rice_chicken",
        "title": "Рис с курицей",
        "categoryId": "chicken",
        "emoji": "🍛",
        "price": 350,
        "image": "images/products/rice_chicken.jpg",
    },
    {
        "id": "beef_buckwheat",
        "title": "Гречка с говядиной",
        "categoryId": "beef",
        "emoji": "🥩",
        "price": 350,
        "image": "images/products/beef_buckwheat.jpg",
    },
    {
        "id": "chicken_soup",
        "title": "Куриный суп",
        "categoryId": "soup",
        "emoji": "🥣",
        "price": 250,
        "image": "images/products/chicken_soup.jpg",
    },
    {
        "id": "beef_soup",
        "title": "Говяжий бульон",
        "categoryId": "soup",
        "emoji": "🍲",
        "price": 280,
        "image": "images/products/beef_soup.jpg",
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
