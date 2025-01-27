# calculations.py
# Changes:
# 1. No changes made. All functionality remains the same.

def calculate_tax_at_vest(shares_vested, vest_price, tax_rate):
    return shares_vested * vest_price * tax_rate

def calculate_capital_gains_tax(sale_price, vest_price, shares_sold, tax_rate, held_over_year):
    capital_gains = (sale_price - vest_price) * shares_sold
    if capital_gains > 0:
        capital_gains_tax = capital_gains * tax_rate
        if held_over_year:
            capital_gains_tax *= 0.5
    else:
        capital_gains_tax = 0
    return capital_gains_tax

def calculate_gains_at_sale(sale_price, vest_price, shares_sold):
    capital_gains_at_sale = (sale_price - vest_price) * shares_sold
    return capital_gains_at_sale