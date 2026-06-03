"""banking transaction generator"""

import json
import random
import uuid
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

from faker import Faker


@dataclass
class BankTransaction:
    """banking transaction data structure"""
    transaction_id: str
    account_id: str
    account_type: str          # CHECKING, SAVINGS, CREDIT, INVESTMENT
    amount: float
    currency: str              # CHF, EUR, USD, GBP
    transaction_type: str      # PAYMENT, TRANSFER, WITHDRAWAL, DEPOSIT, FEE
    status: str                # COMPLETED, PENDING, DECLINED, FAILED
    timestamp_ms: int
    merchant_name: Optional[str]
    merchant_category: Optional[str]
    location_city: str
    location_country: str
    channel: str               # MOBILE_APP, WEB, ATM, BRANCH, POS
    risk_score: float          # 0-100
    
    def to_json(self) -> str:
        """convert to JSON string"""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    def to_dict(self) -> dict:
        """convert to dictionary"""
        return asdict(self)


class TransactionGenerator:
    """transaction data generator"""
    
    def __init__(self, seed: int = 42):
        self.fake = Faker()
        Faker.seed(seed)  #repeatable
        
        # account type distribution (typical for Swiss banks)
        self.account_types = ["CHECKING", "SAVINGS", "CREDIT", "INVESTMENT"]
        self.account_type_weights = [0.55, 0.25, 0.15, 0.05]
        
        # transaction type distribution
        self.txn_types = ["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT", "FEE"]
        self.txn_type_weights = [0.45, 0.25, 0.12, 0.10, 0.08]
        
        # currency distribution (typical for Swiss banks)
        self.currencies = ["CHF", "EUR", "USD", "GBP"]
        self.currency_weights = [0.70, 0.15, 0.10, 0.05]
        
        # transaction channel distribution
        self.channels = ["MOBILE_APP", "WEB", "ATM", "BRANCH", "POS"]
        self.channel_weights = [0.50, 0.20, 0.12, 0.08, 0.10]
        
        # transaction status distribution (typical for Swiss banks)
        self.statuses = ["COMPLETED", "PENDING", "DECLINED", "FAILED"]
        self.status_weights = [0.97, 0.02, 0.008, 0.002]
        
        # merchant categories
        self.merchant_categories = [
            "RESTAURANT", "GROCERY", "RETAIL", "TRAVEL", "ENTERTAINMENT",
            "HEALTHCARE", "EDUCATION", "UTILITIES", "TRANSPORTATION", "OTHER"
        ]
        
        # simulate 10000 active accounts
        self.active_accounts = [
            f"CH{random.randint(100000000, 999999999)}{random.choice(['A', 'B', 'C'])}"
            for _ in range(10000)
        ]
    
    def generate_transaction(self) -> BankTransaction:
        """generate a single banking transaction"""
        
        account_id = random.choice(self.active_accounts)
        
        # amount distribution (log-normal distribution to simulate real transactions)
        amount = round(random.lognormvariate(3.5, 1.2), 2)
        amount = min(amount, 50000)  # single transaction limit of 50,000 CHF
        
        # intraday transaction patterns
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 11 or 14 <= current_hour <= 16:
            # peak hours, larger amounts
            amount = amount * random.uniform(0.8, 1.5)
        elif 22 <= current_hour or current_hour <= 5:
            # late night hours, smaller amounts
            amount = amount * random.uniform(0.3, 0.8)
        
        # adjust amount based on transaction type
        txn_type = random.choices(self.txn_types, weights=self.txn_type_weights)[0]
        if txn_type == "FEE":
            amount = round(random.uniform(0.5, 50), 2)
        elif txn_type == "DEPOSIT":
            amount = abs(amount)
        elif txn_type == "WITHDRAWAL":
            amount = min(amount, 1000)
        
        # choose other attributes
        currency = random.choices(self.currencies, weights=self.currency_weights)[0]
        channel = random.choices(self.channels, weights=self.channel_weights)[0]
        status = random.choices(self.statuses, weights=self.status_weights)[0]
        
        # risk score
        risk_score = 0.0
        if amount > 10000:
            risk_score += 30
        if txn_type == "TRANSFER":
            risk_score += 10
        if current_hour >= 23 or current_hour <= 4:
            risk_score += 15
        risk_score = min(round(risk_score + random.uniform(-5, 20), 1), 100)
        
        # merchant information (only for payment transactions)
        merchant_name = None
        merchant_category = None
        if txn_type in ["PAYMENT", "POS"]:
            merchant_name = self.fake.company()
            merchant_category = random.choice(self.merchant_categories)
        
        # location (85% in Switzerland)
        if random.random() < 0.85:
            location_country = "Switzerland"
            location_city = random.choice([
                "Zurich", "Geneva", "Basel", "Bern", "Lausanne", 
                "Lucerne", "St. Gallen", "Lugano"
            ])
        else:
            location_country = self.fake.country()
            location_city = self.fake.city()
        
        return BankTransaction(
            transaction_id=str(uuid.uuid4()),
            account_id=account_id,
            account_type=random.choices(self.account_types, weights=self.account_type_weights)[0],
            amount=round(amount, 2),
            currency=currency,
            transaction_type=txn_type,
            status=status,
            timestamp_ms=int(time.time() * 1000),
            merchant_name=merchant_name,
            merchant_category=merchant_category,
            location_city=location_city,
            location_country=location_country,
            channel=channel,
            risk_score=risk_score
        )