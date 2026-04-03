"""
Справочник товаров Mini App: id должны совпадать с web/script.js.

Каталог в боте через инлайн\\-кнопки удалён — выбор и корзина в TMA.
"""

# Синхронизируйте с PRODUCTS в web/script.js
MINI_APP_PRODUCTS = (
    ("buckwheat_chicken", "Гречка с курицей"),
    ("rice_chicken", "Рис с курицей"),
    ("beef_buckwheat", "Гречка с говядиной"),
    ("chicken_soup", "Куриный суп"),
    ("beef_soup", "Говяжий бульон"),
)

MINI_APP_PRODUCT_IDS = frozenset(product_id for product_id, _ in MINI_APP_PRODUCTS)
MINI_APP_PRODUCT_TITLES = {
    product_id: title for product_id, title in MINI_APP_PRODUCTS
}
