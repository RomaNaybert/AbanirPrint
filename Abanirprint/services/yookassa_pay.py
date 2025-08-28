from yookassa import Configuration, Payment
import uuid

from config import YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

def create_payment(amount: int, user_id: int):
    payment = Payment.create({
        "amount": {
            "value": f"{amount:.2f}",  # в формате "100.00"
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/AbanirPrintBot?start=confirm_payment_{user_id}"
        },
        "capture": True,  # обязательно!
        "description": f"Печать документа для Telegram ID {user_id}"
    }, uuid.uuid4())

    return {
        "id": payment.id,
        "url": payment.confirmation.confirmation_url
    }

def check_payment(payment_id: str) -> str:
    try:
        payment = Payment.find_one(payment_id)
        return payment.status  # 'succeeded', 'pending', 'canceled' и т.п.
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке платежа: {e}")
        return "error"