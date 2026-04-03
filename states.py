from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    choosing_goal = State()


class Menu(StatesGroup):
    main = State()


class AIConsultant(StatesGroup):
    chatting = State()


class AdminPanel(StatesGroup):
    main = State()
    waiting_promo_add = State()
    waiting_promo_delete = State()
    waiting_ai_promo_text = State()
