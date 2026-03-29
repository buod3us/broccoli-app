from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    choosing_goal = State()


class Menu(StatesGroup):
    main = State()


class AIConsultant(StatesGroup):
    chatting = State()
